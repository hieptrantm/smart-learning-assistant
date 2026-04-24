"""
engine.py – Full ingestion pipeline:
  PDF → structured JSON → classify/extract → VLM for figures/formulas
  → merge → normalize raw_chunks → multi-level indexing
      (raw chunks + Knowledge Graph → low-level + high-level → Qdrant).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field

from ingestor.pdf_parser import (
    parse_pdf_to_json,
    extract_text_from_box,
    filter_to_first_header,
    extract_context_of_figure,
)
# from services.vlm_service import get_b64_image, describe_visual
from services.vlm_service import VLMService
from ingestor.chunker import merge_blocks, create_raw_chunks

# Add parent dir so we can import indexing_pipeline & llm_service at the
# data-ingestor package level.
_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)
    
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    subject: str
    file_name: str
    total_pages: int = 0
    total_boxes_processed: int = 0
    figures_extracted: int = 0
    formulas_extracted: int = 0
    raw_chunks_created: int = 0
    chunks: list[dict] = field(default_factory=list)

def normalize_class_name(data: dict) -> dict:
    for page in data.get("pages", []):
        for box in page.get("boxes", []):
            if "boxclass" in box:
                if box["boxclass"] == "page-header" and isinstance(box['textlines'], list) and len(box['textlines']) > 0:
                    box["boxclass"] = "section-header"
                    
    return data
                    

class ChunkingEngine:
    def __init__(self, vlm_service=None):
        self.vlm_service = vlm_service or VLMService(os.getenv("TOGETHER_API_KEY"), os.getenv("VLM_MODEL_ID"))
    
    def run_pipeline(
        self,
        file_path: str,
        subject: str,
        language: str = "Vietnamese",
        *args, **kwargs
        
    ) -> dict:
        """Execute the full PDF ➜ multi-level Qdrant ingestion pipeline.

        Flow
        ----
        1. Parse PDF to structured JSON.
        2. Trim leading pages before first meaningful header.
        3. Walk boxes – extract text / call VLM for figures & formulas.
        4. Merge adjacent blocks.
        5. **Normalize** flat boxes → ``raw_chunk`` dicts
        (sequential IDs, chapter from level-1 header, section title).
        6. **Multi-level indexing** via ``MultiLevelIngestionPipeline``:
        - Index raw chunks
        - Extract Knowledge Graph (entities + relations)
        - Build & index low-level points (from KG relations)
        - Build & index high-level points (merged KG entities)

        Args:
            file_path:             Absolute path to the uploaded PDF.
            subject:               Name of the academic subject (stored in metadata).
            language:              Language for VLM descriptions.
            save_kg_to_json:       Optional path to persist extracted KG as JSON.
            recreate_collections:  If True, drop & recreate all Qdrant collections.

        Returns:
            IngestResult dataclass with stats about the run.
        """
        file_name = os.path.basename(file_path)
        result = IngestResult(subject=subject, file_name=file_name)

        # ── Step 1: Parse PDF ──
        logger.info(f"Parsing PDF: {file_name}")
        data = normalize_class_name(parse_pdf_to_json(file_path))
        logger.info(json.dumps(data, indent=2, ensure_ascii=False)[:1000] + " ...")

        data = filter_to_first_header(data)

        flat: list[dict] = []

        logger.info(f"Processing {len(data['pages'])} pages and their boxes...")
        for page_idx, page in enumerate(data["pages"]):
            boxes = page.get("boxes", [])
            for box_idx, box in enumerate(boxes):
                bc = box.get("boxclass", "")
                result.total_boxes_processed += 1
                text = ""

                if bc in ("picture", "formula"):
                    # Caption from the next box
                    next_box = boxes[box_idx + 1] if box_idx + 1 < len(boxes) else None
                    caption = extract_text_from_box(next_box)
                    logger.info(f"Processing visual box p{page_idx} b{box_idx} with caption: {caption}")
                    context = extract_context_of_figure(data, page, page_idx, box_idx, num_boxes=3)
                    logger.info(f"Context for visual box p{page_idx} b{box_idx}: {context}")
                    encoded = self.vlm_service.get_b64_image(file_path, page_idx, box)
                    logger.info(f"Encoded visual box p{page_idx} b{box_idx}: {encoded[:30]}...")  # Log start of base64 string
                    if encoded:
                        box_type = "FIGURE" if bc == "picture" else "FORMULA"
                        try:
                            text = self.vlm_service.describe_visual(encoded, caption, context, box_type, language)
                            if bc == "picture":
                                result.figures_extracted += 1
                            else:
                                result.formulas_extracted += 1
                        except Exception as e:
                            err = f"VLM error p{page_idx} b{box_idx}: {e}"
                            logger.error(err)
                            result.errors.append(err)
                            text = caption  # fallback

                elif bc in ("page-footer"):
                    continue

                elif bc in ("text", "list-item", "table", "caption", "section-header"):
                    text = extract_text_from_box(box)

                else:
                    continue

                if text:
                    flat.append({
                        "page_index": page_idx,
                        "box_index": box_idx,
                        "context": text,
                        "boxclass": bc,
                    })

        # ── Step 4: Merge adjacent blocks ──
        flat = merge_blocks(flat)
        
        # ── Step 5: Normalize into raw_chunk format ──
        # Each raw_chunk gets:
        #   raw_chunk_id  – "<subject>_chunk_01", …
        #   chapter       – current level-1 section-header text
        #   title         – sub-section header text
        #   text          – accumulated body content
        raw_chunks = create_raw_chunks(flat, subject=subject)
        os.makedirs("output", exist_ok=True)
        with open(f"output/{subject}_raw_chunks.json", "w", encoding="utf-8") as f:
            json.dump(raw_chunks, f, ensure_ascii=False, indent=2)
        result.raw_chunks_created = len(raw_chunks)
        result.chunks = raw_chunks
        logger.info(f"Created {len(raw_chunks)} raw chunks from {file_name}")

        if not raw_chunks:
            logger.info("No raw chunks produced – skipping indexing.")
            return result
        
        return result