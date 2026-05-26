import json
import os
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPORT_PATH = Path(
    os.getenv(
        "DATA_INGESTOR_REPORT_PATH",
        str(BACKEND_DIR / "output" / "data_ingestor_simple_flow_report.json"),
    )
)

INGESTOR_BASE_URL = os.getenv("INGESTOR_BASE_URL", "http://localhost:8005/ingest").rstrip("/")
AUTH_BASE_URL = os.getenv("AUTH_BASE_URL", "http://localhost:8005/auth").rstrip("/")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/")
NEO4J_URL = os.getenv("NEO4J_URL", "http://localhost:7474").rstrip("/")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testtest")

POLL_TIMEOUT_SECONDS = int(os.getenv("INGEST_POLL_TIMEOUT_SECONDS", "300"))
POLL_INTERVAL_SECONDS = float(os.getenv("INGEST_POLL_INTERVAL_SECONDS", "5"))
SCALE_USERS = int(os.getenv("SCALE_USERS", "100"))
REQUESTS_PER_USER = int(os.getenv("REQUESTS_PER_USER", "1"))
STRICT_BACKEND_CHECKS = os.getenv("STRICT_BACKEND_CHECKS", "false").lower() == "true"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _build_pdf_bytes(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{idx} 0 obj\n".encode("ascii"))
        content.extend(obj)
        content.extend(b"\nendobj\n")

    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(content)


def _write_report(report: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _request(client: httpx.Client, report: dict, method: str, url: str, **kwargs) -> httpx.Response:
    step_name = kwargs.pop("step_name", f"{method} {url}")
    started = time.perf_counter()
    response = client.request(method, url, **kwargs)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    report["steps"].append(
        {
            "name": step_name,
            "method": method,
            "url": url,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "response_text": response.text[:1000] if response.status_code >= 400 else "",
        }
    )
    return response


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    index = int(round((len(values) - 1) * percentile))
    return round(values[index], 2)


def _scale_health_check(report: dict) -> None:
    latencies = []
    status_codes = []
    errors = 0
    total_requests = SCALE_USERS * REQUESTS_PER_USER
    started = time.perf_counter()

    def hit_health() -> tuple[float | None, int | None, str | None]:
        try:
            with httpx.Client(timeout=10) as client:
                req_started = time.perf_counter()
                response = client.get(f"{INGESTOR_BASE_URL}/health")
                return round((time.perf_counter() - req_started) * 1000, 2), response.status_code, None
        except Exception as exc:
            return None, None, str(exc)

    with ThreadPoolExecutor(max_workers=SCALE_USERS) as executor:
        futures = [executor.submit(hit_health) for _ in range(total_requests)]
        for future in as_completed(futures):
            latency_ms, status_code, error = future.result()
            if latency_ms is not None:
                latencies.append(latency_ms)
            if status_code is not None:
                status_codes.append(status_code)
            if error or status_code != 200:
                errors += 1

    elapsed = time.perf_counter() - started
    report["metrics"]["scale_health_check"] = {
        "users": SCALE_USERS,
        "requests_per_user": REQUESTS_PER_USER,
        "total_requests": total_requests,
        "success_count": total_requests - errors,
        "error_count": errors,
        "error_rate": round(errors / total_requests, 4) if total_requests else 0,
        "requests_per_second": round(total_requests / elapsed, 2) if elapsed else None,
        "latency_ms": {
            "min": round(min(latencies), 2) if latencies else None,
            "avg": round(statistics.mean(latencies), 2) if latencies else None,
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "max": round(max(latencies), 2) if latencies else None,
        },
        "status_codes": status_codes,
    }


def _create_access_token(client: httpx.Client, report: dict) -> str:
    suffix = uuid.uuid4().hex[:10]
    email = f"ingestor_test_{suffix}@learning.local"
    password = "TestAuto12345"

    register_response = _request(
        client,
        report,
        "POST",
        f"{AUTH_BASE_URL}/register",
        json={"username": f"ingestor_test_{suffix}", "email": email, "password": password},
        timeout=15,
        step_name="auth_register",
    )
    report["checks"]["auth_register_status"] = register_response.status_code
    register_response.raise_for_status()

    login_response = _request(
        client,
        report,
        "POST",
        f"{AUTH_BASE_URL}/login",
        json={"email": email, "password": password, "provider": "email"},
        timeout=15,
        step_name="auth_login",
    )
    report["checks"]["auth_login_status"] = login_response.status_code
    login_response.raise_for_status()

    token = login_response.json()["access_token"]
    report["checks"]["auth_token_obtained"] = bool(token)
    return token


def _poll_ingest_status(client: httpx.Client, report: dict, token: str, subject_id: int) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    poll_count = 0
    started = time.perf_counter()
    last_payload = {}

    while time.monotonic() < deadline:
        poll_count += 1
        response = _request(
            client,
            report,
            "GET",
            f"{INGESTOR_BASE_URL}/subjects",
            headers=headers,
            timeout=20,
            step_name="poll_subject_status",
        )
        response.raise_for_status()
        subjects = response.json()
        last_payload = next((item for item in subjects if item.get("id") == subject_id), {})
        status = last_payload.get("ingest_status")

        if not last_payload:
            report["steps"][-1]["note"] = f"subject_id={subject_id} not found in list response"
        elif status in {"completed", "failed"}:
            break
        time.sleep(POLL_INTERVAL_SECONDS)

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    report["metrics"]["ingest_poll"] = {
        "poll_count": poll_count,
        "latency_ms": latency_ms,
        "final_status": last_payload.get("ingest_status"),
        "job_id": last_payload.get("ingest_job_id"),
    }
    return last_payload


def _check_qdrant(report: dict) -> None:
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"{QDRANT_URL}/collections")
        collections = response.json().get("result", {}).get("collections", []) if response.status_code == 200 else []
        report["checks"]["qdrant"] = {
            "reachable": response.status_code == 200,
            "status_code": response.status_code,
            "collection_count": len(collections),
            "collections": [item.get("name") for item in collections],
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except Exception as exc:
        report["checks"]["qdrant"] = {"reachable": False, "error": str(exc)}


def _check_neo4j(report: dict) -> None:
    started = time.perf_counter()
    query = {"statements": [{"statement": "MATCH (n) RETURN count(n) AS nodes"}]}
    try:
        with httpx.Client(timeout=10, auth=(NEO4J_USER, NEO4J_PASSWORD)) as client:
            response = client.post(f"{NEO4J_URL}/db/neo4j/tx/commit", json=query)
        payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        node_count = None
        if response.status_code == 200 and payload.get("results"):
            data = payload["results"][0].get("data", [])
            if data:
                node_count = data[0].get("row", [None])[0]
        report["checks"]["neo4j"] = {
            "reachable": response.status_code == 200,
            "status_code": response.status_code,
            "node_count": node_count,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except Exception as exc:
        report["checks"]["neo4j"] = {"reachable": False, "error": str(exc)}


@pytest.mark.integration
def test_data_ingestor_pdf_to_qdrant_neo4j_postgres_simple_flow():
    run_id = uuid.uuid4().hex[:8]
    subject_id = None
    report = {
        "run_id": run_id,
        "started_at_ms": _now_ms(),
        "config": {
            "ingestor_base_url": INGESTOR_BASE_URL,
            "auth_base_url": AUTH_BASE_URL,
            "qdrant_url": QDRANT_URL,
            "neo4j_url": NEO4J_URL,
            "poll_timeout_seconds": POLL_TIMEOUT_SECONDS,
            "scale_users": SCALE_USERS,
            "requests_per_user": REQUESTS_PER_USER,
            "strict_backend_checks": STRICT_BACKEND_CHECKS,
        },
        "checks": {},
        "metrics": {},
        "steps": [],
        "errors": [],
    }

    try:
        _scale_health_check(report)

        with httpx.Client(timeout=60) as client:
            token = _create_access_token(client, report)
            headers = {"Authorization": f"Bearer {token}"}
            subject_name = f"Simple Ingest Flow {run_id}"
            pdf_bytes = _build_pdf_bytes(
                "Algebra basics. Linear equations, variables, constants, and examples for indexing."
            )
            free_time = {"Monday": ["09:00"], "Wednesday": ["14:00"]}

            started = time.perf_counter()
            create_response = _request(
                client,
                report,
                "POST",
                f"{INGESTOR_BASE_URL}/subjects",
                headers=headers,
                data={
                    "name": subject_name,
                    "target_grade": "8.0",
                    "end_date": (date.today() + timedelta(days=30)).isoformat(),
                    "free_time": json.dumps(free_time),
                },
                files={
                    "file": (
                        f"simple-ingest-{run_id}.pdf",
                        pdf_bytes,
                        "application/pdf",
                    )
                },
                timeout=120,
                step_name="create_subject_with_pdf",
            )
            report["metrics"]["create_subject_latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            report["checks"]["create_subject_status"] = create_response.status_code
            create_response.raise_for_status()

            created_subject = create_response.json()
            subject_id = created_subject["id"]
            report["checks"]["postgres_subject_created"] = bool(subject_id)
            report["checks"]["postgres_document_created"] = bool(created_subject.get("documents"))
            report["checks"]["subject_id"] = subject_id
            report["checks"]["initial_ingest_status"] = created_subject.get("ingest_status")

            final_subject = _poll_ingest_status(client, report, token, subject_id)
            report["checks"]["final_subject"] = final_subject
            report["checks"]["ingest_completed"] = final_subject.get("ingest_status") == "completed"

            _check_qdrant(report)
            _check_neo4j(report)

            if subject_id is not None:
                delete_response = _request(
                    client,
                    report,
                    "DELETE",
                    f"{INGESTOR_BASE_URL}/subjects/{subject_id}",
                    headers=headers,
                    timeout=20,
                    step_name="cleanup_subject",
                )
                report["checks"]["cleanup_status"] = delete_response.status_code

        assert report["metrics"]["scale_health_check"]["error_count"] == 0
        assert report["checks"]["postgres_subject_created"] is True
        assert report["checks"]["postgres_document_created"] is True
        assert report["checks"]["ingest_completed"] is True

        if STRICT_BACKEND_CHECKS:
            assert report["checks"]["qdrant"]["reachable"] is True
            assert report["checks"]["qdrant"]["collection_count"] > 0
            assert report["checks"]["neo4j"]["reachable"] is True
            assert (report["checks"]["neo4j"]["node_count"] or 0) > 0

    except Exception as exc:
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        report["finished_at_ms"] = _now_ms()
        report["duration_ms"] = report["finished_at_ms"] - report["started_at_ms"]
        _write_report(report)
