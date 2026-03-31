import json
import os
import anthropic
from datetime import datetime

JSON_FILE = "dati_canonici.json"
MODEL = "claude-opus-4-5"


def carica_dati():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def costruisci_contesto(dati):
    sezioni = []
    for tab, contenuto in dati.items():
        headers = contenuto.get("headers", [])
        rows = contenuto.get("rows", [])
        sezioni.append(f"### Foglio: {tab}")
        sezioni.append(f"Colonne: {', '.join(headers)}")
        sezioni.append(f"Numero di righe: {len(rows)}")
        # Include tutte le righe (il modello ha contesto ampio)
        if rows:
            sample = json.dumps(rows, ensure_ascii=False, indent=2)
            sezioni.append(f"Dati:\n{sample}")
        sezioni.append("")
    return "\n".join(sezioni)


def genera_report(contesto):
    client = anthropic.Anthropic()  # usa ANTHROPIC_API_KEY dall'ambiente

    system_prompt = """Sei un analista commerciale esperto. Analizza i dati forniti da un CRM e un tracker KPI di un team di vendita B2B e produci un report manageriale chiaro, sintetico e utile, scritto in italiano formale.

Il report deve essere strutturato con queste esatte sezioni:
1. RIEPILOGO ATTIVITÀ COMMERCIALE ULTIMA SETTIMANA
   - Analizza i KPI più recenti: email inviate, follow-up, risposte ricevute, chiamate, riunioni
   - Confronta con periodi precedenti se possibile, evidenzia trend

2. STATO PIPELINE CRM
   - Quante aziende sono state contattate totale e nell'ultima settimana
   - Quante sono in attesa di risposta / follow-up
   - Pattern ricorrenti nelle note/aggiornamenti (es. settori, obiezioni, interesse)

3. PROSPECT DA PRIORITIZZARE — BRASILE E ARGENTINA
   - Elenca i prospect più promettenti per BRA e ARG separatamente
   - Evidenzia quelli senza contatti recenti o con segnali positivi
   - Suggerisci azioni concrete per i top 3-5 per paese

4. ALERT — ANOMALIE O CALI DI ATTIVITÀ
   - Identifica settimane o periodi con calo significativo
   - Segnala aziende nel CRM che non vengono aggiornate da tempo
   - Evidenzia eventuali anomalie nei dati (valori mancanti, attività zero, ecc.)

Usa un tono diretto e operativo. Includi numeri specifici dove disponibili."""

    user_message = f"""Ecco i dati completi estratti dal Google Sheet aziendale. Analizzali e genera il report manageriale richiesto.

{contesto}

Genera ora il report manageriale completo seguendo le 4 sezioni indicate."""

    print("Generazione del report in corso (streaming)...")

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


def salva_report(testo):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_file = f"report_ultimo.txt"
    nome_file_ts = f"report_{timestamp}.txt"

    intestazione = (
        f"REPORT COMMERCIALE MANAGERIALE\n"
        f"Generato il: {datetime.now().strftime('%d/%m/%Y alle %H:%M:%S')}\n"
        f"Modello: {MODEL}\n"
        f"{'=' * 60}\n\n"
    )

    contenuto = intestazione + testo

    # Salva come report_ultimo.txt (sovrascrive sempre)
    with open(nome_file, "w", encoding="utf-8") as f:
        f.write(contenuto)

    # Salva anche una copia con timestamp
    with open(nome_file_ts, "w", encoding="utf-8") as f:
        f.write(contenuto)

    print(f"Report salvato come: {nome_file}")
    print(f"Copia con timestamp: {nome_file_ts}")
    return nome_file


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERRORE: variabile d'ambiente ANTHROPIC_API_KEY non impostata.")
        print("Esegui: export ANTHROPIC_API_KEY='la-tua-chiave'")
        return

    print(f"Lettura dati da {JSON_FILE}...")
    dati = carica_dati()

    for tab, contenuto in dati.items():
        print(f"  [{tab}] {len(contenuto.get('rows', []))} righe")

    print("\nCostruzione del contesto per il modello...")
    contesto = costruisci_contesto(dati)
    print(f"Contesto generato: {len(contesto)} caratteri\n")

    testo_report = genera_report(contesto)
    salva_report(testo_report)


if __name__ == "__main__":
    main()
