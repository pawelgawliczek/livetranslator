from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from passlib.hash import bcrypt_sha256 as bcrypt
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import User
from .schemas import SignupIn, TokenOut
from .settings import JWT_SECRET, settings

ALGO = "HS256"
router = APIRouter(prefix="/auth", tags=["auth"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.post("/signup", response_model=TokenOut)
def signup(p: SignupIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == p.email)):
        raise HTTPException(400, "email_exists")
    u = User(email=p.email, password_hash=bcrypt.hash(p.password), display_name=p.display_name or "", preferred_lang="en")
    db.add(u); db.commit()
    return _issue(u)

@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == form.username))
    if not u or not bcrypt.verify(form.password, u.password_hash):
        raise HTTPException(401, "invalid_credentials")
    return _issue(u)

def _issue(u: User) -> TokenOut:
    claims = {"sub": str(u.id), "email": u.email, "exp": datetime.utcnow() + timedelta(hours=12)}
    return TokenOut(access_token=jwt.encode(claims, JWT_SECRET, algorithm=ALGO))
