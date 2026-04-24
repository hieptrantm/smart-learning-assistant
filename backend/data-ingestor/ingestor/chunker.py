"""
chunker.py – Merge adjacent boxes, then split into section-based chunks.
Supports both plain-text chunk output and structured raw_chunk output
for the multi-level indexing pipeline.
"""

from __future__ import annotations

import re
from typing import Callable


# ── Heading-level classifier (inline, avoids circular import) ─────────

_LEVEL1 = [
    r"^(Chương|CHƯƠNG)\s+[IVXLCDM]+",
    r"^(Chương|CHƯƠNG)\s+\d+",
    r"^(Part|PART)\s+[IVXLCDM]+",
    r"^(Part|PART)\s+\d+",
    r"^(Chapter|CHAPTER)\s+[IVXLCDM]+",
    r"^(Chapter|CHAPTER)\s+\d+",
    r"^(Section|SECTION)\s+\d+",
    r"^(Phần|PHẦN)\s+[IVXLCDM]+",
    r"^(Phần|PHẦN)\s+\d+",
]
_LEVEL2 = [
    r"^[IVXLCDM]+\.",
    r"^[A-Z]\.",
    r"^[IVXLCDM]+\s+[A-Za-z]",
    r"^(§)\s+\d+",
]
_LEVEL3 = [
    r"^\d+\.",
    r"^\d+\.\d+",
    r"^\d+\s+[A-Za-z]",
]


def _classify_heading_level(text: str) -> int:
    """Return heading level 1-3, or 0 when no hierarchy detected."""
    text = text.strip()
    for p in _LEVEL1:
        if re.match(p, text, re.IGNORECASE):
            return 1
    for p in _LEVEL2:
        if re.match(p, text):
            return 2
    for p in _LEVEL3:
        if re.match(p, text):
            return 3
    return 0


def _merge_consecutive(data: list[dict], target_class: str) -> list[dict]:
    """Merge consecutive boxes of *target_class* into one entry."""
    to_delete: set[int] = set()
    for idx in range(1, len(data)):
        if (data[idx]["boxclass"] == target_class
                and data[idx - 1]["boxclass"] == target_class):
            prev = data[idx - 1]["context"]
            curr = data[idx]["context"]
            seen: set[str] = set()
            merged_lines: list[str] = []
            for line in (prev + "\n" + curr).split("\n"):
                line = line.strip()
                if line and line not in seen:
                    merged_lines.append(line)
                    seen.add(line)
            data[idx]["context"] = "\n".join(merged_lines)
            to_delete.add(idx - 1)
    return [item for i, item in enumerate(data) if i not in to_delete]


def merge_blocks(data: list[dict]) -> list[dict]:
    """Merge consecutive section-headers and consecutive text blocks."""
    data = _merge_consecutive(data, "section-header")
    data = _merge_consecutive(data, "text")
    return data


def create_chunks(data: list[dict]) -> list[str]:
    """Split flat box list into chunks — one chunk per section."""
    chunks: list[str] = []
    current = ""

    for item in data:
        ctx = item.get("context", "").strip()
        if item["boxclass"] == "section-header":
            if current:
                chunks.append(current.strip())
            current = ctx + "\n\n"
        elif current:
            if ctx:
                current += ctx + "\n\n"

    if current:
        chunks.append(current.strip())
    return chunks


# ── Structured raw_chunk creation for multi-level indexing ────────────

def create_raw_chunks(
    data: list[dict],
    subject: str = "doc",
    classify_fn: Callable[[str], int] | None = None,
) -> list[dict]:
    """Convert flat box list into structured raw_chunk dicts.

    Each chunk follows the ``raw_chunk.json`` schema::

        {
            "raw_chunk_id": "<subject>_chunk_01",
            "chapter": "Chương I: …",      # current level-1 header
            "title": "Khái niệm vật chất", # section title (level 2/3 or 0)
            "text": "…"                     # accumulated body text
        }

    The function:
    1. Tracks the current level-1 section-header as **chapter**.
    2. Every time a sub-section header (level ≥ 2 or unclassified) appears
       it flushes the previous chunk and starts a new one.
    3. Non-header boxes are appended to the current chunk's text.
    4. Assigns sequential IDs: ``<subject>_chunk_01``, ``_chunk_02``, …

    Args:
        data:        Flat list from ``merge_blocks`` (keys: context, boxclass).
        subject:     Prefix for chunk IDs.
        classify_fn: Optional heading-level classifier.  Falls back to the
                     built-in ``_classify_heading_level``.

    Returns:
        List of raw_chunk dicts ready for ``MultiLevelIngestionPipeline.ingest()``.
    """
    classify = classify_fn or _classify_heading_level

    raw_chunks: list[dict] = []
    current_chapter: str = ""
    current_title: str = ""
    current_text_parts: list[str] = []
    chunk_counter: int = 0

    def _flush() -> None:
        nonlocal chunk_counter
        text_body = "\n".join(current_text_parts).strip()
        if not text_body and not current_title:
            return
        chunk_counter += 1
        raw_chunks.append({
            "raw_chunk_id": f"{subject}_chunk_{chunk_counter:02d}",
            "chapter": current_chapter,
            "title": current_title,
            "text": text_body,
        })

    for item in data:
        ctx = item.get("context", "").strip()
        if not ctx:
            continue

        if item["boxclass"] == "section-header":
            level = classify(ctx)

            if level == 1:
                # Flush previous chunk (if any)
                _flush()
                current_chapter = ctx
                current_title = ""
                current_text_parts = []
            else:
                # level 2, 3, or 0 → new sub-section chunk
                _flush()
                current_title = ctx
                current_text_parts = []
        else:
            # Body content (text, list-item, table, caption, picture, formula)
            current_text_parts.append(ctx)

    # Flush the last accumulated chunk
    _flush()

    return raw_chunks
