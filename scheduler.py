import subprocess
import schedule
import time
import json
import os
import requests
from datetime import datetime, timedelta

SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_URL = "https://xnduljfrfmyaxyjhrsfk.supabase.co"
GENERA_REPORT_URL = f"{SUPABASE_URL}/functions/v1/genera-report"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "log.txt")
PYTHON = "python3"

COMMERCIALI = ["pamela", "dante"]

COLONNE_NUMERICHE = [
    "Novos e-mails enviados",
    "Follow-ups enviados",
    "Respostas recebidas",
    "Ligações efetuadas",
    "Reuniões agendadas",
]


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


def chiama_genera_report():
    try:
        log("Chiamata Edge Function genera-report...")
        res = requests.post(
            GENERA_REPORT_URL,
            headers={
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                "Content-Type": "application/json",
            },
            json={},
            timeout=60,
        )
        log(f"genera-report: status {res.status_code}")
    except Exception as e:
        log(f"ERRORE genera-report: {e}")


def chiama_report_finale():
    for commerciale in COMMERCIALI:
        cliente_id = f"aloe-vera-pilot-{commerciale}"
        try:
            log(f"Chiamata Edge Function report-finale [{commerciale}]...")
            res = requests.post(
                f"{SUPABASE_URL}/functions/v1/report-finale",
                headers={
                    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                    "Content-Type": "application/json",
                },
                json={"cliente": cliente_id},
                timeout=120,
            )
            log(f"report-finale [{commerciale}]: status {res.status_code}")
        except Exception as e:
            log(f"ERRORE report-finale [{commerciale}]: {e}")


def aggiorna_dati_e_report():
    log("=== CICLO REPORT: aggiornamento dati e report ===")
    ok = esegui_script("leggi_sheet.py")
    esegui_script("leggi_gmail.py")
    if ok:
        chiama_genera_report()
        time.sleep(600)
        chiama_report_finale()
    else:
        log("genera-report saltato a causa di errore in leggi_sheet.py.")
    log("=== CICLO REPORT completato ===")


def leggi_kpi_da_supabase(commerciale):
    try:
        cliente_id = f"aloe-vera-pilot-{commerciale}"
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/canonical_data",
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            },
            params={
                "cliente": f"eq.{cliente_id}",
                "fonte": "is.null",
                "order": "creato_at.desc",
                "limit": "1",
                "select": "payload",
            },
            timeout=15,
        )
        if res.status_code == 200:
            rows = res.json()
            if rows:
                return rows[0].get("payload", {}).get("KPI", {}).get("rows", [])
    except Exception as e:
        log(f"ERRORE lettura Supabase [{commerciale}]: {e}")
    return []


def controlla_kpi_ieri():
    log("=== CONTROLLO GIORNALIERO KPI ===")
    ieri = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
    log(f"Data controllata: {ieri}")

    for commerciale in COMMERCIALI:
        kpi_rows = leggi_kpi_da_supabase(commerciale)

        if not kpi_rows:
            log(f"ALERT [{commerciale}]: nessun dato KPI trovato su Supabase.")
            continue

        riga_ieri = next(
            (r for r in kpi_rows if r.get("Data", "").strip() == ieri),
            None
        )

        if riga_ieri is None:
            log(f"ALERT [{commerciale}]: KPI non compilati ieri ({ieri}) - riga non trovata.")
            log(f">>> ALERT: notifica {commerciale} e CEO <<<")
            continue

        valori_vuoti = all(
            not riga_ieri.get(col, "").strip() or riga_ieri.get(col, "").strip() in ("0", "")
            for col in COLONNE_NUMERICHE
        )

        if valori_vuoti:
            log(f"ALERT [{commerciale}]: KPI di ieri ({ieri}) tutti vuoti o zero.")
            log(f">>> ALERT: notifica {commerciale} e CEO <<<")
        else:
            valori = {col: riga_ieri.get(col, "N/D") for col in COLONNE_NUMERICHE}
            log(f"OK [{commerciale}]: KPI di ieri ({ieri}) compilati: {valori}")

    log("=== CONTROLLO GIORNALIERO KPI completato ===")


def main():
    log("========================================")
    log("Scheduler avviato.")
    log("Report giornalieri: 08:00, 12:00, 14:00, 19:00")
    log("Controllo KPI giornaliero: ogni giorno alle 09:00")
    log("========================================")

    aggiorna_dati_e_report()
    controlla_kpi_ieri()

    schedule.every().day.at("08:00").do(aggiorna_dati_e_report)
    schedule.every().day.at("12:00").do(aggiorna_dati_e_report)
    schedule.every().day.at("14:00").do(aggiorna_dati_e_report)
    schedule.every().day.at("19:00").do(aggiorna_dati_e_report)
    schedule.every().day.at("09:00").do(controlla_kpi_ieri)

    log("Scheduler in ascolto.")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
