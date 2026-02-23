"""Generate RAG-ready chunks from extracted document markdown. Header-aware, token-sized."""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TARGET_TOKENS = 1000
DEFAULT_OVERLAP_TOKENS = 120


def approx_tokens(text: str) -> int:
    """Approximate token count using chars/4 heuristic."""
    return max(0, (len(text) + 3) // 4)


def iter_sections(markdown: str) -> Iterable[tuple[str, str]]:
    """
    Split markdown by headers (# .. ######). Yields (section_path, section_text).
    section_path is like "H1 > H2 > H3" (header titles joined by " > ").
    Section text includes the header line(s) and content up to the next same-or-higher-level header.
    """
    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    lines = markdown.split("\n")
    current_path: list[tuple[int, str]] = []  # (level, title) for each header level
    current_section_lines: list[str] = []
    current_level = 0

    def flush_section() -> tuple[str, str] | None:
        if not current_section_lines:
            return None
        path_str = " > ".join(t for _, t in current_path) if current_path else ""
        text = "\n".join(current_section_lines).strip()
        if not text:
            return None
        return path_str, text

    for line in lines:
        m = header_pattern.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            # Flush previous section
            out = flush_section()
            if out is not None:
                yield out
            # Update path: pop until we're at a higher or same level parent
            while current_path and current_path[-1][0] >= level:
                current_path.pop()
            current_path.append((level, title))
            current_section_lines = [line]
            current_level = level
        else:
            current_section_lines.append(line)

    out = flush_section()
    if out is not None:
        yield out


def split_to_token_windows(
    text: str,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[str]:
    """
    Split text into overlapping token-sized windows. Splits at paragraph boundaries
    (blank lines) when possible to keep tables/paragraphs intact.
    """
    if not text or not text.strip():
        return []
    if approx_tokens(text) <= target_tokens:
        return [text.strip()] if text.strip() else []

    step = max(1, target_tokens - overlap_tokens)
    # Split into paragraphs (blank-line separated)
    paragraphs = re.split(r"\n\s*\n", text)
    # Build windows by appending paragraphs until we're near target_tokens, then start new window with overlap
    windows: list[str] = []
    current: list[str] = []
    current_tokens = 0
    overlap_paragraphs: list[str] = []

    for para in paragraphs:
        if not para.strip():
            continue
        pt = approx_tokens(para)
        if current_tokens + pt > target_tokens and current:
            # Emit window
            window_text = "\n\n".join(current).strip()
            if window_text:
                windows.append(window_text)
            # Keep last few paragraphs for overlap (by token count)
            overlap_paragraphs = []
            overlap_so_far = 0
            for p in reversed(current):
                overlap_paragraphs.insert(0, p)
                overlap_so_far += approx_tokens(p)
                if overlap_so_far >= overlap_tokens:
                    break
            current = overlap_paragraphs.copy()
            current_tokens = sum(approx_tokens(p) for p in current)
        current.append(para)
        current_tokens += pt

    if current:
        window_text = "\n\n".join(current).strip()
        if window_text:
            windows.append(window_text)
    return windows


def generate_chunks_jsonl(
    document_md_path: str | Path,
    output_path: str | Path,
    doc_id: str,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> int:
    """
    Read document markdown, chunk by headers then token windows, write lean JSONL.
    Schema: {"id": "...", "text": "...", "meta": {"doc_id": "...", "section": "..."}}
    Returns number of chunks written.
    """
    path = Path(document_md_path)
    out = Path(output_path)
    if not path.exists():
        logger.warning("Document path does not exist: %s", path)
        return 0

    markdown = path.read_text(encoding="utf-8", errors="replace")
    chunk_index = 0
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(out, "w", encoding="utf-8") as f:
        for section_path, section_text in iter_sections(markdown):
            windows = split_to_token_windows(
                section_text,
                target_tokens=target_tokens,
                overlap_tokens=overlap_tokens,
            )
            for w in windows:
                if not w.strip():
                    continue
                chunk_id = f"{doc_id}_{chunk_index}"
                record = {
                    "id": chunk_id,
                    "text": w.strip(),
                    "meta": {"doc_id": doc_id, "section": section_path or ""},
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                chunk_index += 1

        # If no headers, treat whole doc as one section
        if chunk_index == 0 and markdown.strip():
            for w in split_to_token_windows(
                markdown,
                target_tokens=target_tokens,
                overlap_tokens=overlap_tokens,
            ):
                if not w.strip():
                    continue
                chunk_id = f"{doc_id}_{chunk_index}"
                record = {
                    "id": chunk_id,
                    "text": w.strip(),
                    "meta": {"doc_id": doc_id, "section": ""},
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                chunk_index += 1

    return chunk_index
