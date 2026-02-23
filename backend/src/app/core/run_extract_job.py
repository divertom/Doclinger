"""
Run extraction for one job in a separate process. Used by the API so that if
the worker is OOM-killed during PDF parsing, only this process dies and the API stays up.
Usage: python -m app.core.run_extract_job <job_id>
Exit: 0 on success, 1 on failure.
"""
from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    if len(sys.argv) != 2:
        logger.error("Usage: python -m app.core.run_extract_job <job_id>")
        return 1
    job_id = sys.argv[1]

    try:
        from app.core.chunker import generate_chunks_jsonl
        from app.core.docling_runner import run_docling
        from app.core.models import JobMetadata, ProcessingConfig
        from app.core.storage import (
            get_uploaded_file_path,
            job_output_dir,
            list_artifacts,
            write_metadata,
            write_progress,
        )
        from app.core.utils import sanitize_stem
    except Exception as e:
        logger.exception("Import failed: %s", e)
        traceback.print_exc()
        return 1

    input_path = get_uploaded_file_path(job_id)
    if not input_path or not input_path.exists():
        logger.error("Upload not found for job %s", job_id)
        return 1

    output_dir = job_output_dir(job_id)
    prefix = sanitize_stem(input_path.name)
    source_file = input_path.name

    # Read processing config written by API before subprocess start (optional)
    processing_config: ProcessingConfig | None = None
    request_config_path = output_dir / "processing_request.json"
    if request_config_path.exists():
        try:
            data = json.loads(request_config_path.read_text(encoding="utf-8"))
            processing_config = ProcessingConfig.model_validate(data)
        except Exception as e:
            logger.warning("Could not parse processing_request.json: %s", e)

    if processing_config is None:
        processing_config = ProcessingConfig()

    md_path = output_dir / f"{prefix}.document.md"
    json_path = output_dir / f"{prefix}.document_structured.json"
    chunks_path = output_dir / f"{prefix}.chunks.jsonl"
    manifest_path = output_dir / f"{prefix}.manifest.json"
    metadata_path = output_dir / f"{prefix}.metadata.json"

    def progress_callback(stage: str, percent: int) -> None:
        write_progress(job_id, stage, percent)

    write_progress(job_id, "Starting extraction", 5)
    try:
        result = run_docling(
            str(input_path),
            str(output_dir),
            progress_callback=progress_callback,
            artifact_prefix=prefix,
        )
    except Exception as e:
        logger.exception("Extraction failed: %s", e)
        traceback.print_exc()
        try:
            meta = JobMetadata(
                job_id=job_id,
                filename=source_file,
                status="failed",
                artifact_prefix=prefix,
                artifacts=[],
                stats={},
                error=str(e),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            write_metadata(job_id, meta, artifact_prefix=prefix)
        except Exception:
            pass
        return 1

    write_progress(job_id, "Chunking", 90)
    num_chunks = 0
    if md_path.exists():
        try:
            num_chunks = generate_chunks_jsonl(
                str(md_path),
                str(chunks_path),
                doc_id=job_id,
                target_tokens=1000,
                overlap_tokens=120,
            )
        except Exception as e:
            logger.warning("Chunking failed: %s", e)

    artifact_list = [f"{prefix}.document.md", f"{prefix}.document_structured.json", f"{prefix}.chunks.jsonl", f"{prefix}.manifest.json", f"{prefix}.metadata.json"]

    manifest = {
        "job_id": job_id,
        "source_file": source_file,
        "artifact_prefix": prefix,
        "artifacts": artifact_list,
        "num_chunks": num_chunks,
        "chunking": {"target_tokens": 1000, "overlap_tokens": 120},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    artifacts = list_artifacts(job_id)

    created_at = datetime.now(timezone.utc).isoformat()
    stats: dict = {
        "num_chunks": num_chunks,
        "placeholder": bool(result.get("placeholder", False)),
    }

    meta = JobMetadata(
        job_id=job_id,
        filename=source_file,
        status="completed",
        artifact_prefix=prefix,
        artifacts=artifacts,
        stats=stats,
        created_at=created_at,
    )
    try:
        write_metadata(job_id, meta, artifact_prefix=prefix)
    except Exception as e:
        logger.exception("Failed to write metadata: %s", e)
        traceback.print_exc()
        minimal = meta.model_dump()
        metadata_path.write_text(json.dumps(minimal, indent=2), encoding="utf-8")

    write_progress(job_id, "Complete", 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
