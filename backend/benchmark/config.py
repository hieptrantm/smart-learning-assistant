from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BENCHMARK_DIR = Path(__file__).resolve().parent
load_dotenv(BENCHMARK_DIR / ".env", override=True)

BENCHMARK_LLM_MODEL = os.getenv("BENCHMARK_LLM_MODEL", "moonshotai/Kimi-K2-Instruct")
BENCHMARK_FALLBACK_LLM_MODEL = os.getenv("BENCHMARK_FALLBACK_LLM_MODEL", "openai/gpt-oss-120b")
BENCHMARK_TOGETHER_API_KEY = os.getenv("BENCHMARK_TOGETHER_API_KEY", os.getenv("TOGETHER_API_KEY", ""))
BENCHMARK_LLM_TEMPERATURE = float(os.getenv("BENCHMARK_LLM_TEMPERATURE", "0.3"))
BENCHMARK_MAX_TOKENS = int(os.getenv("BENCHMARK_MAX_TOKENS", "4096"))
BENCHMARK_LLM_MAX_RETRIES = int(os.getenv("BENCHMARK_LLM_MAX_RETRIES", "3"))
BENCHMARK_LLM_RETRY_BASE_SECONDS = float(os.getenv("BENCHMARK_LLM_RETRY_BASE_SECONDS", "2"))

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testtest")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/authdb")
