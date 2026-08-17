from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import User
from app.schemas import UserCreatePayload
from app.core.security import hash_password

router = APIRouter()


@router.post("/create/", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreatePayload,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user."""

    try:
        user = User(
            email=payload.email,
            hashed_password=hash_password(payload.password),
        )

        db.add(user)

        await db.commit()
        await db.refresh(user)

    except IntegrityError:
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )

    return {
        "id": user.id,
        "email": user.email,
    }
