import os
import shutil
import traceback
from dataclasses import asdict

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from rag_config import APP_HOST, APP_PORT, UPLOAD_DIR, DEFAULT_LANGUAGE, DATABASE_URL
from ingestor.engine import ChunkingEngine
# from ingestor.vector_store import search as qdrant_search, ensure_collection
from indexing.engine import IndexingEngine
from datetime import date as date_type

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, SparseVectorParams
from qdrant_client.http import models as qdrant_models
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_qdrant import QdrantVectorStore, FastEmbedSparse

from services.llm_service import LLMService
from services.vlm_service import VLMService
from langchain_together import ChatTogether
from sqlalchemy.orm import Session
from typing import Optional
import json

from rag_config import (
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    LLM_MODEL_ID,
    VLM_MODEL_ID,
    TOGETHER_API_KEY,
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
    QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_URL,
    LOWLEVEL_COLLECTION_NAME, HIGHLEVEL_COLLECTION_NAME, RAW_CHUNKS_COLLECTION_NAME
)

from database.db_utils import engine, Base, get_db
from database.models import StudySubject, SubjectDocument, SubjectFreeSlot
from database.auth import get_current_user_id
from services.pipeline import run_full_pipeline, init_pipeline

Base.metadata.create_all(bind=engine)


# ── App init ──────────────────────────────────────────────────
app = FastAPI(
    title="Data Ingestor Service",
    description="Upload academic PDFs → parse, OCR, chunk, embed & index into Qdrant.",
    version="1.0.0",
    root_path="/ingest",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("output", exist_ok=True)

# Singleton init 
neo4j_client = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)

dense_embedding_client = HuggingFaceBgeEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={"trust_remote_code": True}
)

llm_client = ChatTogether(api_key=TOGETHER_API_KEY, model=LLM_MODEL_ID)
llm_client = LLMService(client=llm_client)

vlm_client = ChatTogether(api_key=TOGETHER_API_KEY, model=VLM_MODEL_ID)
vlm_service = VLMService(client=vlm_client)



chunking_engine = ChunkingEngine(vlm_service)
indexing_engine = IndexingEngine(
    neo4j_client=neo4j_client,
    dense_emb_client=dense_embedding_client,
    llm=llm_client
)
    


# # ── Events ────────────────────────────────────────────────────
# @app.on_event("startup")
# async def startup():
#     """Ensure all Qdrant collections (raw, low-level, high-level) exist on boot."""
#     try:
#         # Legacy single collection
#         ensure_collection()
#     except Exception as e:
#         print(f"[startup] Could not ensure legacy collection: {e}")


ALLOWED_EXTENSIONS = {".pdf"}

def _validate_file(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Only PDF is supported.",
        )
    return ext


def _save_upload(file: UploadFile) -> str:
    """Save the uploaded file to disk and return its path."""
    dest = os.path.join(UPLOAD_DIR, file.filename)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest

# Wire pipeline service with singleton engines
init_pipeline(chunking_engine, indexing_engine)


async def _run_ingest_job(job_id: str, file_path: str, subject: str, language: str):
    """Background task that runs the full multi-level pipeline and stores the result."""
    try:
        # Step 1 - chunking
        ingest_result = chunking_engine.run_pipeline(
            file_path,
            subject,
            language,
        )
        raw_chunks = ingest_result.chunks
        
        if not raw_chunks:
            return
        
        # Step 2 - indexing (async for concurrent profiling)
        index_stats = await indexing_engine.ingest(
            chunks=raw_chunks,
            subject_id=subject,
            save_to_neo4j=True,
            recreate=False,
        )

    except Exception as e:
        print(f"[job:{job_id}] Failed: {e}")
    finally:
        # Clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)


# ── Endpoints ─────────────────────────────────────────────────

@app.post("/ingest", summary="Upload & ingest a PDF into vector store")
async def ingest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to ingest"),
    subject: str = Form(..., description="Subject / course name"),
    language: str = Form(DEFAULT_LANGUAGE, description="Language for VLM output"),
):
    _validate_file(file)
    file_path = _save_upload(file)

    job_id = f"{subject}_{file.filename}_{os.urandom(4).hex()}"

    background_tasks.add_task(_run_ingest_job, job_id, file_path, subject, language)

    return JSONResponse(
        status_code=202,
        content={
            "message": "Ingestion started",
            "job_id": job_id,
            "file": file.filename,
            "subject": subject,
        },
    )
    


# ── Subject helpers ───────────────────────────────────────────

def _subject_to_out(s: StudySubject) -> dict:
    free_time: dict = {}
    for slot in s.free_slots:
        if slot.day_of_week not in free_time:
            free_time[slot.day_of_week] = []
        free_time[slot.day_of_week].append(slot.time_slot)
    for day in free_time:
        free_time[day].sort()
    return {
        "id": s.id,
        "user_id": s.user_id,
        "name": s.name,
        "emoji": s.emoji,
        "target_grade": float(s.target_grade or 7),
        "end_date": s.end_date.isoformat() if s.end_date else None,
        "status": s.status,
        "ingest_status": s.ingest_status,
        "plan_status": s.plan_status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "documents": [
            {"id": d.id, "file_name": d.file_name, "file_size": d.file_size, "mime_type": d.mime_type}
            for d in s.documents
        ],
        "free_time": free_time,
    }


# ── Subject endpoints ─────────────────────────────────────────

