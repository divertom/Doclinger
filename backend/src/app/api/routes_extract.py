"""Extract endpoint: run Docling in background; return 202 so client can poll. Extraction continues if client disconnects."""
import json
import logging
import os
import subprocess
import sys
import threading

from fastapi import APIRouter, Body, HTTPException

from app.core.config import DATA_ROOT
from app.core.docling_runner import try_placeholder_fallback
from app.core.models import ExtractRequestBody, ExtractionSummary, JobMetadata, ProcessingConfig
from app.core.storage import (
    get_uploaded_file_path,
    job_output_dir,
    list_artifacts,
    read_metadata,
    write_metadata,
)
from app.core.utils import sanitize_stem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extract", tags=["extract"])

# Jobs currently extracting (so we don't start twice)
_extracting: set[str] = set()
_extracting_lock = threading.Lock()


def _run_extract_subprocess(job_id: str) -> int:
    """Run extraction in a subprocess. Returns exit_code."""
    env = os.environ.copy()
    env["DATA_ROOT"] = str(DATA_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "app.core.run_extract_job", job_id],
        env=env,
        timeout=1800,
        cwd="/app" if os.path.exists("/app") else None,
        capture_output=False,
    )
    return result.returncode


def _run_extraction_background(job_id: str, input_path, output_dir, prefix: str) -> None:
    """Run extraction and update metadata when done. Runs in a thread; survives client disconnect."""
    try:
        exit_code = _run_extract_subprocess(job_id)
    except subprocess.TimeoutExpired:
        logger.exception("Extraction timed out for job %s", job_id)
        if try_placeholder_fallback(input_path, output_dir, artifact_prefix=prefix):
            artifacts = list_artifacts(job_id)
            write_metadata(
                job_id,
                JobMetadata(
                    job_id=job_id,
                    filename=input_path.name,
                    status="completed",
                    artifact_prefix=prefix,
                    artifacts=artifacts,
                    stats={"fallback": True, "num_chunks": 0},
                ),
                artifact_prefix=prefix,
            )
        else:
            write_metadata(
                job_id,
                JobMetadata(
                    job_id=job_id,
                    filename=input_path.name,
                    status="failed",
                    artifact_prefix=prefix,
                    artifacts=list_artifacts(job_id),
                    stats={},
                    error="Extraction timed out",
                ),
                artifact_prefix=prefix,
            )
        with _extracting_lock:
            _extracting.discard(job_id)
        return
    except Exception as e:
        logger.exception("Extraction failed for job %s: %s", job_id, e)
        if try_placeholder_fallback(input_path, output_dir, artifact_prefix=prefix):
            artifacts = list_artifacts(job_id)
            write_metadata(
                job_id,
                JobMetadata(
                    job_id=job_id,
                    filename=input_path.name,
                    status="completed",
                    artifact_prefix=prefix,
                    artifacts=artifacts,
                    stats={"fallback": True, "num_chunks": 0},
                ),
                artifact_prefix=prefix,
            )
        else:
            write_metadata(
                job_id,
                JobMetadata(
                    job_id=job_id,
                    filename=input_path.name,
                    status="failed",
                    artifact_prefix=prefix,
                    artifacts=list_artifacts(job_id),
                    stats={},
                    error=str(e),
                ),
                artifact_prefix=prefix,
            )
        with _extracting_lock:
            _extracting.discard(job_id)
        return

    artifacts = list_artifacts(job_id)
    written = read_metadata(job_id)
    has_output = (
        (output_dir.exists() and any(
            f.is_file() and (f.name.endswith(".document.md") or f.name.endswith(".document_structured.json"))
            for f in output_dir.iterdir()
        ))
        or written is not None
    )

    if has_output:
        meta = written or JobMetadata(
            job_id=job_id,
            filename=input_path.name,
            status="completed",
            artifact_prefix=prefix,
            artifacts=artifacts,
            stats={},
        )
        if written is None:
            write_metadata(job_id, meta, artifact_prefix=prefix)
    else:
        write_metadata(
            job_id,
            JobMetadata(
                job_id=job_id,
                filename=input_path.name,
                status="failed",
                artifact_prefix=prefix,
                artifacts=artifacts,
                stats={},
                error="Extraction failed. Check docker logs Docling for details.",
            ),
            artifact_prefix=prefix,
        )
    with _extracting_lock:
        _extracting.discard(job_id)


@router.post("/{job_id}", response_model=ExtractionSummary, status_code=202)
async def extract_job(job_id: str, body: ExtractRequestBody | None = Body(None)) -> ExtractionSummary:
    """Start Docling extraction in background; return 202 immediately. Client polls GET /job and /job/progress."""
    input_path = get_uploaded_file_path(job_id)
    if not input_path or not input_path.exists():
        raise HTTPException(status_code=404, detail="Upload not found for this job")

    output_dir = job_output_dir(job_id)
    prefix = sanitize_stem(input_path.name)

    with _extracting_lock:
        if job_id in _extracting:
            return ExtractionSummary(
                job_id=job_id,
                success=True,
                message="Extraction already in progress. Poll /job/{id}/progress for status.",
                artifacts=[],
            )
        _extracting.add(job_id)

    # Write processing config for subprocess
    config_data = ProcessingConfig().model_dump()
    if body and getattr(body, "processing_config", None) is not None:
        pc = body.processing_config
        if hasattr(pc, "model_dump"):
            config_data = pc.model_dump()
        elif isinstance(pc, dict):
            config_data = {**config_data, **pc}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "processing_request.json").write_text(json.dumps(config_data), encoding="utf-8")

    meta = JobMetadata(
        job_id=job_id,
        filename=input_path.name,
        status="extracting",
        artifact_prefix=prefix,
        artifacts=[],
        stats={},
    )
    write_metadata(job_id, meta, artifact_prefix=prefix)

    thread = threading.Thread(
        target=_run_extraction_background,
        args=(job_id, input_path, output_dir, prefix),
        daemon=True,
    )
    thread.start()

    return ExtractionSummary(
        job_id=job_id,
        success=True,
        message="Extraction started. Poll GET /job/{id} and GET /job/{id}/progress for status.",
        artifacts=[],
    )
