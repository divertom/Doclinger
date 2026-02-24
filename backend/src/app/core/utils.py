"""Utility helpers."""
import logging
import re
import uuid
from pathlib import Path

from .config import ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)

MAX_STEM_LENGTH = 80


def sanitize_stem(filename: str) -> str:
    """
    Derive a filesystem-safe artifact prefix from a filename.
    Example: "User Guide v2.pdf" => "User_Guide_v2"
    """
    stem = Path(filename).stem.strip()
    if not stem or stem.startswith("."):
        return "document"
    # Replace spaces with underscores
    s = stem.replace(" ", "_")
    # Keep only [A-Za-z0-9._-]; replace others with underscore
    s = re.sub(r"[^A-Za-z0-9._-]", "_", s)
    # Collapse multiple underscores
    s = re.sub(r"_+", "_", s).strip("_")
    if not s or not any(c.isalnum() for c in s):
        return "document"
    return s[:MAX_STEM_LENGTH]


def generate_job_id() -> str:
    """Generate a new job UUID."""
    return str(uuid.uuid4())


def is_allowed_file(path: Path) -> bool:
    """Check if file extension is allowed (Docling-supported types)."""
    return path.suffix.lower() in ALLOWED_EXTENSIONS
