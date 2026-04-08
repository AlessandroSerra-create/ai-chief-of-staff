import "jsr:@supabase/functions-js/edge-runtime.d.ts";
 
const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
 
Deno.serve(async (req) => {
  const body = await req.json().catch(() => ({}));
  const focus = body.focus ?? "analisi generale";
  const cliente = body.cliente ?? "aloe-vera-pilot";
 
  try {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/reports?cliente=eq.${cliente}&fonte=neq.finale&order=created_at.desc&limit=50`,
      { headers: { apikey: SUPABASE_SERVICE_ROLE_KEY, Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}` } }
    );
    const reports = await res.json();
    if (!reports.length) return new Response("Nessun report trovato", { status: 404 });
 
    const byFonte: Record<string, string> = {};
    for (const r of reports) {
      if (!byFonte[r.fonte]) byFonte[r.fonte] = r.testo;
    }
 
    const mainReports: string[] = [];
    const gmailReports: string[] = [];
    for (const [fonte, testo] of Object.entries(byFonte)) {
      if (fonte.startsWith("gmail_")) {
        const emailName = fonte.replace("gmail_", "").replace(/_/g, ".").replace(".sorellebrasil.com", "@sorellebrasil.com");
        gmailReports.push(`### ${emailName}\n${testo}`);
      } else {
        mainReports.push(`## ${fonte.toUpperCase()}\n${testo}`);
      }
    }
 
    let reportsText = mainReports.join("\n\n");
    if (gmailReports.length) {
      reportsText += `\n\n## COMUNICAÇÕES EMAIL\n${gmailReports.join("\n\n")}`;
    }
 
    let configContext = "";
    try {
      const configRes = await fetch(
        `${SUPABASE_URL}/rest/v1/configurazioni?cliente=eq.${cliente}&limit=1`,
        { headers: { apikey: SUPABASE_SERVICE_ROLE_KEY, Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}` } }
      );
      const configRows = await configRes.json();
      if (configRows.length) {
        const config = configRows[0];
        const focusList = Array.isArray(config.focus) ? config.focus.join(", ") : (config.focus ?? "");
        const istruzione = config.istruzione_custom ?? "";
        if (focusList || istruzione) {
          configContext = `FOCO SOLICITADO PELO CEO: ${focusList}\nINSTRUÇÃO PERSONALIZADA: ${istruzione}\nPrioritize esses aspectos na análise e nas recomendações.\n\n`;
        }
      }
    } catch (_) {}
 
    let temporalContext = "";
    try {
      const canonRes = await fetch(
        `${SUPABASE_URL}/rest/v1/canonical_data?cliente=eq.${cliente}&order=created_at.desc&limit=1`,
        { headers: { apikey: SUPABASE_SERVICE_ROLE_KEY, Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}` } }
      );
      const canonRows = await canonRes.json();
      if (canonRows.length) {
        const payload = canonRows[0].payload ?? {};
        const dataOggi: string = payload.data_oggi ?? "";
        const ultimaDataKpi: string = payload.ultima_data_kpi ?? "";
        if (dataOggi && ultimaDataKpi) {
          const parseDate = (s: string) => {
            const [d, m, y] = s.split("/").map(Number);
            return new Date(y, m - 1, d).getTime();
          };
          const daysDiff = Math.round((parseDate(dataOggi) - parseDate(ultimaDataKpi)) / 86400000);
          temporalContext = `CONTEXTO TEMPORAL: Hoje é ${dataOggi}. O último dia com dados preenchidos é ${ultimaDataKpi}. Passaram-se ${daysDiff} dias desde o último registro.\n\n`;
        }
      }
    } catch (_) {}
 
    const prompt = `${temporalContext}${configContext}Você é o Chief of Staff de IA da Sorelle Brasil, empresa de produtos de aloe vera no Brasil e Argentina.
 
O CEO pediu: "${focus}"
 
Relatórios disponíveis:
${reportsText}
 
COMO RESPONDER:
- Fale como um Chief of Staff experiente, não como um sistema de dados
- Se um dado não estiver no relatório, diga "não tenho esse dado no relatório atual" — e sugira o que verificar
- Interprete os dados: o que significam para o negócio? O que exige atenção?
- Nunca redirecione o CEO para "consultar logs" ou "verificar sistemas" — você é quem faz isso
 
ESTRUTURA DO RELATÓRIO:
1. SITUAÇÃO GERAL (3-4 linhas diretas — como está o negócio hoje)
2. EMAIL POR CAIXA: todas as caixas presentes nos dados, 1-2 linhas cada
3. KPI E PIPELINE: tendências principais, o que está indo bem e o que preocupa
4. 3 AÇÕES CONCRETAS nas próximas 48 horas — específicas, acionáveis
 
Tom: direto, profissional, como quem conhece bem o negócio e respeita o tempo do CEO.`;
 
    const anthropicRes = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json" },
      body: JSON.stringify({ model: "claude-sonnet-4-6", max_tokens: 2500, messages: [{ role: "user", content: prompt }] }),
    });
    const data = await anthropicRes.json();
    const testo = data.content?.[0]?.text ?? "Errore";
 
    await fetch(`${SUPABASE_URL}/rest/v1/reports`, {
      method: "POST",
      headers: { apikey: SUPABASE_SERVICE_ROLE_KEY, Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`, "Content-Type": "application/json", "Prefer": "return=minimal" },
      body: JSON.stringify({ cliente, fonte: "finale", testo }),
    });
 
    console.log("Report finale salvato.");
    return new Response(JSON.stringify({ ok: true }), { headers: { "Content-Type": "application/json" } });
 
  } catch (err) {
    console.error("Errore:", err);
    return new Response(JSON.stringify({ error: String(err) }), { status: 500 });
  }
});
