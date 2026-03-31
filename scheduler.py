import subprocess
import schedule
import time
import json
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "log.txt")
JSON_FILE = os.path.join(BASE_DIR, "dati_canonici.json")
PYTHON = "python3"


def log(messaggio):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    riga = f"[{ts}] {messaggio}"
    print(riga, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(riga + "\n")


def esegui_script(nome_script):
    percorso = os.path.join(BASE_DIR, nome_script)
    log(f"Avvio {nome_script}...")
    result = subprocess.run(
        [PYTHON, percorso],
        capture_output=True,
        text=True,
        cwd=BASE_DIR,
        env={**os.environ, "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", "")},
    )
    if result.returncode == 0:
        log(f"{nome_script} completato con successo.")
    else:
        log(f"ERRORE in {nome_script}: {result.stderr.strip()[:300]}")
    return result.returncode == 0


def aggiorna_dati_e_report():
    log("=== CICLO ORARIO: aggiornamento dati e report ===")
    ok = esegui_script("leggi_sheet.py")
    if ok:
        esegui_script("genera_report.py")
    else:
        log("Aggiornamento report saltato a causa di errore in leggi_sheet.py.")
    log("=== CICLO ORARIO completato ===")


def controlla_kpi_ieri():
    log("=== CONTROLLO GIORNALIERO KPI ===")
    ieri = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
    log(f"Ricerca dati KPI per la data: {ieri}")

    if not os.path.exists(JSON_FILE):
        log("ERRORE: dati_canonici.json non trovato. Eseguo aggiornamento dati prima.")
        esegui_script("leggi_sheet.py")

    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            dati = json.load(f)
    except Exception as e:
        log(f"ERRORE lettura dati_canonici.json: {e}")
        return

    kpi_rows = dati.get("KPI", {}).get("rows", [])
    colonne_numeriche = [
        "Novos e-mails enviados",
        "Follow-ups enviados",
        "Respostas recebidas",
        "Ligações efetuadas",
        "Reuniões agendadas",
    ]

    riga_ieri = None
    for row in kpi_rows:
        data_riga = row.get("Data", "").strip()
        if data_riga == ieri:
            riga_ieri = row
            break

    if riga_ieri is None:
        log(f"ALERT: KPI non compilati ieri ({ieri}) - riga non trovata nel foglio.")
        log(">>> ALERT: KPI non compilati ieri - notifica collaboratore e CEO <<<")
        return

    valori_vuoti = all(
        not riga_ieri.get(col, "").strip() or riga_ieri.get(col, "").strip() in ("0", "")
        for col in colonne_numeriche
    )

    if valori_vuoti:
        log(f"ALERT: KPI non compilati ieri ({ieri}) - tutti i valori sono vuoti o zero.")
        log(">>> ALERT: KPI non compilati ieri - notifica collaboratore e CEO <<<")
    else:
        valori = {col: riga_ieri.get(col, "N/D") for col in colonne_numeriche}
        log(f"KPI di ieri ({ieri}) presenti e compilati: {valori}")

    log("=== CONTROLLO GIORNALIERO KPI completato ===")


def main():
    log("========================================")
    log("Scheduler avviato.")
    log("Ciclo orario: leggi_sheet.py + genera_report.py")
    log("Controllo KPI giornaliero: ogni giorno alle 09:00")
    log("========================================")

    # Primo run immediato all'avvio
    aggiorna_dati_e_report()
    controlla_kpi_ieri()

    # Pianificazione
    schedule.every(1).hours.do(aggiorna_dati_e_report)
    schedule.every().day.at("09:00").do(controlla_kpi_ieri)

    log("Scheduler in ascolto. Prossima esecuzione oraria tra 60 minuti.")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
