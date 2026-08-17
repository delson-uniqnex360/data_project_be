from typing import Literal, Optional
from pydantic import BaseModel

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()


class ExtractResponse(BaseModel):
    status: Literal["success", "warning", "error", "file"]
    message: str
    file: Optional[str] = None  # Base64 string representing the .xlsx file


@router.post("/")
def extract_data():
    return StreamingResponse(
        media_type="application/x-ndjson",
    )
