from pydantic import BaseModel, EmailStr

class SignupIn(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = ""

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
