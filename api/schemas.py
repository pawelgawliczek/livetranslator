from pydantic import BaseModel, EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    preferred_lang: str = "en"

class UserOut(BaseModel):
    id: int
    email: EmailStr
    preferred_lang: str

class WSOutbound(BaseModel):
    type: str
    segment_id: str
    revision: int
    ts_iso: str
    text: str
    lang: str
    translations: dict | None = None
    final: bool = False
