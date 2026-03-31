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
    """Prova a parsare una stringa data in vari formati, ritorna None se fallisce."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def estrai_kpi_14_giorni(rows):
    """Ritorna le righe KPI degli ultimi 14 giorni con almeno un valore numerico."""
    cutoff = datetime.now() - timedelta(days=14)
    risultati = []
    for row in rows:
        data = parse_data(row.get("Data", ""))
        if data and data >= cutoff:
            risultati.append(row)
    # Ordina per data crescente
    risultati.sort(key=lambda r: parse_data(r.get("Data", "")) or datetime.min)
    return risultati


def estrai_crm_con_note(rows, max_righe=30):
    """Ritorna le aziende CRM con campo Atualizações non vuoto."""
    con_note = [
        r for r in rows
        if r.get("Atualizações", "").strip()
    ]
    return con_note[:max_righe]


def estrai_prospect(rows, max_righe=15):
    """Ritorna i primi N prospect (tutte le righe, non c'è filtro stato esplicito)."""
    non_vuoti = [
        r for r in rows
        if any(v.strip() for v in r.values())
    ]
    return non_vuoti[:max_righe]


def costruisci_riassunto(dati):
    righe = []

    # --- KPI: ultimi 14 giorni ---
    kpi_rows = dati.get("KPI", {}).get("rows", [])
    kpi_recenti = estrai_kpi_14_giorni(kpi_rows)
    righe.append("## KPI — Ultimi 14 giorni")
    if kpi_recenti:
        righe.append(f"({len(kpi_recenti)} giorni con dati nel periodo)")
        righe.append(json.dumps(kpi_recenti, ensure_ascii=False, indent=2))
    else:
        righe.append("Nessun dato KPI negli ultimi 14 giorni.")
    righe.append("")

    # --- CRM: aziende con note ---
    crm_rows = dati.get("CRM", {}).get("rows", [])
    crm_con_note = estrai_crm_con_note(crm_rows, max_righe=30)
    righe.append(f"## CRM — Aziende con aggiornamenti ({len(crm_con_note)} su {len(crm_rows)} totali)")
    if crm_con_note:
        righe.append(json.dumps(crm_con_note, ensure_ascii=False, indent=2))
    else:
        righe.append("Nessuna azienda con note nel CRM.")
    righe.append("")

    # --- Prospect BRA ---
    bra_rows = dati.get("BRA - Novos a contactar", {}).get("rows", [])
    bra_prospect = estrai_prospect(bra_rows, max_righe=15)
    righe.append(f"## Prospect BRASILE — Primi {len(bra_prospect)} (totale: {len(bra_rows)})")
    if bra_prospect:
        righe.append(json.dumps(bra_prospect, ensure_ascii=False, indent=2))
    else:
        righe.append("Nessun prospect BRA disponibile.")
    righe.append("")

    # --- Prospect ARG ---
    arg_rows = dati.get("ARG - Novos a contactar", {}).get("rows", [])
    arg_prospect = estrai_prospect(arg_rows, max_righe=15)
    righe.append(f"## Prospect ARGENTINA — Primi {len(arg_prospect)} (totale: {len(arg_rows)})")
    if arg_prospect:
        righe.append(json.dumps(arg_prospect, ensure_ascii=False, indent=2))
    else:
        righe.append("Nessun prospect ARG disponibile.")
    righe.append("")

    return "\n".join(righe)


def genera_report(riassunto):
    http_client = httpx.Client(
        timeout=httpx.Timeout(30.0, connect=10.0),
    )
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        http_client=http_client,
    )

    system_prompt = """Sei un analista commerciale esperto. Analizza i dati forniti da un CRM e un tracker KPI di un team di vendita B2B e produci un report manageriale chiaro, sintetico e utile, scritto in italiano formale.

Il report deve avere esattamente queste 4 sezioni:

1. RIEPILOGO ATTIVITÀ COMMERCIALE (ultimi 14 giorni)
   - Trend: email, follow-up, risposte, chiamate, riunioni giorno per giorno
   - Medie giornaliere e settimanali
   - Anomalie: giorni a zero, picchi, buchi di dati

2. STATO PIPELINE CRM
   - Pattern ricorrenti nelle note (settori, obiezioni, interesse, stadio trattativa)
   - Aziende da prioritizzare subito (segnali positivi nelle note)
   - Aziende ferme da riattivare (note vecchie o assenti)

3. PROSPECT DA CONTATTARE
   - Brasile: top 5 con motivazione specifica per ognuno
   - Argentina: top 5 con motivazione specifica per ognuno
   - Criteri usati per la prioritizzazione

4. ALERT CRITICI PER IL CEO
   - Cali significativi di attività
   - Buchi di dati o KPI non compilati
   - Situazioni commerciali che richiedono attenzione immediata

Usa un tono diretto e operativo. Includi numeri specifici. Sii conciso ma completo."""

    user_message = f"""Ecco il riassunto dei dati estratti dal Google Sheet aziendale (KPI ultimi 14 giorni, CRM con note, prospect BRA e ARG):

{riassunto}

Genera il report manageriale completo seguendo le 4 sezioni indicate."""

    max_tentativi = 3
    attesa = 5

    for tentativo in range(1, max_tentativi + 1):
        try:
            print(f"Generazione report in corso (tentativo {tentativo}/{max_tentativi})...", flush=True)

            with client.messages.stream(
                model=MODEL,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                testo = ""
                for chunk in stream.text_stream:
                    print(chunk, end="", flush=True)
                    testo += chunk

            print("\n")
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
        print(f"Salvato: {nome}")


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRORE: ANTHROPIC_API_KEY non impostata.")
        return

    print(f"Lettura {JSON_FILE}...")
    dati = carica_dati()
    for tab, contenuto in dati.items():
        print(f"  [{tab}] {len(contenuto.get('rows', []))} righe")

    print("\nCostruzione riassunto intelligente...")
    riassunto = costruisci_riassunto(dati)
    print(f"Riassunto: {len(riassunto)} caratteri\n")

    testo_report = genera_report(riassunto)
    salva_report(testo_report)


if __name__ == "__main__":
    main()
