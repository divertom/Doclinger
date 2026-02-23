"""Storage management: clean uploads and outputs to free disk space."""
from fastapi import APIRouter

from app.core.storage import clean_storage

router = APIRouter(prefix="/storage", tags=["storage"])


@router.post("/clean")
def storage_clean() -> dict:
    """Delete all uploaded files and extraction outputs. Use to free disk space."""
    return clean_storage()
