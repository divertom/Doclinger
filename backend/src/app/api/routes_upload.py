"""Upload endpoint: accept documents (PDF, DOCX, PPTX, XLSX, HTML, images, etc.), store under data/uploads/{job_id}/, return job_id."""
import errno
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.models import UploadResponse
from app.core.storage import job_upload_dir
from app.core.utils import generate_job_id, is_allowed_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

MIN_FREE_BYTES = 15 * 1024 * 1024  # 15 MB minimum (for a typical upload + headroom)

DISK_FULL_MESSAGE = (
    "Server out of disk space. Use **Clean storage** in the sidebar to remove old uploads and outputs. "
    "If you already did that, the full disk is likely **Docker's own disk** (C: or WSL), not the project folder: "
    "run `docker system prune -a`, or in Docker Desktop move **Settings → Resources → Disk image location** to a drive with more space (e.g. E:)."
)


@router.post("", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    """Accept a document file (PDF, DOCX, PPTX, XLSX, HTML, images, etc.), store it, return job_id."""
    path = Path(file.filename or "document")
    if not is_allowed_file(path):
        raise HTTPException(
            status_code=400,
            detail="File type not allowed. Allowed: PDF, DOCX, PPTX, XLSX, HTML, MD, CSV, TXT, PNG, TIFF, JPG.",
        )

    job_id = generate_job_id()
    upload_dir = job_upload_dir(job_id)
    dest = upload_dir / (path.name or "document.pdf")

    # Soft check: only warn if reported free is very low (container may report Docker disk, not the mount)
    try:
        usage = shutil.disk_usage(upload_dir)
        if usage.free < MIN_FREE_BYTES:
            free_mb = usage.free // (1024 * 1024)
            raise HTTPException(
                status_code=507,
                detail=(
                    f"Reported free space is only {free_mb} MB. " + DISK_FULL_MESSAGE
                ),
            )
    except HTTPException:
        raise
    except OSError as e:
        if e.errno == errno.ENOSPC:
            raise HTTPException(status_code=507, detail=DISK_FULL_MESSAGE) from e
        raise HTTPException(status_code=500, detail="Failed to check disk space") from e

    try:
        contents = await file.read()
        dest.write_bytes(contents)
    except OSError as e:
        if e.errno == errno.ENOSPC:
            logger.exception("Upload failed (no space) for job %s", job_id)
            raise HTTPException(status_code=507, detail=DISK_FULL_MESSAGE) from e
        logger.exception("Upload failed for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Failed to save upload") from e
    except Exception as e:
        logger.exception("Upload failed for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Failed to save upload") from e

    return UploadResponse(job_id=job_id)
