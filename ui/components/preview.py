"""Document extraction preview component."""
import requests
import streamlit as st


def _artifact_by_suffix(artifacts: list[str], suffix: str) -> str | None:
    """Return first artifact filename ending with suffix, or None."""
    for a in artifacts:
        if a.endswith(suffix):
            return a
    return None


def render_document_preview(backend_url: str, job_id: str, artifacts: list[str]) -> None:
    """Fetch and display document markdown or structured JSON preview. Uses artifact list (prefixed names)."""
    doc_md = _artifact_by_suffix(artifacts, ".document.md")
    doc_json = _artifact_by_suffix(artifacts, ".document_structured.json")
    if doc_md:
        try:
            r = requests.get(f"{backend_url}/artifact/{job_id}/{doc_md}", timeout=10)
            r.raise_for_status()
            text = r.text
            st.subheader("Markdown")
            st.markdown(text[:50000] if len(text) > 50000 else text)
            if len(text) > 50000:
                st.caption("(Preview truncated at 50k characters)")
        except requests.RequestException as e:
            st.error(f"Failed to load {doc_md}: {e}")
    elif doc_json:
        try:
            r = requests.get(f"{backend_url}/artifact/{job_id}/{doc_json}", timeout=10)
            r.raise_for_status()
            data = r.json()
            st.subheader("Document JSON")
            st.json(data)
        except requests.RequestException as e:
            st.error(f"Failed to load {doc_json}: {e}")
    else:
        st.info("No document artifact yet. Run extraction first.")


def render_markdown_tab(backend_url: str, job_id: str, artifacts: list[str]) -> None:
    """Fetch and show .document.md in a tab."""
    doc_md = _artifact_by_suffix(artifacts, ".document.md")
    if not doc_md:
        st.info("No document markdown yet. Run extraction first.")
        return
    try:
        r = requests.get(f"{backend_url}/artifact/{job_id}/{doc_md}", timeout=10)
        r.raise_for_status()
        text = r.text
        st.markdown(text[:50000] if len(text) > 50000 else text)
        if len(text) > 50000:
            st.caption("(Truncated at 50k characters)")
    except requests.RequestException as e:
        st.error(f"Failed to load {doc_md}: {e}")


def render_json_tab(backend_url: str, job_id: str, artifacts: list[str]) -> None:
    """Fetch and show .document_structured.json in a tab."""
    doc_json = _artifact_by_suffix(artifacts, ".document_structured.json")
    if not doc_json:
        st.info("No document JSON yet. Run extraction first.")
        return
    try:
        r = requests.get(f"{backend_url}/artifact/{job_id}/{doc_json}", timeout=10)
        r.raise_for_status()
        st.json(r.json())
    except requests.RequestException as e:
        st.error(f"Failed to load {doc_json}: {e}")


def render_manifest_tab(backend_url: str, job_id: str, artifacts: list[str], processing_config: dict | None = None) -> None:
    """Fetch and show .manifest.json in a tab; optionally show processing_config used."""
    manifest_file = _artifact_by_suffix(artifacts, ".manifest.json")
    if processing_config:
        st.caption("Settings used for this run:")
        st.json(processing_config)
        st.divider()
    if not manifest_file:
        st.info("No manifest yet. Run extraction first.")
        return
    try:
        r = requests.get(f"{backend_url}/artifact/{job_id}/{manifest_file}", timeout=10)
        r.raise_for_status()
        st.json(r.json())
    except requests.RequestException as e:
        st.error(f"Failed to load {manifest_file}: {e}")
