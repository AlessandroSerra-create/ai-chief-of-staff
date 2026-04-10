from fastapi import FastAPI, Request
import logging

from auth import router as auth_router

app = FastAPI(title="AI Chief of Staff API")
app.include_router(auth_router)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/webhook/webmais")
async def webhook_webmais(request: Request):
    body = await request.body()
    headers = dict(request.headers)
    print(f"WEBMAIS WEBHOOK - Headers: {headers}", flush=True)
    print(f"WEBMAIS WEBHOOK - Body: {body[:2000]}", flush=True)
    return {"status": "ok"}
