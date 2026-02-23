"""
Docling-UI Streamlit app.
Upload, configure processing options, run extraction, preview and download artifacts.
"""
from __future__ import annotations

import io
import os
import time
import zipfile
from copy import deepcopy
from pathlib import Path

import requests
import streamlit as st

from components.chunks_view import render_chunks_preview
from components.preview import render_json_tab, render_markdown_tab, render_manifest_tab
from components.progress_stepper import STAGE_LABELS, render_stepper, stage_index
from components.settings import DEFAULT_PROCESSING_CONFIG, render_advanced_settings, render_minimal_settings

DEFAULT_BACKEND = "http://localhost:8001"


def get_backend_url() -> str:
    return st.session_state.get("backend_url") or os.environ.get("BACKEND_URL") or DEFAULT_BACKEND


def backend_reachable(url: str) -> bool:
    try:
        r = requests.get(f"{url}/job/00000000-0000-0000-0000-000000000000", timeout=3)
        return True
    except requests.RequestException:
        return False


def clear_document_cache() -> None:
    """Clear session state for the current document/artifacts so a new document starts fresh."""
    for key in (
        "progress_job_id",
        "progress_completed_times",
        "progress_total_seconds",
        "show_artifact_content",
        "extract_error",
        "extract_artifacts",
        "extract_artifacts_job_id",
    ):
        if key in st.session_state:
            del st.session_state[key]


def upload_file(backend_url: str) -> str | None:
    file = st.file_uploader(
        "Choose a document (PDF, DOCX, PPTX, XLSX, HTML, MD, CSV, images…)",
        type=["pdf", "docx", "pptx", "xlsx", "html", "htm", "md", "csv", "txt", "png", "tiff", "tif", "jpg", "jpeg"],
    )
    if not file:
        # Keep current job when file uploader is empty (e.g. after switching to Advanced Settings and back)
        if "job_id" in st.session_state:
            return st.session_state["job_id"]
        return None
    file_key = (file.name, file.size)
    if st.session_state.get("uploaded_file_key") == file_key and st.session_state.get("job_id"):
        return st.session_state["job_id"]
    with st.spinner("Uploading..."):
        try:
            # Always clean storage before loading a new document
            try:
                requests.post(f"{backend_url}/storage/clean", timeout=10)
            except requests.RequestException:
                pass
            r = requests.post(
                f"{backend_url}/upload",
                files={"file": (file.name, file.getvalue(), file.type)},
                timeout=30,
            )
            if r.status_code >= 400:
                try:
                    detail = r.json().get("detail", r.text) or r.reason
                except Exception:
                    detail = r.text or r.reason or f"HTTP {r.status_code}"
                st.error(f"Upload failed: {detail}")
                return None
            job_id = r.json()["job_id"]
            clear_document_cache()
            st.session_state["job_id"] = job_id
            st.session_state["uploaded_file_key"] = file_key
            return job_id
        except requests.RequestException as e:
            st.error(f"Upload failed: {e}")
            return None


def run_extract_async(backend_url: str, job_id: str, processing_config: dict) -> tuple[bool, str | None, dict | None]:
    """Call extract API with optional processing_config body. Returns (success, error_message, response_json or None)."""
    try:
        r = requests.post(
            f"{backend_url}/extract/{job_id}",
            json={"processing_config": processing_config},
            timeout=1820,
        )
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text) or r.reason
            except Exception:
                detail = r.text or r.reason or str(r.status_code)
            return False, f"{r.status_code}: {detail}" if detail else str(r.reason), None
        # 200 or 202 (extraction started in background)
        try:
            return True, None, r.json()
        except Exception:
            return True, None, None
    except requests.RequestException as e:
        return False, str(e), None


