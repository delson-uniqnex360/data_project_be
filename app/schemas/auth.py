from pydantic import BaseModel, EmailStr


class AccessTokenBody(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenBody(BaseModel):
    refresh_token: str