"""Run Docling extraction; fallback to placeholder when Docling is unavailable."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


def _json_default(obj):
    """Handle numpy and other non-JSON-serializable types from Docling export."""
    if hasattr(obj, "item"):
        return obj.item()
    return str(obj)

_docling_available: bool | None = None


def _check_docling() -> bool:
    global _docling_available
    if _docling_available is not None:
        return _docling_available
    try:
        import docling  # noqa: F401
        _docling_available = True
        return True
    except ImportError:
        _docling_available = False
        logger.warning("Docling not installed; using placeholder extraction")
        return False


def _build_converter():
    """Build DocumentConverter with PDF text-only by default (no OCR) to avoid hangs."""
    from docling.document_converter import DocumentConverter

    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import PdfFormatOption

        pipeline_options = PdfPipelineOptions(do_ocr=False)
        # Allow partial result if conversion is slow (e.g. large doc)
        pipeline_options.document_timeout = 1800.0
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )
    except Exception as e:
        logger.debug("Using default DocumentConverter (pipeline options not available): %s", e)
        return DocumentConverter()


def try_placeholder_fallback(
    input_path: str | Path, output_dir: str | Path, artifact_prefix: str | None = None
) -> bool:
    """Run placeholder (e.g. pypdf) extraction to write prefix.document.md / .document_structured.json. Returns True if written."""
    try:
        _placeholder_extract(str(input_path), str(output_dir), artifact_prefix=artifact_prefix)
        prefix = artifact_prefix if artifact_prefix else "document"
        return (Path(output_dir) / f"{prefix}.document.md").exists()
    except Exception as e:
        logger.warning("Placeholder fallback failed: %s", e)
        return False


def _placeholder_extract(input_path: str, output_dir: str, artifact_prefix: str | None = None) -> dict:
    """Placeholder: read raw text and save as prefix.document.md + prefix.document_structured.json."""
    path = Path(input_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    raw_text = ""
    try:
        if path.suffix.lower() == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(path)
                parts = []
                for i in range(len(reader.pages)):
                    parts.append(reader.pages[i].extract_text() or "")
                raw_text = "\n".join(parts)
                del reader
            except ImportError:
                raw_text = f"[PDF placeholder: {path.name} - install pypdf or docling for full extraction]"
        elif path.suffix.lower() == ".docx":
            try:
                import docx
                doc = docx.Document(path)
                raw_text = "\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                raw_text = f"[DOCX placeholder: {path.name} - install python-docx or docling for full extraction]"
        elif path.suffix.lower() in {".html", ".htm", ".md", ".csv", ".txt"}:
            raw_text = path.read_text(encoding="utf-8", errors="replace")
        else:
            raw_text = f"[{path.suffix.upper()} placeholder: {path.name} - install docling for extraction]"
    except Exception as e:
        logger.exception("Placeholder read failed: %s", e)
        raw_text = f"[Error reading file: {e}]"

    prefix = artifact_prefix if artifact_prefix else "document"
    md_path = output / f"{prefix}.document.md"
    md_path.write_text(raw_text, encoding="utf-8")
    json_path = output / f"{prefix}.document_structured.json"
    doc_json = {
        "source": str(path),
        "text": raw_text,
        "placeholder": True,
    }
    json_path.write_text(json.dumps(doc_json, indent=2), encoding="utf-8")
    return {
        "document_md": str(md_path),
        "document_structured_json": str(json_path),
        "placeholder": True,
    }


def run_docling(
    input_path: str,
    output_dir: str,
    progress_callback: Callable[[str, int], None] | None = None,
    artifact_prefix: str | None = None,
) -> dict:
    """
    Run Docling extraction on input_path and write results to output_dir.
    Writes <prefix>.document.md and <prefix>.document_structured.json.
    Returns dict with document_md, document_structured_json paths and optional page_count, tables_detected, warnings.
    """
    def report(stage: str, percent: int) -> None:
        if progress_callback:
            progress_callback(stage, percent)

    inp = Path(input_path)
    out = Path(output_dir)
    if not inp.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    out.mkdir(parents=True, exist_ok=True)
    prefix = artifact_prefix if artifact_prefix else "document"

    if _check_docling():
        try:
            report("Starting extraction", 5)
            from docling.document_converter import DocumentConverter

            report("Loading document", 10)
            converter = _build_converter()
            report("Converting document (layout, tables…)", 25)
            result = converter.convert(str(inp))
            report("Document converted", 60)
            doc = result.document
            report("Generating markdown", 75)
            export = doc.export_to_markdown()
            report("Saving outputs", 85)
            md_path = out / f"{prefix}.document.md"
            md_path.write_text(export, encoding="utf-8")
            json_path = out / f"{prefix}.document_structured.json"
            doc_json = {"source": str(inp), "markdown": export}
            try:
                doc_json = doc.export_to_dict()
            except Exception:
                pass
            json_path.write_text(
                json.dumps(doc_json, indent=2, default=_json_default), encoding="utf-8"
            )
            summary = {
                "document_md": str(md_path),
                "document_structured_json": str(json_path),
                "placeholder": False,
            }
            if hasattr(result, "document") and hasattr(result.document, "pages"):
                summary["page_count"] = len(result.document.pages)
            return summary
        except Exception as e:
            logger.exception("Docling extraction failed: %s", e)
            return _placeholder_extract(input_path, output_dir, artifact_prefix=prefix)
    report("Using placeholder extraction", 50)
    return _placeholder_extract(input_path, output_dir, artifact_prefix=prefix)
