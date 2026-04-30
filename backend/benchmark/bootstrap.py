from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_INGESTOR_DIR = BACKEND_DIR / "data-ingestor"
STUDY_PLANNER_DIR = BACKEND_DIR / "study-planner-api"
OUTPUT_DIR = BACKEND_DIR / "benchmark" / "output"
ENV_PATH = BACKEND_DIR / "benchmark" / ".env"


if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


def configure_paths() -> None:
    for path in (DATA_INGESTOR_DIR, STUDY_PLANNER_DIR):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


configure_paths()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
