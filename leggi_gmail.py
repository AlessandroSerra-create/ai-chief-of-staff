import os
import json
import base64
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
DOMINIO_INTERNO = 'sorellebrasil.com'

CASELLE = [
    'serra@sorellebrasil.com',
    'producao@sorellebrasil.com',
    'incardona@sorellebrasil.com',
    'dscottini@sorellebrasil.com',
    'vendas@sorellebrasil.com',
    'gilvolpato@sorellebrasil.com',
    'j.werlich@sorellebrasil.com',
    'qualidade@sorellebrasil.com',
    'pcp@sorellebrasil.com',
    'lucac@sorellebrasil.com',
    'financeiro@sorellebrasil.com',
    'laboratorio@sorellebrasil.com',
    'sorelle@sorellebrasil.com',
    'u.garanhani@sorellebrasil.com',
    'valerio@sorellebrasil.com',
    'compras@sorellebrasil.com',
]

SUPABASE_URL = "https://xnduljfrfmyaxyjhrsfk.supabase.co"


def sanitize_email(email):
    return email.replace("@", "_").replace(".", "_")


def get_service(email):
    creds_json = os.environ.get("GMAIL_CREDENTIALS_JSON")
    if not creds_json:
        raise RuntimeError("GMAIL_CREDENTIALS_JSON non impostata")
    info = json.loads(creds_json)
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    delegated_credentials = credentials.with_subject(email)
    return build('gmail', 'v1', credentials=delegated_credentials)


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


def is_esterno(indirizzo):
    if not indirizzo:
        return False
    return DOMINIO_INTERNO not in indirizzo.lower()


def parse_email(msg_data):
    headers = msg_data['payload'].get('headers', [])
    return {
        'mittente': get_header(headers, 'From'),
        'destinatario': get_header(headers, 'To'),
        'oggetto': get_header(headers, 'Subject'),
        'anteprima': extract_text(msg_data['payload'])[:200],
        'data': get_header(headers, 'Date'),
    }


def leggi_casella(email, giorni=2):
    service = get_service(email)
    dopo = (datetime.now() - timedelta(days=giorni)).strftime('%Y/%m/%d')

    # Email ricevute da esterni
    ricevute = []
    results = service.users().messages().list(
        userId='me', q=f'after:{dopo} in:inbox', maxResults=40
    ).execute()
    for msg in results.get('messages', []):
        if len(ricevute) >= 20:
            break
        m = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        parsed = parse_email(m)
        if is_esterno(parsed['mittente']):
            ricevute.append(parsed)

    # Email inviate a esterni
    inviate = []
    results = service.users().messages().list(
        userId='me', q=f'after:{dopo} in:sent', maxResults=40
    ).execute()
    for msg in results.get('messages', []):
        if len(inviate) >= 20:
            break
        m = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        parsed = parse_email(m)
        if is_esterno(parsed['destinatario']):
            inviate.append(parsed)

    return {'email_ricevute': ricevute, 'email_inviate': inviate}


def salva_su_supabase(email, payload_casella, supabase_key):
    import requests as req
    fonte = f"gmail_{sanitize_email(email)}"

    # Prova PATCH prima (aggiorna record esistente)
    response = req.patch(
        f"{SUPABASE_URL}/rest/v1/canonical_data?cliente=eq.aloe-vera-pilot&fonte=eq.{fonte}",
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json={"payload": payload_casella},
        timeout=15,
    )

    # Se PATCH non ha aggiornato niente (nessun record esistente), fai POST
    if response.status_code == 200 and response.json() == []:
        response = req.post(
            f"{SUPABASE_URL}/rest/v1/canonical_data",
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json={
                "cliente": "aloe-vera-pilot",
                "fonte": fonte,
                "payload": payload_casella,
            },
            timeout=15,
        )

    print(f"  Supabase {fonte}: {response.status_code}")


def main():
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    for email in CASELLE:
        print(f'Lettura {email}...')
        try:
            risultato = leggi_casella(email)
            print(f'  {len(risultato["email_ricevute"])} ricevute, {len(risultato["email_inviate"])} inviate')

            if supabase_key:
                salva_su_supabase(email, risultato, supabase_key)
        except Exception as e:
            print(f'  ERRORE: {e}')

    print('Completato.')


if __name__ == '__main__':
    main()