@app.get("/subjects", summary="List all subjects for current user")
def list_subjects(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    subjects = (
        db.query(StudySubject)
        .filter_by(user_id=user_id)
        .order_by(StudySubject.created_at.desc())
        .all()
    )
    return [_subject_to_out(s) for s in subjects]


@app.post("/subjects", summary="Create subject + start background ingest pipeline")
async def create_subject(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    emoji: str = Form("📚"),
    target_grade: float = Form(7.0),
    end_date: str = Form(None),
    free_time: str = Form("{}"),
    file: Optional[UploadFile] = File(None),
    google_access_token: str = Form(None),
    google_refresh_token: str = Form(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    print(f"Google access token: {google_access_token}")
    print(f"Google refresh token: {google_refresh_token}")

    subject = StudySubject(
        user_id=user_id,
        name=name,
        emoji=emoji,
        target_grade=target_grade,
        end_date=date_type.fromisoformat(end_date) if end_date else None,
        status="active",
        ingest_status="pending",
        plan_status="pending",
    )
    db.add(subject)
    db.flush()

    free_time_dict = json.loads(free_time) if isinstance(free_time, str) else free_time
    for day, slots in free_time_dict.items():
        for slot in slots:
            db.add(SubjectFreeSlot(subject_id=subject.id, day_of_week=day, time_slot=slot))

    file_bytes = None
    file_name = None
    if file and file.filename:
        file_bytes = await file.read()
        file_name = file.filename
        db.add(SubjectDocument(
            subject_id=subject.id,
            file_name=file.filename,
            file_size=f"{len(file_bytes) / (1024 * 1024):.1f} MB",
            mime_type=file.content_type,
        ))

    db.commit()
    db.refresh(subject)
    
    print()

    background_tasks.add_task(
        run_full_pipeline,
        subject.id,
        file_bytes,
        file_name,
        google_access_token,
        google_refresh_token,
    )

    return _subject_to_out(subject)


@app.put("/subjects/{subject_id}", summary="Update subject info")
def update_subject(
    subject_id: int,
    name: str = Form(None),
    emoji: str = Form(None),
    target_grade: float = Form(None),
    end_date: str = Form(None),
    free_time: str = Form(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    subject = db.query(StudySubject).filter_by(id=subject_id, user_id=user_id).first()
    if not subject:
        raise HTTPException(404, "Subject not found")

    if name is not None:
        subject.name = name
    if emoji is not None:
        subject.emoji = emoji
    if target_grade is not None:
        subject.target_grade = target_grade
    if end_date is not None:
        from datetime import date as date_type
        subject.end_date = date_type.fromisoformat(end_date) if end_date else None
    if free_time is not None:
        db.query(SubjectFreeSlot).filter_by(subject_id=subject.id).delete()
        ft = json.loads(free_time) if isinstance(free_time, str) else free_time
        for day, slots in ft.items():
            for slot in slots:
                db.add(SubjectFreeSlot(subject_id=subject.id, day_of_week=day, time_slot=slot))

    db.commit()
    db.refresh(subject)
    return _subject_to_out(subject)


@app.delete("/subjects/{subject_id}", summary="Delete a subject and all associated data")
def delete_subject(
    subject_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    subject = db.query(StudySubject).filter_by(id=subject_id, user_id=user_id).first()
    if not subject:
        raise HTTPException(404, "Subject not found")
    db.delete(subject)
    db.commit()
    return {"success": True, "id": subject_id}


@app.post("/ingest/sync", summary="Upload & ingest a PDF (synchronous, waits for result)")
async def ingest_sync(
    file: UploadFile = File(..., description="PDF file to ingest"),
    subject: str = Form(..., description="Subject / course name"),
    language: str = Form(DEFAULT_LANGUAGE, description="Language for VLM output"),
):
    _validate_file(file)
    file_path = _save_upload(file)

    try:
        result = chunking_engine.run_pipeline(
            file_path,
            subject,
            language,
            recreate_collections=False,
        )
        return JSONResponse(content=asdict(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


# @app.get("/search", summary="Semantic search across indexed documents (legacy single collection)")
# async def search_endpoint(
#     query: str = Query(..., description="Search query"),
#     subject: str = Query(None, description="Filter by subject"),
#     k: int = Query(10, ge=1, le=50, description="Number of results"),
# ):
#     try:
#         results = qdrant_search(query, subject=subject, k=k)
#         return {
#             "query": query,
#             "subject": subject,
#             "results": [
#                 {
#                     "content": doc.page_content[:500],
#                     "score": round(score, 4),
#                     "metadata": doc.metadata,
#                 }
#                 for doc, score in results
#             ],
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @app.get("/search/multilevel", summary="Multi-level search across raw / low / high collections")
# async def search_multilevel(
#     query: str = Query(..., description="Search query"),
#     k: int = Query(3, ge=1, le=20, description="Results per level"),
# ):
#     """Search all three index levels and return combined results."""
#     try:
#         builder = MultiLevelIndexBuilder()
#         # print(f"[debug] Running multi-level search for query: '{query}' with k={k} per level")
#         results = builder.search_all_levels(query, top_k_per_level=k)
#         # print(f"[debug] Multi-level search results: {results}")
#         return {"query": query, "results": results}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @app.get("/collections/info", summary="Get statistics for all Qdrant collections")
# async def collections_info():
#     try:
#         builder = MultiLevelIndexBuilder()
#         return builder.get_all_collection_info()
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", summary="Health check")
async def health():
    return {"status": "ok", "service": "data-ingestor"}


# ── Run directly ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=APP_HOST, port=APP_PORT)
