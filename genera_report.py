import json
import os
import time
import traceback
import httpx
import anthropic
from datetime import datetime, timedelta

JSON_FILE = "dati_canonici.json"
MODEL = "claude-opus-4-5"


def carica_dati():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_data(s):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def estrai_kpi_7_giorni(rows):
    cutoff = datetime.now() - timedelta(days=7)
    risultati = [
        r for r in rows
        if (d := parse_data(r.get("Data", ""))) and d >= cutoff
    ]
    risultati.sort(key=lambda r: parse_data(r.get("Data", "")) or datetime.min)
    return risultati


def estrai_crm_con_note(rows, max_righe=10):
    con_note = [r for r in rows if r.get("Atualizações", "").strip()]
    return con_note[:max_righe]


def costruisci_riassunto(dati):
    parti = []

    kpi_rows = dati.get("KPI", {}).get("rows", [])
    kpi_recenti = estrai_kpi_7_giorni(kpi_rows)
    parti.append("KPI ULTIMI 7 GIORNI:")
    if kpi_recenti:
        for r in kpi_recenti:
            parti.append(
                f"  {r.get('Data','')} | email={r.get('Novos e-mails enviados','')} "
                f"followup={r.get('Follow-ups enviados','')} "
                f"risposte={r.get('Respostas recebidas','')} "
                f"chiamate={r.get('Ligações efetuadas','')} "
                f"riunioni={r.get('Reuniões agendadas','')}"
            )
    else:
        parti.append("  Nessun dato negli ultimi 7 giorni.")

    crm_rows = dati.get("CRM", {}).get("rows", [])
    crm_con_note = estrai_crm_con_note(crm_rows, max_righe=10)
    parti.append(f"\nCRM TOP 10 CON NOTE (totale aziende: {len(crm_rows)}):")
    for r in crm_con_note:
        parti.append(
            f"  {r.get('Nome da empresa','')} | {r.get('Data do contato','')} | {r.get('Atualizações','')[:80]}"
        )

    riassunto = "\n".join(parti)
    return riassunto[:2000]


def genera_report(riassunto):
    http_client = httpx.Client(timeout=httpx.Timeout(None, connect=15.0))
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        http_client=http_client,
    )

    prompt = f"""Você é o Chief of Staff de IA da Sorelle Brasil, empresa de produtos de aloe vera no Brasil e Argentina.
Analise os dados abaixo e gere um relatório intermediário em português com 4 seções:

1. KPIs (tendência dos últimos 7 dias — o que está subindo, o que está caindo, o que preocupa)
2. PIPELINE CRM (empresas que precisam de atenção, contatos parados, prioridades)
3. PROSPECTS (quem contatar e por quê)
4. ALERTAS (quedas, dados faltando, urgências para o CEO)

Interprete os dados — não apenas liste. Se um número é baixo, diga que é baixo e por quê isso importa.
Seja direto e conciso.

Dados: {riassunto}"""

    max_tentativi = 3
    attesa = 5

    for tentativo in range(1, max_tentativi + 1):
        try:
            print(f"Generazione report (tentativo {tentativo}/{max_tentativi})...", flush=True)

            risposta = client.messages.create(
                model=MODEL,
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )

            testo = risposta.content[0].text
            print(testo, flush=True)
            return testo

        except Exception as e:
            print(f"\nERRORE tentativo {tentativo}/{max_tentativi}: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()
            if tentativo < max_tentativi:
                print(f"Nuovo tentativo tra {attesa} secondi...", flush=True)
                time.sleep(attesa)
            else:
                print("Tutti i tentativi esauriti. Interruzione.", flush=True)
                raise


def salva_report(testo):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    intestazione = (
        f"REPORT COMMERCIALE MANAGERIALE\n"
        f"Generato il: {datetime.now().strftime('%d/%m/%Y alle %H:%M:%S')}\n"
        f"Modello: {MODEL}\n"
        f"{'=' * 60}\n\n"
    )
    contenuto = intestazione + testo
    for nome in ("report_ultimo.txt", f"report_{timestamp}.txt"):
        with open(nome, "w", encoding="utf-8") as f:
            f.write(contenuto)
        print(f"Salvato: {nome}", flush=True)


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRORE: ANTHROPIC_API_KEY non impostata.")
        return

    print(f"Lettura {JSON_FILE}...", flush=True)
    dati = carica_dati()
    for tab, contenuto in dati.items():
        print(f"  [{tab}] {len(contenuto.get('rows', []))} righe")

    print("\nCostruzione riassunto...", flush=True)
    riassunto = costruisci_riassunto(dati)
    print(f"Riassunto: {len(riassunto)} caratteri\n", flush=True)

    testo_report = genera_report(riassunto)
    salva_report(testo_report)


if __name__ == "__main__":
    main()
