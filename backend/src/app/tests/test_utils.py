"""Tests for utils (sanitize_stem)."""
import pytest

from app.core.utils import sanitize_stem


def test_sanitize_stem_basic():
    assert sanitize_stem("Hydraulics Manual v3.pdf") == "Hydraulics_Manual_v3"
    assert sanitize_stem("report.pdf") == "report"
    assert sanitize_stem("doc.docx") == "doc"


def test_sanitize_stem_spaces_and_special():
    assert sanitize_stem("a b c.pdf") == "a_b_c"
    assert sanitize_stem("file (1).pdf") == "file_1"
    assert sanitize_stem("test@file#2.x") == "test_file_2"


def test_sanitize_stem_collapse_underscores():
    assert sanitize_stem("a   b.pdf") == "a_b"
    assert sanitize_stem("x__y__.pdf") == "x_y"


def test_sanitize_stem_empty():
    assert sanitize_stem("") == "document"
    # .pdf has empty or dot-only stem on some systems; we normalize to document
    assert sanitize_stem(".pdf") == "document"
    assert sanitize_stem("...") == "document"


def test_sanitize_stem_length_limit():
    long_name = "a" * 100 + ".pdf"
    out = sanitize_stem(long_name)
    assert len(out) <= 80
