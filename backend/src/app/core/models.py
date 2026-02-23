"""Pydantic models for API and domain."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProcessingConfig(BaseModel):
    """Document processing options (UI + backend). Extra keys allowed for forward compatibility."""
    model_config = {"extra": "allow"}


class ExtractRequestBody(BaseModel):
    """Optional body for POST /extract/{job_id}. UI sends processing_config; backend may apply (partial support)."""
    processing_config: ProcessingConfig | dict[str, Any] | None = Field(default=None, description="Document processing options from UI")


class UploadResponse(BaseModel):
    """Response after successful file upload."""
    job_id: str = Field(..., description="UUID of the created job")


class ExtractionSummary(BaseModel):
    """Summary returned after extraction completes."""
    job_id: str
    success: bool = True
    message: str = "Extraction completed"
    artifacts: list[str] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)


class JobMetadata(BaseModel):
    """Job metadata stored in <prefix>.metadata.json."""
    job_id: str
    filename: str
    status: str = "pending"  # pending | extracting | completed | failed
    artifact_prefix: str | None = None  # sanitized stem for artifact filenames
    artifacts: list[str] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: str | None = None


class JobResponse(BaseModel):
    """Response for GET /job/{job_id}."""
    metadata: JobMetadata
    artifacts: list[str] = Field(default_factory=list)
