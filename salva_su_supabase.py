import requests, json, os
from datetime import datetime

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

with open("dati_canonici.json") as f:
    dati = json.load(f)

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

response = requests.post(
    f"{SUPABASE_URL}/rest/v1/dati_canonici",
    headers=headers,
    json={"cliente": "aloe-vera-pilot", "payload": dati},
    timeout=30
)

print(f"[{datetime.now()}] Supabase status: {response.status_code}")
print(response.text[:200])
