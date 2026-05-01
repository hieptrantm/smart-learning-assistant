from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from benchmark.bootstrap import BACKEND_DIR, OUTPUT_DIR
from benchmark.ingestion_pipeline import BenchmarkIngestionPipeline
from benchmark.llm.together_llm import TogetherLLM
from benchmark.models import BenchmarkJob, SubjectDescriptor
from benchmark.strategy_runner import BenchmarkStrategyRunner
from benchmark.subject_repository import SubjectRepository


DOWNLOADS_DIR = OUTPUT_DIR / "downloads"


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "subject"


def _get_field(payload: dict[str, Any], *aliases: str) -> Any:
    normalized = {_normalize_key(str(key)): value for key, value in payload.items()}
    for alias in aliases:
        key = _normalize_key(alias)
        if key in normalized:
            return normalized[key]
    raise ValueError(f"Missing required field. Expected one of: {', '.join(aliases)}")


def _get_optional_field(payload: dict[str, Any], *aliases: str) -> Any:
    normalized = {_normalize_key(str(key)): value for key, value in payload.items()}
    for alias in aliases:
        key = _normalize_key(alias)
        if key in normalized:
            return normalized[key]
    return None


def _parse_manifest_slots(slot_value: Any) -> dict[str, list[str]]:
    if slot_value is None:
        return {}

    if isinstance(slot_value, str):
        slot_args = [item for item in slot_value.split() if item]
    elif isinstance(slot_value, list):
        slot_args = [str(item).strip() for item in slot_value if str(item).strip()]
    else:
        raise ValueError("Manifest field 'slot' or 'slots' must be a string or a list of strings")

    free_slots: dict[str, list[str]] = {}
    for slot_arg in slot_args:
        if "=" not in slot_arg:
            raise ValueError(f"Invalid slot '{slot_arg}'. Expected day=09:00 or day=09:00-11:00")
        day, slot = slot_arg.split("=", 1)
        day = day.strip().lower()
        slot = slot.strip()
        if not day or not slot:
            raise ValueError(f"Invalid slot '{slot_arg}'. Expected day=09:00 or day=09:00-11:00")
        free_slots.setdefault(day, []).append(slot)
    return {key: sorted(value) for key, value in free_slots.items()}


def _parse_session_weights(payload: dict[str, Any]) -> list[float] | None:
    explicit_weights = _get_optional_field(payload, "session_weights", "session weights")
    if explicit_weights is not None:
        if not isinstance(explicit_weights, list) or not explicit_weights:
            raise ValueError("Manifest field 'session_weights' must be a non-empty list of positive numbers")
        weights = [float(value) for value in explicit_weights]
        if any(weight <= 0 for weight in weights):
            raise ValueError("Manifest field 'session_weights' must contain only positive numbers")
        return weights

    session_count = _get_optional_field(payload, "session_count", "session count", "num_sessions", "sessions")
    if session_count is None:
        return None

    count = int(session_count)
    if count <= 0:
        raise ValueError("Manifest field 'session_count' must be a positive integer")

    session_weight_value = _get_optional_field(payload, "session_weight", "session weight")
    weight = float(session_weight_value) if session_weight_value is not None else 1.0
    if weight <= 0:
        raise ValueError("Manifest field 'session_weight' must be a positive number")
    return [weight] * count


class BenchmarkRuntime:
    def __init__(self) -> None:
        self.llm_client = TogetherLLM()
        self.ingestion_pipeline = BenchmarkIngestionPipeline(llm_client=self.llm_client)
        self.strategy_runner = BenchmarkStrategyRunner(llm_client=self.llm_client)
        self.subject_repository = SubjectRepository()
        self._http_client: httpx.AsyncClient | None = None
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    async def warmup(self, include_ingestion: bool = True) -> None:
        if include_ingestion:
            self.ingestion_pipeline.warmup()

    async def close(self) -> None:
        self.ingestion_pipeline.close()
        if self._http_client is not None:
            await self._http_client.aclose()

    async def load_jobs_from_manifest(self, manifest_path: str) -> list[BenchmarkJob]:
        manifest_file = Path(manifest_path).expanduser()
        if not manifest_file.is_absolute():
            manifest_file = (Path.cwd() / manifest_file).resolve()
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
        items = payload.get("subjects", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise ValueError("Subjects manifest must be a JSON array or an object with a 'subjects' array")

        jobs: list[BenchmarkJob] = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"Subject entry #{index} must be a JSON object")
            slot_value = _get_optional_field(item, "slot", "slots", "free_slots", "free slots")
            subject = SubjectDescriptor(
                subject_id=int(_get_field(item, "id", "subject_id", "subject id")),
                subject_name=str(_get_field(item, "name", "subject_name", "subject name")).strip(),
                target_grade=float(_get_optional_field(item, "target_grade", "target grade")) if _get_optional_field(item, "target_grade", "target grade") is not None else None,
                start_date=_get_optional_field(item, "start_date", "start date"),
                end_date=_get_optional_field(item, "end_date", "end date"),
                free_slots=_parse_manifest_slots(slot_value),
            )
            pdf_source = _get_field(item, "pdf_url", "pdf url", "pdf", "pdf_path", "pdf path", "url")
            pdf_path = await self.resolve_pdf_source(str(pdf_source).strip(), subject, manifest_file.parent)
            jobs.append(
                BenchmarkJob(
                    subject=subject,
                    pdf_path=pdf_path,
                    session_weights=_parse_session_weights(item),
                )
            )
        return jobs

    async def resolve_pdf_source(self, pdf_source: str, subject: SubjectDescriptor, base_dir: Path) -> str:
        if pdf_source.startswith(("http://", "https://")):
            return await self._download_pdf(pdf_source, subject)
        return str(self._resolve_local_path(pdf_source, base_dir))

    def _resolve_local_path(self, pdf_source: str, base_dir: Path) -> Path:
        candidate = Path(pdf_source).expanduser()
        candidates = []
        if candidate.is_absolute():
            candidates.append(candidate)
        else:
            candidates.append((base_dir / candidate).resolve())
            candidates.append((BACKEND_DIR / candidate).resolve())
        for resolved in candidates:
            if resolved.exists():
                return resolved
        raise FileNotFoundError(f"PDF source not found: {pdf_source}")

    async def _download_pdf(self, pdf_url: str, subject: SubjectDescriptor) -> str:
        client = self._http_client
        if client is None:
            client = httpx.AsyncClient(follow_redirects=True, timeout=300)
            self._http_client = client

        url_hash = httpx.URL(pdf_url).path or pdf_url
        suffix = Path(httpx.URL(pdf_url).path).suffix or ".pdf"
        filename = f"{subject.subject_id}_{_slugify(subject.subject_name)}_{abs(hash(url_hash)) % 10_000_000:07d}{suffix}"
        target_path = DOWNLOADS_DIR / filename
        if target_path.exists():
            return str(target_path)

        response = await client.get(pdf_url)
        response.raise_for_status()
        target_path.write_bytes(response.content)
        return str(target_path)