import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SUPABASE_SERVICE_ROLE_KEY =
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, apikey",
};

const KEYWORD_MAP: Record<string, string[]> = {
  gmail: ["email", "mail", "pamela", "casella", "comunicaz", "inviato", "ricevuto"],
  kpi: ["kpi", "attività", "chiamate", "visite", "compilato", "giornalier"],
  crm: ["crm", "contatto", "cliente", "azienda", "stato"],
  prospect: ["prospect", "argentina", "brasile", "nuovo", "lead"],
};

const GENERIC_PATTERNS = [
  "cosa sta succedendo",
  "aggiornami",
  "situazione",
  "riepilogo",
  "panoramica",
  "overview",
  "tutto",
];

function detectFonti(question: string): string[] | "all" {
  const q = question.toLowerCase();

  if (GENERIC_PATTERNS.some((p) => q.includes(p))) return "all";

  const matched: string[] = [];
  for (const [fonte, keywords] of Object.entries(KEYWORD_MAP)) {
    if (keywords.some((kw) => q.includes(kw))) matched.push(fonte);
  }

  return matched.length ? matched : ["finale"];
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  try {
    const body = await req.json().catch(() => ({}));
    const question: string = body.question ?? "";

    if (!question.trim()) {
      return new Response(
        JSON.stringify({ error: "Campo 'question' obbligatorio" }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    const fonti = detectFonti(question);

    // Helper: build URL and fetch reports
    const textFilters = "testo=not.is.null&testo=neq.&testo=neq.{}";
    const supaHeaders = {
      apikey: SUPABASE_SERVICE_ROLE_KEY,
      Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
    };

    function buildUrl(fonti: string[] | "all", extraFilters?: string): string {
      const base = `${SUPABASE_URL}/rest/v1/reports`;
      const params = [textFilters];
      if (fonti !== "all") {
        const likeConditions = fonti.map((f) => `fonte.like.${f}*`).join(",");
        params.push(`or=(${likeConditions})`);
      }
      if (extraFilters) params.push(extraFilters);
      params.push("order=created_at.desc", "limit=50", "select=fonte,testo,created_at");
      return `${base}?${params.join("&")}`;
    }

    function extractByFonte(rows: Array<{ fonte: string; testo: string; created_at: string }>) {
      const byFonte: Record<string, { testo: string; created_at: string }> = {};
      for (const r of rows) {
        if (!byFonte[r.fonte] && r.testo && r.testo.length > 50) {
          byFonte[r.fonte] = { testo: r.testo, created_at: r.created_at };
        }
      }
      return byFonte;
    }

    // 1. Try last 24 hours
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    let res = await fetch(buildUrl(fonti, `created_at=gte.${since}`), { headers: supaHeaders });
    let rows = await res.json();
    let byFonte = extractByFonte(rows);

    // 2. Fallback: no time filter if nothing found
    if (!Object.keys(byFonte).length) {
      res = await fetch(buildUrl(fonti), { headers: supaHeaders });
      rows = await res.json();
      byFonte = extractByFonte(rows);
    }

    const fontiTrovate = Object.keys(byFonte);

    if (!fontiTrovate.length) {
      return new Response(
        JSON.stringify({ risposta: "Nessun report trovato.", fonti: [], generato_at: null, data_report: null }),
        {
          status: 404,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    const contenuto = fontiTrovate
      .map((f) => `## ${f.toUpperCase()}\n${byFonte[f].testo}`)
      .join("\n\n");

    const maxDate = fontiTrovate.reduce((max, f) =>
      byFonte[f].created_at > max ? byFonte[f].created_at : max,
      ""
    );

    return new Response(
      JSON.stringify({
        risposta: contenuto,
        fonti: fontiTrovate,
        generato_at: maxDate,
        data_report: maxDate,
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
