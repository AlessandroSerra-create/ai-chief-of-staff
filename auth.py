from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import os

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.environ.get("SECRET_KEY", "cambia-questa-chiave-in-produzione")
ALGORITHM = "HS256"
EXPIRE_HOURS = 72

class LoginRequest(BaseModel):
    email: str
    password: str

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def hash_password(password):
    return pwd_context.hash(password)

def create_token(data: dict):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=EXPIRE_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/login")
async def login(req: LoginRequest):
    import asyncpg
    DATABASE_URL = os.environ.get("DATABASE_URL")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE email = $1 AND is_active = TRUE",
            req.email.lower().strip()
        )
    finally:
        await conn.close()

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenziali non valide")

    token = create_token({
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "client_id": user["client_id"]
    })
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}}

@router.post("/set-password")
async def set_password(email: str, new_password: str):
    import asyncpg
    DATABASE_URL = os.environ.get("DATABASE_URL")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        hashed = hash_password(new_password)
        result = await conn.execute(
            "UPDATE users SET password_hash = $1 WHERE email = $2",
            hashed, email.lower().strip()
        )
    finally:
        await conn.close()
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return {"ok": True}
