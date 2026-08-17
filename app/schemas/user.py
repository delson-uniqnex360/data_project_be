from pydantic import BaseModel, EmailStr


class UserCreatePayload(BaseModel):
    email: EmailStr
    password: str