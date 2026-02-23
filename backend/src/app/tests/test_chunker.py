"""Tests for chunker module: header-aware, token-sized, lean JSONL schema."""
import json
import tempfile
from pathlib import Path

import pytest

from app.core.chunker import (
    approx_tokens,
    generate_chunks_jsonl,
    iter_sections,
    split_to_token_windows,
    DEFAULT_TARGET_TOKENS,
    DEFAULT_OVERLAP_TOKENS,
)


def test_approx_tokens():
    assert approx_tokens("") == 0
    assert approx_tokens("a") == 1
    assert approx_tokens("abcd") == 1
    assert approx_tokens("abcde") == 2
    assert approx_tokens("x" * 400) == 100


def test_iter_sections_empty():
    assert list(iter_sections("")) == []
    assert list(iter_sections("  \n  ")) == []


def test_iter_sections_no_headers():
    md = "Just some paragraph.\n\nAnother one."
    sections = list(iter_sections(md))
    assert len(sections) == 1
    assert sections[0][0] == ""
    assert "Just some paragraph" in sections[0][1]


def test_iter_sections_multiple_headers():
    md = "# H1\n\nA\n\n## H2\n\nB\n\n### H3\n\nC"
    sections = list(iter_sections(md))
    assert len(sections) >= 3
    paths = [p for p, _ in sections]
    assert any("H1" in p for p in paths)
    assert any("H2" in p for p in paths)
    assert any("H3" in p for p in paths)


def test_split_to_token_windows_short():
    text = "Short text."
    out = split_to_token_windows(text, target_tokens=100, overlap_tokens=10)
    assert len(out) == 1
    assert out[0].strip() == text


def test_split_to_token_windows_large():
    text = "A\n\n" * 500
    out = split_to_token_windows(text, target_tokens=50, overlap_tokens=5)
    assert len(out) >= 2
    for w in out:
        assert approx_tokens(w) <= 60


def test_generate_chunks_jsonl_schema():
    with tempfile.TemporaryDirectory() as tmp:
        md = Path(tmp) / "doc.md"
        md.write_text("# Intro\n\nFirst paragraph.\n\n## Part 2\n\nSecond.")
        out = Path(tmp) / "chunks.jsonl"
        n = generate_chunks_jsonl(str(md), str(out), doc_id="job-1", target_tokens=500, overlap_tokens=50)
        assert n >= 1
        assert out.exists()
        lines = out.read_text().strip().split("\n")
        assert len(lines) == n
        for line in lines:
            obj = json.loads(line)
            assert "id" in obj
            assert "text" in obj
            assert "meta" in obj
            assert obj["meta"].get("doc_id") == "job-1"
            assert "section" in obj["meta"]
            assert len(obj["text"].strip()) > 0


def test_generate_chunks_jsonl_no_headers():
    with tempfile.TemporaryDirectory() as tmp:
        md = Path(tmp) / "doc.md"
        md.write_text("First paragraph.\n\nSecond paragraph.\n\nThird.")
        out = Path(tmp) / "chunks.jsonl"
        n = generate_chunks_jsonl(str(md), str(out), doc_id="d1", target_tokens=20, overlap_tokens=5)
        assert n >= 1
        first = json.loads(out.read_text().strip().split("\n")[0])
        assert first["meta"]["section"] == ""
