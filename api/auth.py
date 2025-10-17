import time, bcrypt, jwt, httpx, base64, orjson
from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as st
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import User
from .settings import settings, JWT_SECRET, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from .db import get_session

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginReq(BaseModel):
    email: EmailStr
    password: str

class GoogleTokenReq(BaseModel):
    id_token: str  # from Google JS client

def mkjwt(sub: str, email: str) -> str:
    now = int(time.time())
    payload = {"sub": sub, "email": email, "iat": now, "exp": now + 3600 * 24 * 7}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

@router.post("/register")
def register(req: LoginReq, db: Session = Depends(get_session)):
    if db.scalar(select(User).where(User.email == req.email)):
        raise HTTPException(st.HTTP_409_CONFLICT, "exists")
    ph = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    u = User(email=req.email, password_hash=ph)
    db.add(u); db.commit(); db.refresh(u)
    return {"token": mkjwt(str(u.id), u.email)}

@router.post("/login")
def login(req: LoginReq, db: Session = Depends(get_session)):
    u = db.scalar(select(User).where(User.email == req.email))
    if not u or not u.password_hash or not bcrypt.checkpw(req.password.encode(), u.password_hash.encode()):
        raise HTTPException(st.HTTP_401_UNAUTHORIZED, "invalid")
    return {"token": mkjwt(str(u.id), u.email)}

@router.post("/google")
def google(req: GoogleTokenReq, db: Session = Depends(get_session)):
    # Minimal verification using Google tokeninfo
    r = httpx.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": req.id_token}, timeout=10)
    if r.status_code != 200: raise HTTPException(401, "bad_token")
    data = r.json()
    if data.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(401, "aud_mismatch")
    email = data.get("email")
    sub = data.get("sub")
    u = db.scalar(select(User).where((User.google_sub == sub) | (User.email == email)))
    if not u:
        u = User(email=email, google_sub=sub)
        db.add(u); db.commit(); db.refresh(u)
    return {"token": mkjwt(str(u.id), u.email)}
