import json
import os
from datetime import datetime
from supabase import create_client, Client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(BASE_DIR, "dati_canonici.json")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

with open(JSON_FILE, "r", encoding="utf-8") as f:
    dati = json.load(f)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

response = supabase.table("dati_canonici").insert({"cliente": "aloe-vera-pilot", "payload": dati}).execute()

ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f"[{ts}] Dati salvati su Supabase (cliente=aloe-vera-pilot).")