def render_sidebar(backend_url: str) -> str:
    """Render sidebar (backend, status, storage). Returns backend_url."""
    st.caption("Backend API")
    override = st.text_input(
        "URL",
        value=st.session_state["backend_url"],
        key="backend_url_input",
        label_visibility="collapsed",
        placeholder="http://localhost:8001",
    )
    st.session_state["backend_url"] = (override.strip() or st.session_state["backend_url"])
    st.caption(f"Using: `{backend_url}`")
    st.divider()
    st.caption("Status")
    if st.session_state.get("extract_error"):
        st.error(st.session_state["extract_error"])
        if st.button("Dismiss", key="dismiss_error"):
            st.session_state["extract_error"] = None
            st.rerun()
    else:
        st.caption("No errors")
    st.divider()
    docker_default = os.environ.get("BACKEND_URL", "").strip()
    if docker_default.startswith("http://127.0.0.1:8000"):
        st.info("Using Docker: API is on port **8000** in this container. Use **8001** when running UI on your machine.")
        if st.button("Reset to Docker API (8000)", key="reset_backend"):
            st.session_state["backend_url"] = docker_default
            st.rerun()
    elif "8000" in backend_url and "8001" not in backend_url:
        st.warning("Running locally? If the API is in Docker, use **http://localhost:8001**.")
    return backend_url


