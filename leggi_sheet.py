import json
import os
import requests
import gspread
from datetime import date, datetime
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

CREDENTIALS_FILE = os.environ.get(
    "GOOGLE_CREDENTIALS_FILE", "tidal-cipher-433109-v5-db7b245cc5ba.json"
)

COMMERCIALI = {
    "pamela": "1XjsUv3TD1sF5upiwX29rbmIcueAvvT_TFQBi2Yq4e6g",
    "dante":  "1AjWpKL8ptiiTS9ERSlfHLNtJT9bhTGFF3S1lYs2vUH8",
}

TAB_COLUMNS = {
    "KPI": ["Data", "Novos e-mails enviados", "Follow-ups enviados", "Respostas recebidas", "Ligações efetuadas", "Reuniões agendadas"],
    "CRM": ["Nome da empresa", "Responsável", "Número", "E-mail", "Data do contato", "Atualizações"],
    "BRA - Novos a contactar": None,
    "ARG - Novos a contactar": None,
}

KPI_NUMERIC_COLS = [
    "Novos e-mails enviados",
    "Follow-ups enviados",
    "Respostas recebidas",
    "Ligações efetuadas",
    "Reuniões agendadas",
]


def get_credentials():
    credentials_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if credentials_json:
        info = json.loads(credentials_json)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    return Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)


def normalize_sheet(worksheet, expected_columns):
    all_values = worksheet.get_all_values()
    if not all_values:
        return [], []

    headers = all_values[0]
    data_rows = all_values[1:]

    if expected_columns:
        header_index = {h: i for i, h in enumerate(headers)}
        rows = []
        for row in data_rows:
            record = {}
            for col in expected_columns:
                idx = header_index.get(col)
                value = row[idx].strip() if idx is not None and idx < len(row) else ""
                record[col] = value
            rows.append(record)
    else:
        rows = []
        for row in data_rows:
            record = {}
            for i, header in enumerate(headers):
                value = row[i].strip() if i < len(row) else ""
                record[header] = value
            rows.append(record)

    return headers, rows


def processa_commerciale(client, nome, sheet_id):
    print(f"\n--- Elaboro {nome} ({sheet_id}) ---")
    spreadsheet = client.open_by_key(sheet_id)
    canonical = {}

    for tab_name, expected_columns in TAB_COLUMNS.items():
        try:
            worksheet = spreadsheet.worksheet(tab_name)
            headers, rows = normalize_sheet(worksheet, expected_columns)

            if tab_name == "KPI":
                filtered = [
                    r for r in rows
                    if any(r.get(col, "").strip() not in ("", "0") for col in KPI_NUMERIC_COLS)
                ]
                oggi = date.today()
                non_future = []
                for r in filtered:
                    d = r.get("Data", "").strip()
                    if not d:
                        continue
                    try:
                        parsed = datetime.strptime(d, "%d/%m/%Y").date()
                    except ValueError:
                        continue
                    if parsed <= oggi:
                        non_future.append(r)
                print(f"  [KPI] {len(non_future)} righe dopo filtro data <= oggi")
                rows = non_future[-14:]
                print(f"  [KPI] {len(rows)} righe reali (dopo filtro su colonne B-F)")

                ultima_data_kpi = ""
                for r in reversed(rows):
                    d = r.get("Data", "").strip()
                    if d:
                        ultima_data_kpi = d
                        break
                canonical["ultima_data_kpi"] = ultima_data_kpi
                canonical["data_oggi"] = date.today().strftime("%d/%m/%Y")
            else:
                print(f"  [{tab_name}] {len(rows)} righe lette")

            canonical[tab_name] = {
                "headers": headers,
                "rows": rows,
            }

        except gspread.exceptions.WorksheetNotFound:
            print(f"  [{tab_name}] FOGLIO NON TROVATO")
            canonical[tab_name] = {"headers": [], "rows": []}

    return canonical


def salva_su_supabase(supabase_key, cliente_id, canonical):
    try:
        response = requests.post(
            "https://xnduljfrfmyaxyjhrsfk.supabase.co/rest/v1/canonical_data",
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
            },
            json={"cliente": cliente_id, "payload": canonical},
            timeout=15,
        )
        print(f"  Supabase [{cliente_id}]: {response.status_code}")
    except Exception as e:
        print(f"  ERRORE salvataggio Supabase [{cliente_id}]: {e}")


def main():
    creds = get_credentials()
    client = gspread.authorize(creds)
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    for nome, sheet_id in COMMERCIALI.items():
        canonical = processa_commerciale(client, nome, sheet_id)
        salva_su_supabase(supabase_key, f"aloe-vera-pilot-{nome}", canonical)

    print("\nFatto.")


if __name__ == "__main__":
    main()
