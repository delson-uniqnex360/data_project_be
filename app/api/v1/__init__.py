from fastapi import APIRouter


from .auth import router as auth_router
from .user import router as user_router
from .extract import router as extract_router
from .extract_v2 import router as extract_v2_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(user_router, prefix="/user", tags=["User"])
router.include_router(extract_router, prefix="/extract", tags=["Extract"])
router.include_router(extract_v2_router, prefix="/extract_v2", tags=["Extract V2"])

