from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine

from app.config import CORS_ORIGINS, DATABASE_URL
from app.controllers.auth_controller import auth_router
from app.controllers.detect_controller import detect_router

Base = declarative_base()
engine = create_engine(DATABASE_URL)


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Auth Service", root_path="/auth")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(detect_router)


@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)