"""Docling-UI FastAPI application."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_upload import router as upload_router
from app.api.routes_extract import router as extract_router
from app.api.routes_job import router as job_router
from app.api.routes_artifact import router as artifact_router
from app.api.routes_storage import router as storage_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Docling-UI",
    description="Document extraction and RAG chunking API",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(extract_router)
app.include_router(job_router)
app.include_router(artifact_router)
app.include_router(storage_router)


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok"}