def ingest_page(backend_url: str) -> None:
    st.subheader("Processing")
    job_id = upload_file(backend_url)
    if not job_id:
        if st.session_state.get("progress_job_id") is not None:
            st.session_state["progress_job_id"] = None
            st.session_state["progress_completed_times"] = None
            st.session_state["progress_total_seconds"] = None
        return

    # Minimal settings (always visible)
    processing_config = st.session_state.get("processing_config") or deepcopy(DEFAULT_PROCESSING_CONFIG)
    config = render_minimal_settings(processing_config)
    st.session_state["processing_config"] = {**processing_config, **config}

    if st.button("Reset to defaults", key="reset_minimal"):
        st.session_state["processing_config"] = deepcopy(DEFAULT_PROCESSING_CONFIG)
        st.rerun()

    # Job status and artifacts (fetch first so we can show status and progress in one section)
    try:
        r = requests.get(f"{backend_url}/job/{job_id}", timeout=10)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        st.warning(f"Could not load job: {e}")
        return

    metadata = data.get("metadata", {})
    artifacts = data.get("artifacts", []) or []
    # Use artifacts from last successful extract response if GET /job returned none (e.g. timing)
    if not artifacts and st.session_state.get("extract_artifacts_job_id") == job_id:
        artifacts = st.session_state.get("extract_artifacts") or []
    status = metadata.get("status", "unknown")

    st.divider()
    st.subheader("Job status")
    progress_placeholder = st.empty()

    # ----- Extracting: progress block auto-updates (fragment only), plus manual "Refresh progress" -----
    if status == "extracting":
        st.session_state["_extract_job_id"] = job_id
        st.session_state["_extract_backend_url"] = backend_url

        @st.fragment(run_every=5)
        def progress_poll():
            bid = st.session_state.get("_extract_backend_url") or backend_url
            jid = st.session_state.get("_extract_job_id") or job_id
            try:
                r = requests.get(f"{bid}/job/{jid}", timeout=5)
                if r.status_code == 200:
                    meta = r.json().get("metadata", {})
                    if meta.get("status") != "extracting":
                        # Persist last known timings so completed view can show total time
                        ct = st.session_state.get("progress_completed_times") or {}
                        if ct and st.session_state.get("progress_job_id") == jid:
                            st.session_state["progress_total_seconds"] = sum(ct.values())
                        st.rerun()
                        return
            except requests.RequestException:
                pass
            stage = "Extracting…"
            try:
                r = requests.get(f"{bid}/job/{jid}/progress", timeout=5)
                if r.status_code == 200:
                    stage = r.json().get("stage", "Extracting…")
            except requests.RequestException:
                pass
            now = time.time()
            if st.session_state.get("progress_job_id") != jid:
                st.session_state["progress_job_id"] = jid
                st.session_state["progress_current_stage"] = stage
                st.session_state["progress_stage_start_time"] = now
                st.session_state["progress_completed_times"] = {}
            completed_times = st.session_state.get("progress_completed_times") or {}
            prev = st.session_state.get("progress_current_stage")
            if prev != stage:
                if prev:
                    idx = stage_index(prev)
                    if 0 <= idx < len(STAGE_LABELS):
                        completed_times[STAGE_LABELS[idx]] = int(now - st.session_state.get("progress_stage_start_time", now))
                st.session_state["progress_current_stage"] = stage
                st.session_state["progress_stage_start_time"] = now
                st.session_state["progress_completed_times"] = dict(completed_times)
            elapsed = int(now - st.session_state.get("progress_stage_start_time", now))
            with progress_placeholder.container():
                st.caption("Large files can take several minutes.")
                render_stepper(stage, elapsed, completed_times)

        progress_poll()
        if st.button("Refresh progress", key="refresh_progress"):
            st.rerun()

    # ----- Not extracting: show static progress and "Run extraction" -----
    if status != "extracting":
        with progress_placeholder.container():
            st.caption("Large files can take several minutes.")
            if (
                st.session_state.get("progress_job_id") == job_id
                and st.session_state.get("progress_completed_times") is not None
                and st.session_state.get("progress_total_seconds") is not None
            ):
                render_stepper("complete", 0, st.session_state["progress_completed_times"])
                total_s = st.session_state["progress_total_seconds"]
                st.caption(
                    f"**Total processing time:** {total_s // 60}m {total_s % 60}s"
                    if total_s >= 60
                    else f"**Total processing time:** {total_s}s"
                )

        if st.button("Run extraction", type="primary", key="run_extract"):
            st.session_state["extract_error"] = None
            config_to_send = st.session_state.get("processing_config") or deepcopy(DEFAULT_PROCESSING_CONFIG)
            success, err, resp = run_extract_async(backend_url, job_id, config_to_send)
            msg = (resp or {}).get("message", "")
            extraction_started = success and (
                not (resp and resp.get("artifacts"))
                or "Extraction started" in msg
                or "already in progress" in msg
            )
            if extraction_started:
                st.rerun()
            if success and resp and isinstance(resp.get("artifacts"), list) and resp["artifacts"]:
                st.session_state["extract_artifacts"] = resp["artifacts"]
                st.session_state["extract_artifacts_job_id"] = job_id
                st.session_state["extract_error"] = None
                st.rerun()
            st.session_state["extract_error"] = err or "Extraction failed."
            st.rerun()

    if status == "failed":
        st.error("Extraction failed. Check the Status section in the sidebar for details.")
        with st.expander("How to get full logs"):
            st.code("docker logs Docling", language="text")
    st.write(f"**Status:** {status}")

    # Download artifacts – always show section; when empty, show message
    st.write("**Download artifacts:**")
    if artifacts:
        fetched = []
        for name in artifacts:
            try:
                r = requests.get(f"{backend_url}/artifact/{job_id}/{name}", timeout=30)
                if r.status_code == 200:
                    fetched.append((name, r.content))
            except requests.RequestException:
                pass
        if fetched:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, content in fetched:
                    zf.writestr(name, content)
            prefix = metadata.get("artifact_prefix") or Path(metadata.get("filename", "document")).stem
            zip_name = f"{prefix}.docling.zip"
            st.download_button(
                label="Download all artifacts (ZIP)",
                data=buf.getvalue(),
                file_name=zip_name,
                key=f"dl_all_{job_id}",
            )
            st.caption("Or download individually:")
            for name, content in fetched:
                st.download_button(label=name, data=content, file_name=name, key=f"dl_{job_id}_{name}")
            for name in artifacts:
                if not any(n == name for n, _ in fetched):
                    st.caption(f"{name} (unavailable)")
        else:
            st.caption("No artifacts available yet.")
    else:
        st.caption("No artifacts yet. Run extraction above to generate document and chunks.")
    st.divider()

    # Show artifact content – always show option; when no artifacts, caption only
    show_artifact_content = st.checkbox(
        "Show artifact content",
        value=False,
        key="show_artifact_content",
        disabled=not artifacts,
    )
    if show_artifact_content and artifacts:
        tab_md, tab_json, tab_chunks, tab_manifest = st.tabs(["Markdown", "JSON", "Chunks", "Manifest"])
        with tab_md:
            render_markdown_tab(backend_url, job_id, artifacts)
        with tab_json:
            render_json_tab(backend_url, job_id, artifacts)
        with tab_chunks:
            render_chunks_preview(backend_url, job_id, artifacts)
        with tab_manifest:
            render_manifest_tab(backend_url, job_id, artifacts, st.session_state.get("processing_config"))
    elif not artifacts:
        st.caption("Run extraction above to generate artifacts, then you can preview them here.")
    else:
        st.caption("Enable **Show artifact content** to preview Markdown, JSON, Chunks, and Manifest here.")



