"""Artifact endpoint: serve stored artifact files."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.storage import get_artifact_path

router = APIRouter(prefix="/artifact", tags=["artifact"])


@router.get("/{job_id}/{filename}")
async def get_artifact(job_id: str, filename: str) -> FileResponse:
    """Return the contents of a stored artifact file (download)."""
    path = get_artifact_path(job_id, filename)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(
        path,
        filename=Path(filename).name,
        content_disposition_type="attachment",
    )
