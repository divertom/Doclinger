"""Stepper progress: dots connected by a line, stage names on top, times below."""
from __future__ import annotations

import streamlit as st

# Short labels for display above dots (no "Complete" – last stage is Chunking)
STAGE_LABELS = [
    "Starting",
    "Loading",
    "Converting (this will take long)",
    "Saving",
    "Chunking",
]


def stage_index(api_stage: str) -> int:
    """Map backend stage string to display index (0..5)."""
    api_stage = (api_stage or "").strip().lower()
    if "starting" in api_stage:
        return 0
    if "loading" in api_stage:
        return 1
    if "converting" in api_stage or "document converted" in api_stage or "generating" in api_stage:
        return 2
    if "saving" in api_stage:
        return 3
    if "chunking" in api_stage:
        return 4
    if "complete" in api_stage:
        return 5  # all done; stepper shows all 5 stages completed
    return 0


def render_stepper(
    current_stage: str,
    current_stage_elapsed_s: int,
    completed_times: dict[str, int],
) -> None:
    """
    Render a horizontal stepper: dots connected by a line (lighter base, darker when done/active).
    Stage name above each dot; below the line segment: completed time or in-progress elapsed.
    """
    idx = stage_index(current_stage)
    n = len(STAGE_LABELS)
    completed = [completed_times.get(STAGE_LABELS[i], None) for i in range(n)]

    # Blue theme: lighter when pending, dark when done (match "Drag and drop file here" feel)
    light_blue = "#93c5fd"
    dark_blue = "#1e40af"

    parts = []
    for i in range(n):
        is_done = i < idx
        is_current = i == idx
        dot_color = dark_blue if (is_done or is_current) else light_blue
        # Segment to the right of this dot (connector to next dot; include after last dot so Chunking has a line too)
        seg_color = dark_blue if is_done else light_blue
        # Font size 0.875rem (14px) to match Streamlit file uploader text
        parts.append('<div style="flex:1; min-width:0; display:flex; flex-direction:column; align-items:center;">')
        parts.append(f'<div style="font-size:0.875rem; font-weight:600; color:inherit; margin-bottom:6px;">{STAGE_LABELS[i]}</div>')
        # Row: dot + connecting line (thicker line)
        parts.append('<div style="display:flex; align-items:center; width:100%;">')
        parts.append(f'<div style="width:12px; height:12px; border-radius:50%; background:{dot_color}; flex-shrink:0;"></div>')
        parts.append(f'<div style="flex:1; height:5px; background:{seg_color}; min-width:8px;"></div>')
        # End dot after Chunking segment
        if i == n - 1:
            end_dot = dark_blue if idx >= n else light_blue
            parts.append(f'<div style="width:12px; height:12px; border-radius:50%; background:{end_dot}; flex-shrink:0;"></div>')
        parts.append("</div>")
        # Time under the segment (same font size as stages)
        parts.append('<div style="font-size:0.875rem; color:inherit; margin-top:4px; min-height:1.2em;">')
        if is_done and completed[i] is not None:
            parts.append(f"{completed[i]}s")
        elif is_current:
            parts.append(f"{current_stage_elapsed_s}s")
        parts.append("</div></div>")

    html = f"""
    <div style="display:flex; width:100%; gap:0; padding:12px 0 20px; font-family:system-ui,sans-serif;">
        {"".join(parts)}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
