"""
Document processing settings: defaults and UI helpers.
Minimal settings (Ingest page) and Advanced settings (Settings page).
"""
from __future__ import annotations

import streamlit as st

# Single source of truth for defaults; keys match backend expectations (future use).
DEFAULT_PROCESSING_CONFIG = {
    # Minimal (always visible on Ingest)
    "image_export_mode": "Figures (referenced)",
    "chunk_size_tokens": 1000,
    "chunk_overlap_tokens": 120,
    "ocr_mode": "Auto",
    "remove_repetitive_headers_footers": True,
    # Advanced (Settings page)
    "header_aware_chunking": True,
    "process_all_pages": True,
    "page_start": 1,
    "page_end": 1,
    "table_handling_mode": "Separate table chunks + keep structured (recommended)",
    "fault_error_code_focus": False,
    "include_page_numbers_in_chunk_metadata": True,
    "include_bounding_boxes": False,
    "language": "Auto",
}


def render_minimal_settings(config: dict) -> dict:
    """Render minimal settings (Ingest page). Returns updated config from widget values."""
    st.subheader("Options")
    config = dict(config)

    opts_image = [
        "Off",
        "Figures (referenced)",
        "Figures + pages (referenced)",
        "Figures (embedded)",
        "Figures + pages (embedded)",
    ]
    config["image_export_mode"] = st.selectbox(
        "Image export mode",
        options=opts_image,
        index=opts_image.index(config.get("image_export_mode", "Figures (referenced)")),
        key="min_image_export",
        help="Referenced: separate image files + links (best for RAG). Embedded: increases markdown size and slows ingestion.",
    )
    config["chunk_size_tokens"] = st.number_input(
        "Chunk size (tokens)",
        min_value=100,
        max_value=8000,
        value=int(config.get("chunk_size_tokens", 1000)),
        step=100,
        key="min_chunk_size",
        help="Larger chunks = fewer vectors (faster ingest) but can reduce precision if too large.",
    )
    config["chunk_overlap_tokens"] = st.number_input(
        "Chunk overlap (tokens)",
        min_value=0,
        max_value=500,
        value=int(config.get("chunk_overlap_tokens", 120)),
        step=10,
        key="min_chunk_overlap",
        help="Overlap improves retrieval continuity but increases tokens embedded and storage.",
    )
    opts_ocr = ["Auto", "Force OCR", "Disable OCR"]
    config["ocr_mode"] = st.selectbox(
        "OCR mode",
        options=opts_ocr,
        index=opts_ocr.index(config.get("ocr_mode", "Auto")),
        key="min_ocr",
        help="OCR required for scanned PDFs. For digital PDFs it can slow processing.",
    )
    config["remove_repetitive_headers_footers"] = st.checkbox(
        "Remove repetitive headers/footers",
        value=bool(config.get("remove_repetitive_headers_footers", True)),
        key="min_remove_headers_footers",
        help="Removes repeating boilerplate to reduce noise, chunk count, and improve search quality.",
    )

    return config


def render_advanced_settings(config: dict) -> dict:
    """Render advanced settings (Settings page). Returns updated config from widget values."""
    config = dict(config)

    st.subheader("Chunking & structure")
    config["header_aware_chunking"] = st.checkbox(
        "Header-aware chunking",
        value=bool(config.get("header_aware_chunking", True)),
        key="adv_header_aware",
        help="Uses markdown headers to keep chunks aligned with sections; improves relevance.",
    )
    config["process_all_pages"] = st.checkbox(
        "Process all pages",
        value=bool(config.get("process_all_pages", True)),
        key="adv_process_all_pages",
        help="If off, only the given page range is processed; reduces runtime and output size.",
    )
    if not config["process_all_pages"]:
        c1, c2 = st.columns(2)
        with c1:
            config["page_start"] = int(st.number_input("Start page (1-indexed)", min_value=1, value=int(config.get("page_start", 1)), key="adv_page_start"))
        with c2:
            config["page_end"] = int(st.number_input("End page (1-indexed)", min_value=1, value=int(config.get("page_end", 1)), key="adv_page_end"))

    st.subheader("Tables & technical content")
    opts_table = [
        "Flatten tables into markdown only",
        "Keep structured tables in JSON only",
        "Separate table chunks + keep structured (recommended)",
        "Normalize tables to key-value text + keep structured",
    ]
    current_table = config.get("table_handling_mode") or "Separate table chunks + keep structured (recommended)"
    table_index = opts_table.index(current_table) if current_table in opts_table else 2
    config["table_handling_mode"] = st.selectbox(
        "Table handling mode",
        options=opts_table,
        index=table_index,
        key="adv_table_mode",
        help="Separate table chunks improves retrieval for specs/error codes; normalization makes tables more searchable.",
    )
    config["fault_error_code_focus"] = st.checkbox(
        "Fault / error code focus",
        value=bool(config.get("fault_error_code_focus", False)),
        key="adv_fault_focus",
        help="Attempts to detect error/fault codes and keep them in dedicated chunks; improves lookup queries.",
    )

    st.subheader("Metadata & size controls")
    config["include_page_numbers_in_chunk_metadata"] = st.checkbox(
        "Include page numbers in chunk metadata",
        value=bool(config.get("include_page_numbers_in_chunk_metadata", True)),
        key="adv_page_numbers",
        help="Enables citations like 'page 12'; tiny size overhead.",
    )
    config["include_bounding_boxes"] = st.checkbox(
        "Include bounding boxes",
        value=bool(config.get("include_bounding_boxes", False)),
        key="adv_bbox",
        help="Adds layout bbox metadata; useful for linking to page regions but increases artifact size.",
    )
    opts_lang = ["Auto", "English", "German", "Multi-language"]
    config["language"] = st.selectbox(
        "Language",
        options=opts_lang,
        index=opts_lang.index(config.get("language", "Auto")),
        key="adv_language",
        help="Helps OCR and normalization; wrong choice can reduce OCR accuracy.",
    )

    return config
