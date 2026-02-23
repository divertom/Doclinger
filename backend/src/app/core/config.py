"""Application configuration."""
import os
from pathlib import Path

# Data root: overridable via env; otherwise project root / "data" or cwd / "data"
_DATA_ROOT = os.environ.get("DATA_ROOT")
if _DATA_ROOT:
    DATA_ROOT = Path(_DATA_ROOT)
else:
    _here = Path(__file__).resolve().parent
    # core -> app -> src -> backend -> project root
    _project_root = _here.parent.parent.parent.parent
    DATA_ROOT = _project_root / "data"
    if not DATA_ROOT.exists():
        # Fallback when not run from repo (e.g. installed package): use cwd
        DATA_ROOT = Path.cwd() / "data"

UPLOADS_DIR = DATA_ROOT / "uploads"
OUTPUTS_DIR = DATA_ROOT / "outputs"
EXAMPLES_DIR = DATA_ROOT / "examples"

# Docling-supported document types (and common fallbacks for placeholder)
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx",  # Office
    ".html", ".htm", ".md", ".csv", ".txt",  # Web / text
    ".png", ".tiff", ".tif", ".jpg", ".jpeg",  # Images (Docling can extract text/OCR)
}
MAX_UPLOAD_MB = 200
