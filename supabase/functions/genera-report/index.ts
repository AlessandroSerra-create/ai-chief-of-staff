import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

async function callClaude(prompt: string): Promise<string> {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json" },
    body: JSON.stringify({ model: "claude-sonnet-4-6", max_tokens: 1024, messages: [{ role: "user", content: prompt }] }),
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

Deno.serve(async (req) => {
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

    // Report KPI
    const kpi = payload.KPI?.rows?.slice(-7) ?? [];
    const reportKPI = await callClaude(`Sei il Chief of Staff AI. Analizza questi KPI commerciali degli ultimi 7 giorni e scrivi un report di 100 parole in italiano. Identifica trend e anomalie. Tono diretto.\n\n${JSON.stringify(kpi, null, 2)}`);
    await salvaReport(cliente, "kpi", reportKPI);

    // Report CRM
    const crm = (payload.CRM?.rows ?? []).filter((r: any) => r.Note).slice(0, 20);
    const reportCRM = await callClaude(`Sei il Chief of Staff AI. Analizza questi contatti CRM con note recenti e scrivi un report di 100 parole in italiano. Identifica opportunità e rischi. Tono diretto.\n\n${JSON.stringify(crm, null, 2)}`);
    await salvaReport(cliente, "crm", reportCRM);

    // Report Prospect
    const bra = payload.BRA?.rows?.slice(0, 10) ?? [];
    const arg = payload.ARG?.rows?.slice(0, 10) ?? [];
    const reportProspect = await callClaude(`Sei il Chief of Staff AI. Analizza questi prospect per Brasile e Argentina e scrivi un report di 100 parole in italiano. Identifica priorità di contatto. Tono diretto.\n\nBRASILE:\n${JSON.stringify(bra, null, 2)}\n\nARGENTINA:\n${JSON.stringify(arg, null, 2)}`);
    await salvaReport(cliente, "prospect", reportProspect);

    // Report Gmail — un report per ogni casella
    const gmailRes = await fetch(
      `${SUPABASE_URL}/rest/v1/canonical_data?cliente=eq.${cliente}&fonte=like.gmail_*&order=creato_at.desc`,
      { headers: { apikey: SUPABASE_SERVICE_ROLE_KEY, Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}` } }
    );
    const gmailRows = await gmailRes.json();
    const gmailFonti: string[] = [];

    for (const row of gmailRows) {
      const fonte = row.fonte as string;
      const p = row.payload ?? {};
      const ricevute = p.email_ricevute ?? [];
      const inviate = p.email_inviate ?? [];

      if (ricevute.length === 0 && inviate.length === 0) continue;

      const emailName = fonte.replace("gmail_", "").replace(/_/g, ".").replace(".sorellebrasil.com", "@sorellebrasil.com");

      const reportGmail = await callClaude(
        `Sei il Chief of Staff AI. Analizza le comunicazioni email esterne della casella ${emailName} degli ultimi 2 giorni.\n\n` +
        `EMAIL RICEVUTE (da esterni):\n${JSON.stringify(ricevute, null, 2)}\n\n` +
        `EMAIL INVIATE (a esterni):\n${JSON.stringify(inviate, null, 2)}\n\n` +
        `Scrivi un riassunto di 80 parole in italiano: con chi ha comunicato, su quali argomenti, cosa sembra urgente. Tono diretto.`
      );
      await salvaReport(cliente, fonte, reportGmail);
      gmailFonti.push(fonte);
    }

    return new Response(JSON.stringify({ ok: true, fonti: ["kpi", "crm", "prospect", ...gmailFonti] }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), { status: 500 });
  }
});