def settings_page(backend_url: str) -> None:
    st.subheader("Advanced Settings")
    st.caption("Advanced processing options. Save to apply; they are sent with the next Run extraction on the Processing page.")
    processing_config = st.session_state.get("processing_config") or deepcopy(DEFAULT_PROCESSING_CONFIG)
    config = render_advanced_settings(processing_config)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Reset to defaults", key="reset_settings"):
            st.session_state["processing_config"] = deepcopy(DEFAULT_PROCESSING_CONFIG)
            st.rerun()
    with col2:
        if st.button("Save settings", type="primary", key="save_settings"):
            st.session_state["processing_config"] = dict(config)
            st.success("Settings saved. They will be used on the next extraction.")
            st.rerun()
    st.caption("Minimal settings (image export, chunk size/overlap, OCR, headers/footers) are on the Processing page.")

    st.divider()
    st.caption("Storage")
    if st.button("Clean storage (delete all uploads & outputs)", key="clean_storage"):
        try:
            r = requests.post(f"{backend_url}/storage/clean", timeout=10)
            if r.status_code == 200:
                data = r.json()
                u, o = data.get("removed_uploads", 0), data.get("removed_outputs", 0)
                st.success(f"Cleaned: {u} upload job(s), {o} output job(s) removed.")
                if "job_id" in st.session_state:
                    del st.session_state["job_id"]
                    del st.session_state["uploaded_file_key"]
                    clear_document_cache()
                st.rerun()
            else:
                st.error(r.text or f"Clean failed: {r.status_code}")
        except requests.RequestException as e:
            st.error(f"Clean failed: {e}")


