import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

async function callClaude(prompt: string, maxTokens = 4096): Promise<string> {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json" },
    body: JSON.stringify({ model: "claude-sonnet-4-6", max_tokens: maxTokens, messages: [{ role: "user", content: prompt }] }),
  });
  const data = await res.json();
  return data.content?.[0]?.text ?? "Errore nella generazione";
}

async function salvaReport(cliente: string, fonte: string, testo: string) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/reports`, {
    method: "POST",
    headers: {
      apikey: SUPABASE_SERVICE_ROLE_KEY,
      Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
      "Content-Type": "application/json",
      "Prefer": "return=minimal",
    },
    body: JSON.stringify({ cliente, fonte, testo }),
  });
  console.log(`Salvato report ${fonte}: status ${res.status}`);
}

Deno.serve(async (_req) => {
  try {
    const cliente = "aloe-vera-pilot";

    // Leggi canonical_data principale (KPI, CRM, prospect)
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/canonical_data?cliente=eq.${cliente}&fonte=is.null&order=creato_at.desc&limit=1`,
      { headers: { apikey: SUPABASE_SERVICE_ROLE_KEY, Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}` } }
    );
    const rows = await res.json();
    if (!rows.length) return new Response("Nessun dato trovato", { status: 404 });

    const payload = rows[0].payload;

    // KPI, CRM, Prospect in parallelo
    const kpi = payload.KPI?.rows?.slice(-7) ?? [];
    const crm = (payload.CRM?.rows ?? []).filter((r: any) => r.Note).slice(0, 20);
    const bra = payload.BRA?.rows?.slice(0, 10) ?? [];
    const arg = payload.ARG?.rows?.slice(0, 10) ?? [];

    const [reportKPI, reportCRM, reportProspect] = await Promise.all([
      callClaude(`Sei il Chief of Staff AI. Analizza questi KPI commerciali degli ultimi 7 giorni e scrivi un report di 100 parole in italiano. Identifica trend e anomalie. Tono diretto.\n\n${JSON.stringify(kpi, null, 2)}`, 1024),
      callClaude(`Sei il Chief of Staff AI. Analizza questi contatti CRM con note recenti e scrivi un report di 100 parole in italiano. Identifica opportunità e rischi. Tono diretto.\n\n${JSON.stringify(crm, null, 2)}`, 1024),
      callClaude(`Sei il Chief of Staff AI. Analizza questi prospect per Brasile e Argentina e scrivi un report di 100 parole in italiano. Identifica priorità di contatto. Tono diretto.\n\nBRASILE:\n${JSON.stringify(bra, null, 2)}\n\nARGENTINA:\n${JSON.stringify(arg, null, 2)}`, 1024),
    ]);

    await Promise.all([
      salvaReport(cliente, "kpi", reportKPI),
      salvaReport(cliente, "crm", reportCRM),
      salvaReport(cliente, "prospect", reportProspect),
    ]);

    // Report Gmail — un report per ogni casella, in parallelo a batch di 4
    const gmailRes = await fetch(
      `${SUPABASE_URL}/rest/v1/canonical_data?cliente=eq.${cliente}&fonte=like.gmail_*&order=creato_at.desc`,
      { headers: { apikey: SUPABASE_SERVICE_ROLE_KEY, Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}` } }
    );
    const gmailRows = await gmailRes.json();
    const gmailFonti: string[] = [];

    // Filtra caselle con dati
    const caselle = gmailRows.filter((row: any) => {
      const p = row.payload ?? {};
      return (p.email_ricevute?.length ?? 0) > 0 || (p.email_inviate?.length ?? 0) > 0;
    });

    // Processa in batch di 4 per non sovraccaricare
    for (let i = 0; i < caselle.length; i += 4) {
      const batch = caselle.slice(i, i + 4);
      const results = await Promise.all(batch.map(async (row: any) => {
        const fonte = row.fonte as string;
        const p = row.payload ?? {};
        const ricevute = p.email_ricevute ?? [];
        const inviate = p.email_inviate ?? [];
        const emailName = fonte.replace("gmail_", "").replace(/_/g, ".").replace(".sorellebrasil.com", "@sorellebrasil.com");

        const report = await callClaude(
          `Sei il Chief of Staff AI. Produci un report dettagliato della casella ${emailName} degli ultimi 2 giorni.\n\n` +
          `DATI EMAIL RICEVUTE:\n${JSON.stringify(ricevute, null, 2)}\n\n` +
          `DATI EMAIL INVIATE:\n${JSON.stringify(inviate, null, 2)}\n\n` +
          `Il report DEVE contenere queste 3 sezioni:\n\n` +
          `1. **EMAIL RICEVUTE** — elenca OGNI email con: mittente (nome e indirizzo), oggetto esatto, data. Non omettere nessuna email.\n\n` +
          `2. **EMAIL INVIATE** — elenca OGNI email con: destinatario (nome e indirizzo), oggetto esatto, data. Non omettere nessuna email.\n\n` +
          `3. **ANALISI** — breve analisi (max 80 parole): temi principali delle comunicazioni, cosa appare urgente o richiede azione immediata.\n\n` +
          `REGOLE: Non fare riassunti vaghi. Elenca ogni email singolarmente con mittente/destinatario e oggetto esatto. Il CEO deve poter cercare per nome o azienda. Scrivi in italiano.`
        );
        return { fonte, report };
      }));

      await Promise.all(results.map(({ fonte, report }) => {
        gmailFonti.push(fonte);
        return salvaReport(cliente, fonte, report);
      }));
    }

    return new Response(JSON.stringify({ ok: true, fonti: ["kpi", "crm", "prospect", ...gmailFonti] }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), { status: 500 });
  }
});
