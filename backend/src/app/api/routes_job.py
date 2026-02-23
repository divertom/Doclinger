"""Job endpoint: return metadata and list of artifacts for a job."""
from fastapi import APIRouter, HTTPException

from app.core.config import OUTPUTS_DIR
from app.core.models import JobMetadata, JobResponse
from app.core.storage import get_artifact_prefix, get_uploaded_file_path, list_artifacts, read_metadata, read_progress

router = APIRouter(prefix="/job", tags=["job"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    """Return metadata.json contents and list of available artifacts."""
    metadata = read_metadata(job_id)
    artifacts = list_artifacts(job_id)
    upload_path = get_uploaded_file_path(job_id)

    # Job exists if we have metadata, artifacts, or an uploaded file (before extraction)
    if metadata is None and not artifacts and upload_path is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Only treat as completed when we have real document output (not just *.metadata.json from "extracting")
    out_dir = OUTPUTS_DIR / job_id
    has_output = out_dir.exists() and any(
        f.is_file() and (f.name.endswith(".document.md") or f.name.endswith(".document_structured.json"))
        for f in out_dir.iterdir()
    )
    if has_output and (metadata is None or metadata.status not in ("completed", "failed")):
        filename = (metadata.filename if metadata else (upload_path.name if upload_path else "")) or ""
        metadata = JobMetadata(
            job_id=job_id,
            filename=filename,
            status="completed",
            artifact_prefix=get_artifact_prefix(job_id),
            artifacts=artifacts,
            stats=metadata.stats if metadata else {},
        )

    if metadata is None:
        filename = upload_path.name if upload_path else ""
        metadata = JobMetadata(
            job_id=job_id,
            filename=filename,
            status="uploaded",
            artifact_prefix=get_artifact_prefix(job_id),
            artifacts=artifacts,
        )

    # While extracting, don't expose the in-progress metadata file as a downloadable artifact
    if metadata.status == "extracting":
        artifacts = []

    return JobResponse(metadata=metadata, artifacts=artifacts)


@router.get("/{job_id}/progress")
async def get_job_progress(job_id: str) -> dict:
    """Return current extraction progress (stage name and 0-100 percent) for polling."""
    data = read_progress(job_id)
    if data is None:
        return {"stage": "pending", "percent": 0}
    return data
