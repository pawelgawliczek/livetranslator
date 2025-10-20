from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from passlib.hash import bcrypt_sha256 as bcrypt
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from .db import SessionLocal
from .models import User
from .schemas import SignupIn, TokenOut
from .settings import JWT_SECRET, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI

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

@router.get("/google/login")
def google_login():
    """Redirect to Google OAuth"""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(500, "Google OAuth not configured")
    
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=openid email profile&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    return RedirectResponse(auth_url)

@router.get("/google/callback")
def google_callback(code: str, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(500, "Google OAuth not configured")
    
    try:
        # Exchange code for tokens
        import httpx
        token_response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code"
            }
        )
        
        if token_response.status_code != 200:
            raise HTTPException(400, "Failed to exchange code for tokens")
        
        tokens = token_response.json()
        google_id_token = tokens.get("id_token")
        
        # Verify and decode the ID token
        idinfo = id_token.verify_oauth2_token(
            google_id_token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        
        google_user_id = idinfo.get("sub")
        email = idinfo.get("email")
        name = idinfo.get("name", "")
        
        if not google_user_id or not email:
            raise HTTPException(400, "Invalid Google token")
        
        # Find or create user
        user = db.scalar(select(User).where(User.google_id == google_user_id))
        
        if not user:
            # Check if email exists (user with password login)
            user = db.scalar(select(User).where(User.email == email))
            if user:
                # Link Google account to existing user
                user.google_id = google_user_id
                db.commit()
            else:
                # Create new user
                user = User(
                    email=email,
                    google_id=google_user_id,
                    display_name=name,
                    preferred_lang="en",
                    password_hash=None
                )
                db.add(user)
                db.commit()
        
        # Generate JWT token
        token = _issue(user)
        
        # Redirect to frontend with token
        return RedirectResponse(f"/login?token={token.access_token}")
        
    except Exception as e:
        print(f"[Google OAuth] Error: {e}")
        raise HTTPException(400, f"Google authentication failed: {str(e)}")

def _issue(u: User) -> TokenOut:
    claims = {"sub": str(u.id), "email": u.email, "exp": datetime.utcnow() + timedelta(hours=12)}
    return TokenOut(access_token=jwt.encode(claims, JWT_SECRET, algorithm=ALGO))
