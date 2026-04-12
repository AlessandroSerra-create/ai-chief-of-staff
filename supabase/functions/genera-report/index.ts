import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

const COMMERCIALI = ["pamela", "dante"];

async function callClaude(prompt: string, maxTokens = 1024): Promise<string> {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-sonnet-4-6",
      max_tokens: maxTokens,
      messages: [{ role: "user", content: prompt }],
    }),
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
  console.log(`Salvato report ${cliente}/${fonte}: status ${res.status}`);
}

async function elaboraCommerciale(commerciale: string) {
  const clienteId = `aloe-vera-pilot-${commerciale}`;

  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/canonical_data?cliente=eq.${clienteId}&fonte=is.null&order=creato_at.desc&limit=1`,
    {
      headers: {
        apikey: SUPABASE_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
      },
    }
  );
  const rows = await res.json();
  if (!rows.length) {
    console.log(`Nessun dato per ${clienteId}`);
    return [];
  }

  const payload = rows[0].payload;
  const kpi = payload.KPI?.rows?.slice(-7) ?? [];
  const crm = (payload.CRM?.rows ?? []).filter((r: any) => r.Atualizações).slice(0, 20);
  const bra = payload["BRA - Novos a contactar"]?.rows?.slice(0, 10) ?? [];
  const arg = payload["ARG - Novos a contactar"]?.rows?.slice(0, 10) ?? [];

  const nomeDisplay = commerciale.charAt(0).toUpperCase() + commerciale.slice(1);

  const [reportKPI, reportCRM, reportProspect] = await Promise.all([
    callClaude(
      `Sei il Chief of Staff AI. Analizza i KPI commerciali degli ultimi 7 giorni di ${nomeDisplay} e scrivi un report di 100 parole in italiano. Identifica trend e anomalie. Tono diretto.\n\n${JSON.stringify(kpi, null, 2)}`
    ),
    callClaude(
      `Sei il Chief of Staff AI. Analizza i contatti CRM con note recenti di ${nomeDisplay} e scrivi un report di 100 parole in italiano. Identifica opportunità e rischi. Tono diretto.\n\n${JSON.stringify(crm, null, 2)}`
    ),
    callClaude(
      `Sei il Chief of Staff AI. Analizza i prospect di ${nomeDisplay} per Brasile e Argentina e scrivi un report di 100 parole in italiano. Identifica priorità di contatto. Tono diretto.\n\nBRASILE:\n${JSON.stringify(bra, null, 2)}\n\nARGENTINA:\n${JSON.stringify(arg, null, 2)}`
    ),
  ]);

  await Promise.all([
    salvaReport(clienteId, "kpi", reportKPI),
    salvaReport(clienteId, "crm", reportCRM),
    salvaReport(clienteId, "prospect", reportProspect),
  ]);

  return ["kpi", "crm", "prospect"];
}

Deno.serve(async (_req) => {
  try {
    const risultati: Record<string, string[]> = {};

    for (const commerciale of COMMERCIALI) {
      const fonti = await elaboraCommerciale(commerciale);
      risultati[commerciale] = fonti;
    }

    // Report Gmail — invariato, usa ancora aloe-vera-pilot come cliente
    const cliente = "aloe-vera-pilot";
    const gmailRes = await fetch(
      `${SUPABASE_URL}/rest/v1/canonical_data?cliente=eq.${cliente}&fonte=like.gmail_*&order=creato_at.desc`,
      {
        headers: {
          apikey: SUPABASE_SERVICE_ROLE_KEY,
          Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
        },
      }
    );
    const gmailRows = await gmailRes.json();

    const caselle = gmailRows.filter((row: any) => {
      const p = row.payload ?? {};
      return (p.email_ricevute?.length ?? 0) > 0 || (p.email_inviate?.length ?? 0) > 0;
    });

    const gmailResults = await Promise.all(
      caselle.map(async (row: any) => {
        const fonte = row.fonte as string;
        const p = row.payload ?? {};
        const ricevute = p.email_ricevute ?? [];
        const inviate = p.email_inviate ?? [];
        const emailName = fonte
          .replace("gmail_", "")
          .replace(/_/g, ".")
          .replace(".sorellebrasil.com", "@sorellebrasil.com");

        const report = await callClaude(
          `Sei il Chief of Staff AI. Produci un report dettagliato della casella ${emailName} degli ultimi 2 giorni.\n\n` +
          `DATI EMAIL RICEVUTE:\n${JSON.stringify(ricevute, null, 2)}\n\n` +
          `DATI EMAIL INVIATE:\n${JSON.stringify(inviate, null, 2)}\n\n` +
          `Il report DEVE contenere queste 3 sezioni:\n\n` +
          `1. **EMAIL RICEVUTE** — elenca OGNI email con: mittente, oggetto, data.\n\n` +
          `2. **EMAIL INVIATE** — elenca OGNI email con: destinatario, oggetto, data.\n\n` +
          `3. **ANALISI** — max 80 parole: temi principali, cosa è urgente.\n\n` +
          `Scrivi in italiano.`,
          1024
        );
        return { fonte, report };
      })
    );

    await Promise.all(
      gmailResults.map(({ fonte, report }) => salvaReport(cliente, fonte, report))
    );

    return new Response(
      JSON.stringify({ ok: true, commerciali: risultati }),
      { headers: { "Content-Type": "application/json" } }
    );
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), { status: 500 });
  }
});
