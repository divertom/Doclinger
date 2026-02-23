"""Tests for storage module."""
from pathlib import Path

import pytest

# Use a temporary data root for tests
@pytest.fixture
def data_root(tmp_path):
    return tmp_path


@pytest.fixture(autouse=True)
def patch_config(monkeypatch, data_root):
    monkeypatch.setattr("app.core.storage.UPLOADS_DIR", data_root / "uploads")
    monkeypatch.setattr("app.core.storage.OUTPUTS_DIR", data_root / "outputs")
    from app.core import storage
    storage.ensure_dirs()
    yield


def test_job_upload_dir():
    from app.core.storage import job_upload_dir
    d = job_upload_dir("job-123")
    assert d.name == "job-123"
    assert d.parent.name == "uploads"
    assert d.exists()


def test_job_output_dir():
    from app.core.storage import job_output_dir
    d = job_output_dir("job-456")
    assert d.name == "job-456"
    assert d.parent.name == "outputs"
    assert d.exists()


def test_get_uploaded_file_path_empty():
    from app.core.storage import get_uploaded_file_path
    assert get_uploaded_file_path("nonexistent") is None


def test_get_uploaded_file_path_found():
    from app.core.storage import job_upload_dir, get_uploaded_file_path
    ud = job_upload_dir("job-789")
    (ud / "doc.pdf").write_bytes(b"fake pdf")
    path = get_uploaded_file_path("job-789")
    assert path is not None
    assert path.name == "doc.pdf"


def test_list_artifacts_empty():
    from app.core.storage import list_artifacts
    assert list_artifacts("no-job") == []


def test_list_artifacts_found():
    from app.core.storage import job_output_dir, list_artifacts
    od = job_output_dir("job-abc")
    (od / "report.document.md").write_text("# Hi")
    (od / "report.chunks.jsonl").write_text("{}")
    (od / "report.metadata.json").write_text("{}")
    assert set(list_artifacts("job-abc")) == {"report.document.md", "report.chunks.jsonl", "report.metadata.json"}


def test_read_write_metadata():
    from app.core.storage import read_metadata, write_metadata
    from app.core.models import JobMetadata
    meta = JobMetadata(job_id="m1", filename="x.pdf", status="completed", artifact_prefix="x", artifacts=["x.document.md"])
    write_metadata("m1", meta, artifact_prefix="x")
    read = read_metadata("m1")
    assert read is not None
    assert read.job_id == "m1"
    assert read.filename == "x.pdf"
    assert read.artifacts == ["x.document.md"]


def test_get_artifact_path():
    from app.core.storage import job_output_dir, get_artifact_path
    od = job_output_dir("job-art")
    (od / "prefix.document.md").write_text("x")
    assert get_artifact_path("job-art", "prefix.document.md") is not None
    assert get_artifact_path("job-art", "missing") is None
    assert get_artifact_path("job-art", "../etc/passwd") is None
