"""File storage for uploads and extraction outputs."""
import json
import logging
import shutil
from pathlib import Path

from .config import UPLOADS_DIR, OUTPUTS_DIR
from .models import JobMetadata
from .utils import sanitize_stem

logger = logging.getLogger(__name__)


def ensure_dirs() -> None:
    """Ensure upload and output directories exist."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def job_upload_dir(job_id: str) -> Path:
    """Path to job's upload directory: data/uploads/{job_id}/"""
    ensure_dirs()
    d = UPLOADS_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def job_output_dir(job_id: str) -> Path:
    """Path to job's output directory: data/outputs/{job_id}/"""
    ensure_dirs()
    d = OUTPUTS_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_uploaded_file_path(job_id: str) -> Path | None:
    """Return path to the single uploaded file in job's upload dir, or None."""
    ud = UPLOADS_DIR / job_id
    if not ud.exists():
        return None
    for f in ud.iterdir():
        if f.is_file():
            return f
    return None


def get_artifact_prefix(job_id: str) -> str:
    """Return artifact prefix (sanitized stem from uploaded filename), or 'document' if unknown."""
    p = get_uploaded_file_path(job_id)
    if p is None:
        return "document"
    return sanitize_stem(p.name)


PROGRESS_FILENAME = "progress.json"
PROCESSING_REQUEST_FILENAME = "processing_request.json"


def list_artifacts(job_id: str) -> list[str]:
    """List artifact filenames in job's output directory (excludes progress.json and processing_request.json)."""
    od = OUTPUTS_DIR / job_id
    if not od.exists():
        return []
    skip = {PROGRESS_FILENAME, PROCESSING_REQUEST_FILENAME}
    return [f.name for f in od.iterdir() if f.is_file() and f.name not in skip]


def write_progress(job_id: str, stage: str, percent: int) -> None:
    """Write extraction progress for polling (stage name and 0-100 percent)."""
    path = job_output_dir(job_id) / PROGRESS_FILENAME
    path.write_text(json.dumps({"stage": stage, "percent": percent}), encoding="utf-8")


def read_progress(job_id: str) -> dict | None:
    """Read current extraction progress, or None if no progress file."""
    path = OUTPUTS_DIR / job_id / PROGRESS_FILENAME
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_metadata(job_id: str) -> JobMetadata | None:
    """Read metadata for a job (finds *.metadata.json, or legacy *.meta.json / metadata.json)."""
    od = job_output_dir(job_id)
    if not od.exists():
        return None
    path = None
    for f in od.iterdir():
        if f.is_file() and (
            f.name.endswith(".metadata.json")
            or f.name.endswith(".meta.json")
            or f.name == "metadata.json"
        ):
            path = f
            break
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return JobMetadata.model_validate(data)
    except Exception as e:
        logger.exception("Failed to read metadata for %s: %s", job_id, e)
        return None


def write_metadata(job_id: str, metadata: JobMetadata, artifact_prefix: str | None = None) -> Path:
    """Write metadata for a job to <prefix>.metadata.json."""
    prefix = artifact_prefix if artifact_prefix is not None else get_artifact_prefix(job_id)
    path = job_output_dir(job_id) / f"{prefix}.metadata.json"
    path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
    return path


def clean_storage() -> dict:
    """Remove all uploads and extraction outputs (frees disk space). Returns counts removed."""
    removed_uploads = 0
    removed_outputs = 0
    for d in (UPLOADS_DIR, OUTPUTS_DIR):
        if not d.exists():
            continue
        for item in d.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
                if d == UPLOADS_DIR:
                    removed_uploads += 1
                else:
                    removed_outputs += 1
            except OSError as e:
                logger.warning("Could not remove %s: %s", item, e)
    ensure_dirs()
    return {"removed_uploads": removed_uploads, "removed_outputs": removed_outputs}


def get_artifact_path(job_id: str, filename: str) -> Path | None:
    """Return path to an artifact file if it exists and is under job output dir. Prevents path traversal."""
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return None
    od = OUTPUTS_DIR / job_id
    if not od.exists():
        return None
    path = (od / filename).resolve()
    if not str(path).startswith(str(od.resolve())):
        return None
    return path if path.is_file() else None