def main() -> None:
    st.set_page_config(page_title="Docling - Document Processing", page_icon="📄", layout="wide", initial_sidebar_state="collapsed")

    if "backend_url" not in st.session_state:
        st.session_state["backend_url"] = (os.environ.get("BACKEND_URL") or DEFAULT_BACKEND).strip()
    if "extract_error" not in st.session_state:
        st.session_state["extract_error"] = None
    st.session_state.setdefault("processing_config", deepcopy(DEFAULT_PROCESSING_CONFIG))
    if "progress_completed_times" not in st.session_state:
        st.session_state["progress_completed_times"] = None
    if "progress_total_seconds" not in st.session_state:
        st.session_state["progress_total_seconds"] = None
    if "progress_job_id" not in st.session_state:
        st.session_state["progress_job_id"] = None
    st.session_state.setdefault("nav_page", "Processing")
    page = st.session_state.get("nav_page", "Processing")

    # Backend status for optional status panel (computed before header so we can show it)
    backend_url = get_backend_url()
    backend_ok = backend_reachable(backend_url)

    # Header per handoff: nav bar (buttons, no new page) → page title (h1) → status panel; blue gradient
    page_title = "Processing" if page == "Processing" else "Advanced Settings"
    status_class = "status-success" if backend_ok else "status-error"
    status_text = "Connected" if backend_ok else "Disconnected"

    # Nav as buttons so selecting Processing/Advanced Settings only changes content below (st.rerun), no URL change
    st.markdown("""
    <style>
    :root {
        --primary-color: #2563eb;
        --primary-hover: #1d4ed8;
        --shadow: 0 1px 3px 0 rgba(0,0,0,0.1), 0 1px 2px 0 rgba(0,0,0,0.06);
    }
    .header-nav-row {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-hover) 100%);
        padding: 1.5rem 2rem 0.5rem 2rem;
        margin: 0 -1rem 0 -1rem;
        border-radius: 0.25rem 0.25rem 0 0;
        box-shadow: var(--shadow);
        box-sizing: border-box;
    }
    .header-nav-row .stButton button {
        color: rgba(255,255,255,0.9) !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        padding: 0.375rem 0.75rem !important;
        border-radius: 0.375rem !important;
    }
    .header-nav-row .stButton button:hover {
        background: rgba(255,255,255,0.15) !important;
        color: white !important;
    }
    .header-nav-row .stButton button[kind="primary"] {
        background: rgba(255,255,255,0.2) !important;
        color: white !important;
    }
    .header-rest {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-hover) 100%);
        color: white;
        padding: 0 2rem 1.5rem 2rem;
        margin: 0 -1rem 1.5rem -1rem;
        margin-top: -24px;
        padding-top: 24px;
        box-sizing: border-box;
    }
    .header-rest h1 { font-size: 1.75rem; font-weight: 600; margin: 0 0 1rem 0; color: white; }
    .header-rest .status-panel { display: flex; gap: 1.5rem; flex-wrap: wrap; }
    .header-rest .status-item { display: flex; align-items: center; gap: 0.5rem; }
    .header-rest .status-label { font-size: 0.875rem; opacity: 0.9; }
    .header-rest .status-badge {
        padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.05em;
    }
    .header-rest .status-success { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); }
    .header-rest .status-error { background: rgba(239,68,68,0.3); border: 1px solid rgba(239,68,68,0.5); }
    @media (max-width: 768px) { .header-nav-row, .header-rest { padding-left: 1rem; padding-right: 1rem; } .header-rest h1 { font-size: 1.5rem; } }
    /* Header stays in main content area so it resizes with sidebar; use content-relative width */
    div:has(> .header-nav-row) + div,
    div:has(.header-nav-row) + div {
        margin: 0 -1rem 0 -1rem !important;
        padding: 0 !important;
        width: calc(100% + 2rem) !important;
        max-width: calc(100% + 2rem) !important;
        box-sizing: border-box !important;
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-hover) 100%) !important;
        border: none !important;
    }
    div:has(> .header-nav-row) + div [data-testid="stVerticalBlock"],
    div:has(.header-nav-row) + div [data-testid="stVerticalBlock"],
    div:has(> .header-nav-row) + div [data-testid="stHorizontalBlock"] > div {
        background: transparent !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
    }
    div:has(> .header-nav-row) + div [data-testid="stHorizontalBlock"],
    div:has(.header-nav-row) + div [data-testid="stHorizontalBlock"] {
        background: transparent !important;
        padding: 0.5rem 2rem 0.25rem 2rem !important;
        margin: 0 !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        box-sizing: border-box !important;
        display: flex !important;
        justify-content: flex-start !important;
    }
    div:has(> .header-nav-row) + div [data-testid="stHorizontalBlock"] > div,
    div:has(.header-nav-row) + div [data-testid="stHorizontalBlock"] > div {
        flex: 0 0 auto !important;
        max-width: max-content !important;
    }
    div:has(> .header-nav-row) + div .stButton button,
    div:has(.header-nav-row) + div .stButton button {
        color: rgba(255,255,255,0.9) !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        padding: 0.375rem 0.75rem !important;
        border-radius: 0.375rem !important;
    }
    div:has(> .header-nav-row) + div .stButton button:hover {
        background: rgba(255,255,255,0.15) !important;
        color: white !important;
    }
    div:has(> .header-nav-row) + div .stButton button[kind="primary"],
    div:has(.header-nav-row) + div .stButton button[kind="primary"] {
        background: rgba(255,255,255,0.2) !important;
        color: white !important;
    }
    </style>
    <div class="header-nav-row" style="height:0;overflow:hidden;margin:0;padding:0;"></div>
    """, unsafe_allow_html=True)
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button(
            "Processing",
            key="nav_processing",
            type="primary" if page == "Processing" else "secondary",
        ):
            st.session_state["nav_page"] = "Processing"
            st.rerun()
    with col2:
        if st.button(
            "Advanced Settings",
            key="nav_settings",
            type="primary" if page == "Advanced Settings" else "secondary",
        ):
            st.session_state["nav_page"] = "Advanced Settings"
            st.rerun()
    st.markdown(
        f"""
    <div class="header-rest">
        <h1>{page_title}</h1>
        <div class="status-panel">
            <div class="status-item">
                <span class="status-label">Backend:</span>
                <span class="status-badge {status_class}">{status_text}</span>
            </div>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )
    st.caption("Upload a document and extract content.")
    st.divider()

    with st.sidebar:
        backend_url = get_backend_url()
        render_sidebar(backend_url)

    if not backend_reachable(backend_url):
        err_msg = f"Cannot reach the backend at **{backend_url}**."
        if "8001" in backend_url:
            err_msg += " Using Docker UI? Set sidebar URL to **http://127.0.0.1:8000**."
        else:
            err_msg += " Ensure the Docling API is running (e.g. `docker-compose up -d`)."
        st.error(err_msg)
        return

    if page == "Processing":
        ingest_page(backend_url)
    else:
        settings_page(backend_url)


if __name__ == "__main__":
    main()
