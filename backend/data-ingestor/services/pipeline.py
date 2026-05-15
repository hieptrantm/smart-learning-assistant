"""
pipeline.py -- Background pipeline: save file → ingest → update subject ingest_status in DB.
After ingest completes, calls study-planner-api to trigger plan generation.
"""
import os
import traceback
import logging
from typing import Optional

import httpx

from database.db_utils import SessionLocal
from database.models import StudySubject
from rag_config import UPLOAD_DIR, DEFAULT_LANGUAGE, PLANNER_URL

logger = logging.getLogger(__name__)

# Injected from main.py after engine init
_chunking_engine = None
_indexing_engine = None
_jobs: dict = {}


def init_pipeline(chunking_engine, indexing_engine):
    global _chunking_engine, _indexing_engine, _jobs
    _chunking_engine = chunking_engine
    _indexing_engine = indexing_engine
    _jobs = {}
    

async def run_full_pipeline(
    subject_id: int,
    file_bytes: Optional[bytes],
    file_name: Optional[str],
    google_access_token: Optional[str] = None,
    google_refresh_token: Optional[str] = None,
):
    """
    Background task:
      1. Save PDF to disk
      2. Run chunking + indexing pipeline
      3. Update subject ingest_status in DB
      4. Call planner-api to trigger plan generation
    """
    from dataclasses import asdict

    db = SessionLocal()
    subject = None
    try:
        subject = db.query(StudySubject).filter_by(id=subject_id).first()
        if not subject:
            logger.error(f"[pipeline] Subject {subject_id} not found")
            return

        if not file_bytes or not file_name:
            subject.ingest_status = "completed"
            db.commit()
            _trigger_plan(subject_id, google_access_token, google_refresh_token)
            return

        # ── Step 1: Save file ──────────────────────────────────
        file_path = os.path.join(UPLOAD_DIR, file_name)
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        import os as _os
        job_id = f"{subject.name}_{file_name}_{_os.urandom(4).hex()}"
        subject.ingest_job_id = job_id
        subject.ingest_status = "processing"
        db.commit()

        # Track in-memory job dict (shared with /ingest endpoints)
        _jobs[job_id] = {"status": "queued", "file": file_name, "subject": subject.name}

        # ── Step 2: Chunking ──────────────────────────────────
        _jobs[job_id]["status"] = "chunking"
        ingest_result = _chunking_engine.run_pipeline(file_path, subject.name, DEFAULT_LANGUAGE)
        raw_chunks = ingest_result.chunks

        if not raw_chunks:
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["result"] = asdict(ingest_result)
            _jobs[job_id]["warning"] = "No raw chunks produced; skipping indexing."
            subject.ingest_status = "completed"
            db.commit()
            _trigger_plan(subject_id, google_access_token, google_refresh_token)
            return

        # ── Step 3: Indexing ──────────────────────────────────
        _jobs[job_id]["status"] = "indexing"
        index_stats = await _indexing_engine.ingest(
            chunks=raw_chunks,
            subject_id=subject.name,
            save_to_neo4j=True,
            recreate=False,
        )

        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = {**asdict(ingest_result), "index_stats": index_stats}

        subject.ingest_status = "completed"
        db.commit()

        # ── Step 4: Trigger plan generation ───────────────────
        _trigger_plan(subject_id, google_access_token, google_refresh_token)

    except Exception as e:
        logger.error(f"[pipeline] subject_id={subject_id} failed: {e}")
        traceback.print_exc()
        if subject:
            subject.ingest_status = "failed"
            db.commit()
    finally:
        db.close()
        # Clean up uploaded file
        if file_name:
            fp = os.path.join(UPLOAD_DIR, file_name)
            if os.path.exists(fp):
                os.remove(fp)


def _trigger_plan(subject_id: int, google_access_token: Optional[str], google_refresh_token: Optional[str]):
    """Fire-and-forget HTTP call to study-planner-api to generate study plan."""
    try:
        payload = {}
        if google_access_token:
            payload["google_access_token"] = google_access_token
        if google_refresh_token:
            payload["google_refresh_token"] = google_refresh_token

        with httpx.Client(timeout=10) as client:
            client.post(
                f"{PLANNER_URL}/subjects/{subject_id}/generate-plan",
                json=payload,
            )
    except Exception as e:
        logger.warning(f"[pipeline] Could not trigger plan for subject {subject_id}: {e}")
