import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

Deno.serve(async (req) => {
  const body = await req.json().catch(() => ({}));
  const focus = body.focus ?? "analisi generale";
  const cliente = body.cliente ?? "aloe-vera-pilot";

  EdgeRuntime.waitUntil((async () => {
    try {
      const res = await fetch(
        `${SUPABASE_URL}/rest/v1/reports?cliente=eq.${cliente}&fonte=neq.finale&order=created_at.desc&limit=10`,
        { headers: { apikey: SUPABASE_SERVICE_ROLE_KEY, Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}` } }
      );
      const reports = await res.json();
      if (!reports.length) { console.log("Nessun report trovato"); return; }

      const byFonte: Record<string, string> = {};
      for (const r of reports) {
        if (!byFonte[r.fonte]) byFonte[r.fonte] = r.testo;
      }

      const reportsText = Object.entries(byFonte)
        .map(([fonte, testo]) => `## ${fonte.toUpperCase()}\n${testo}`)
        .join("\n\n");

      const prompt = `Sei il Chief of Staff AI di un'azienda che vende prodotti aloe vera in Brasile e Argentina.\n\nIl CEO ha richiesto: "${focus}"\n\nReport disponibili:\n${reportsText}\n\nScrivi un report finale di 200-250 parole in italiano che risponde direttamente alla richiesta del CEO. Indica 3 azioni concrete da intraprendere nelle prossime 48 ore. Tono diretto, manageriale.`;

      const anthropicRes = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json" },
        body: JSON.stringify({ model: "claude-sonnet-4-6", max_tokens: 1500, messages: [{ role: "user", content: prompt }] }),
      });
      const data = await anthropicRes.json();
      const testo = data.content?.[0]?.text ?? "Errore";

      await fetch(`${SUPABASE_URL}/rest/v1/reports`, {
        method: "POST",
        headers: { apikey: SUPABASE_SERVICE_ROLE_KEY, Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`, "Content-Type": "application/json", "Prefer": "return=minimal" },
        body: JSON.stringify({ cliente, fonte: "finale", testo }),
      });
      console.log("Report finale salvato.");
    } catch (err) {
      console.error("Errore:", err);
    }
  })());

  return new Response(JSON.stringify({ ok: true, status: "in elaborazione" }), {
    headers: { "Content-Type": "application/json" },
  });
});
