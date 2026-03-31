import json
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

CREDENTIALS_FILE = "tidal-cipher-433109-v5-db7b245cc5ba.json"
SHEET_ID = "1XjsUv3TD1sF5upiwX29rbmIcueAvvT_TFQBi2Yq4e6g"

TAB_COLUMNS = {
    "KPI": ["Data", "Novos e-mails enviados", "Follow-ups enviados", "Respostas recebidas", "Ligações efetuadas", "Reuniões agendadas"],
    "CRM": ["Nome da empresa", "Responsável", "Número", "E-mail", "Data do contato", "Atualizações"],
    "BRA - Novos a contactar": None,  # legge intestazioni dinamicamente
    "ARG - Novos a contactar": None,
}


def normalize_sheet(worksheet, expected_columns):
    all_values = worksheet.get_all_values()
    if not all_values:
        return [], []

    headers = all_values[0]
    data_rows = all_values[1:]

    # Se le colonne attese sono specificate, usale come riferimento
    if expected_columns:
        # Mappa header trovati -> indice colonna
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


def main():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)

    canonical = {}
    row_counts = {}

    for tab_name, expected_columns in TAB_COLUMNS.items():
        try:
            worksheet = spreadsheet.worksheet(tab_name)
            headers, rows = normalize_sheet(worksheet, expected_columns)
            canonical[tab_name] = {
                "headers": headers,
                "rows": rows,
            }
            row_counts[tab_name] = len(rows)
            print(f"  [{tab_name}] {len(rows)} righe lette")
        except gspread.exceptions.WorksheetNotFound:
            print(f"  [{tab_name}] FOGLIO NON TROVATO")
            canonical[tab_name] = {"headers": [], "rows": []}
            row_counts[tab_name] = 0

    with open("dati_canonici.json", "w", encoding="utf-8") as f:
        json.dump(canonical, f, ensure_ascii=False, indent=2)

    print("\nFile salvato: dati_canonici.json")
    return row_counts


if __name__ == "__main__":
    main()
