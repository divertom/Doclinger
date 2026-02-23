"""Chunks preview component."""
import json
import requests
import streamlit as st


def _chunks_artifact(artifacts: list[str]) -> str | None:
    """Return artifact filename ending with .chunks.jsonl, or None."""
    for a in artifacts:
        if a.endswith(".chunks.jsonl"):
            return a
    return None


def render_chunks_preview(backend_url: str, job_id: str, artifacts: list[str]) -> None:
    """Fetch chunks JSONL (prefixed name) and display a preview table/list."""
    chunks_file = _chunks_artifact(artifacts)
    if not chunks_file:
        st.info("No chunks yet. Run extraction first.")
        return

    try:
        r = requests.get(f"{backend_url}/artifact/{job_id}/{chunks_file}", timeout=10)
        r.raise_for_status()
        lines = r.text.strip().split("\n")
        chunks = [json.loads(ln) for ln in lines if ln]
    except requests.RequestException as e:
        st.error(f"Failed to load chunks: {e}")
        return
    except json.JSONDecodeError as e:
        st.error(f"Invalid chunks.jsonl: {e}")
        return

    st.subheader("RAG-ready chunks")
    st.caption(f"Total: {len(chunks)} chunks")

    for i, c in enumerate(chunks[:50]):
        chunk_id = c.get("id", i)
        section = c.get("meta", {}).get("section", "")
        with st.expander(f"Chunk {chunk_id}" + (f" — {section}" if section else "")):
            st.text(c.get("text", ""))

    if len(chunks) > 50:
        st.caption("(Showing first 50 chunks)")
