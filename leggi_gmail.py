import os
import json
import base64
import re
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_FILE = 'gmail_credentials.json'
TOKEN_FILE = 'gmail_token.json'

CASELLE = [
    'serra@sorellebrasil.com',
]

def get_service(email):
    token_file = f'gmail_token_{email.replace("@","_").replace(".","_")}.json'
    if not os.path.exists(token_file) and os.environ.get("GMAIL_TOKEN_SERRA"):
        with open(token_file, 'w') as f:
            f.write(os.environ["GMAIL_TOKEN_SERRA"])
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, 'w') as f:
            f.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_header(headers, name):
    for h in headers:
        if h['name'].lower() == name.lower():
            return h['value']
    return ''

def extract_text(payload):
    text = ''
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain' and 'data' in part.get('body', {}):
                text += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
    elif 'body' in payload and 'data' in payload['body']:
        text += base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
    return text[:500]

def leggi_casella(email, giorni=7):
    service = get_service(email)
    dopo = (datetime.now() - timedelta(days=giorni)).strftime('%Y/%m/%d')
    results = service.users().messages().list(
        userId='me', q=f'after:{dopo}', maxResults=50
    ).execute()
    messages = results.get('messages', [])
    threads = {}
    for msg in messages:
        m = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        headers = m['payload'].get('headers', [])
        thread_id = m['threadId']
        mittente = get_header(headers, 'From')
        destinatario = get_header(headers, 'To')
        oggetto = get_header(headers, 'Subject')
        data = get_header(headers, 'Date')
        testo = extract_text(m['payload'])
        if thread_id not in threads:
            threads[thread_id] = {
                'oggetto': oggetto,
                'data': data,
                'partecipanti': set(),
                'anteprima': testo[:200],
                'tipo': 'interno' if all(
                    email.split('@')[1] in p for p in [mittente, destinatario] if p
                ) else 'esterno'
            }
        threads[thread_id]['partecipanti'].add(mittente)
        threads[thread_id]['partecipanti'].add(destinatario)
    result = []
    for tid, t in threads.items():
        result.append({
            'oggetto': t['oggetto'],
            'data': t['data'],
            'partecipanti': list(t['partecipanti']),
            'anteprima': t['anteprima'],
            'tipo': t['tipo']
        })
    return result

def main():
    canonical = {}
    for email in CASELLE:
        print(f'Lettura {email}...')
        try:
            threads = leggi_casella(email)
            canonical[email] = threads
            print(f'  {len(threads)} thread trovati')
        except Exception as e:
            print(f'  ERRORE: {e}')
            canonical[email] = []
    with open('dati_gmail.json', 'w', encoding='utf-8') as f:
        json.dump(canonical, f, ensure_ascii=False, indent=2)
    print('Salvato: dati_gmail.json')

    import requests as req
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_key:
        try:
            # 1. Leggi il payload esistente
            get_resp = req.get(
                "https://xnduljfrfmyaxyjhrsfk.supabase.co/rest/v1/canonical_data?cliente=eq.aloe-vera-pilot&select=payload",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                },
                timeout=15,
            )
            existing_payload = {}
            if get_resp.status_code == 200 and get_resp.json():
                existing_payload = get_resp.json()[0].get("payload", {}) or {}

            # 2. Merge: aggiorna solo il campo gmail
            existing_payload["gmail"] = canonical

            # 3. PATCH (upsert) sul record esistente
            response = req.patch(
                "https://xnduljfrfmyaxyjhrsfk.supabase.co/rest/v1/canonical_data?cliente=eq.aloe-vera-pilot",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json={"payload": existing_payload},
                timeout=15,
            )
            print(f"Supabase gmail: {response.status_code}")
        except Exception as e:
            print(f"ERRORE Supabase gmail: {e}")

    return canonical

if __name__ == '__main__':
    main()
