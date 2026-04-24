"""
pdf_parser.py – Extract structured JSON from PDF using PyMuPDF layout analysis.
"""

import json
import re

# layout engine MUST be activated before importing pymupdf4llm
import pymupdf.layout
pymupdf.layout.activate()

import pymupdf
import pymupdf4llm

from rag_config import _LEVEL1, _LEVEL2, _LEVEL3


def parse_pdf_to_json(file_path: str) -> dict:
    """Open a PDF and return the structured JSON dict from pymupdf4llm."""
    try:
        doc = pymupdf.open(file_path)
        json_str = pymupdf4llm.to_json(doc)
    except Exception as e:
        raise RuntimeError(f"Failed to parse PDF: {e}") from e
    return json.loads(json_str)


# ── Text helpers ──────────────────────────────────────────────

def extract_text_from_box(box: dict | None) -> str:
    """Return plain text from a box (handles tables specially)."""
    if box is None:
        return ""
    if box.get("boxclass") == "table":
        md = box.get("table", {}).get("markdown", "")
        return f"[TABLE]\n{md}\n[/TABLE]"
    text = ""
    try:
        for line in box["textlines"]:
            for span in line["spans"]:
                text += span["text"].strip() + " "
    except Exception:
        return ""
    return text.strip()


def classify_heading_level(text: str) -> int:
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


# ── Data filtering ────────────────────────────────────────────

def filter_to_first_header(data: dict) -> dict:
    """Trim pages/boxes before the first level-1 or level-2 section header."""
    target_page = target_box = None
    for pi, page in enumerate(data["pages"]):
        for bi, box in enumerate(page["boxes"]):
            if box.get("boxclass") == "section-header":
                level = classify_heading_level(extract_text_from_box(box))
                if level in (1, 2):
                    target_page, target_box = pi, bi
                    break
        if target_page is not None:
            break

    if target_page is not None:
        data["pages"] = data["pages"][target_page:]
        data["pages"][0]["boxes"] = data["pages"][0]["boxes"][target_box:]
    return data


def extract_context_of_figure(data: dict, page: dict, page_index: int,
                               fig_index: int, num_boxes: int = 3) -> str:
    """Gather context text from boxes preceding a figure/formula box."""
    available = {"text", "page-header", "section-header", "list-item", "table"}
    parts: list[str] = []
    start = fig_index - num_boxes
    for i in range(start, fig_index):
        if i < 0 and page_index > 0:
            prev_boxes = data["pages"][page_index - 1]["boxes"]
            if abs(i) - 1 < len(prev_boxes):
                box = prev_boxes[i]
                if box.get("boxclass") in available:
                    parts.append(extract_text_from_box(box))
        elif 0 <= i < len(page["boxes"]):
            box = page["boxes"][i]
            if box.get("boxclass") in available:
                parts.append(extract_text_from_box(box))
    return " ".join(parts).strip()


# Test function
if __name__ == "__main__":
    file_path = "KTVM.pdf"
    
    data = parse_pdf_to_json(file_path)
    with open("parsed_output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    # print(json.dumps(data, indent=2, ensure_ascii=False))