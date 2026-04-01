import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

Deno.serve(async (req) => {
  try {
    // 1. Leggi il payload canonico più recente da Supabase
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/canonical_data?cliente=eq.aloe-vera-pilot&order=creato_at.desc&limit=1`,
      {
        headers: {
          apikey: SUPABASE_SERVICE_ROLE_KEY,
          Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
        },
      }
    );
    const rows = await res.json();
    if (!rows.length) return new Response("Nessun dato trovato", { status: 404 });

    const payload = rows[0].payload;

    // 2. Costruisci prompt compatto
    const kpi_recenti = payload.KPI?.rows?.slice(-7) ?? [];
    const crm_top = (payload.CRM?.rows ?? []).filter((r: any) => r.Note).slice(0, 15);
    const prompt = `Sei il Chief of Staff AI di un'azienda che vende prodotti aloe vera in Brasile e Argentina.

KPI ultimi 7 giorni:
${JSON.stringify(kpi_recenti, null, 2)}

CRM - contatti con note recenti:
${JSON.stringify(crm_top, null, 2)}

Scrivi un report manageriale in italiano di 150-200 parole. Identifica trend, segnala anomalie, indica le 2-3 priorità più urgenti. Tono diretto, professionale.`;

    // 3. Chiama Anthropic API
    const anthropicRes = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-6",
        max_tokens: 1024,
        messages: [{ role: "user", content: prompt }],
      }),
    });
    const anthropicData = await anthropicRes.json();
    const testo = anthropicData.content?.[0]?.text ?? "Errore nella generazione";

    // 4. Salva report su Supabase
    await fetch(`${SUPABASE_URL}/rest/v1/reports`, {
      method: "POST",
      headers: {
        apikey: SUPABASE_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ cliente: "aloe-vera-pilot", testo }),
    });

    return new Response(JSON.stringify({ ok: true, report: testo }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), { status: 500 });
  }
});
