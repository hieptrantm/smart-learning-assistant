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


SERVICE_DIR = Path(__file__).resolve().parents[1]
REPORT_PATH = Path(
    os.getenv(
        "STUDY_PLANNER_REPORT_PATH",
        str(SERVICE_DIR / "output" / "study_planner_generate_plan_report.json"),
    )
)

AUTH_BASE_URL = os.getenv("AUTH_BASE_URL", "http://localhost:8005/auth").rstrip("/")
INGESTOR_BASE_URL = os.getenv("INGESTOR_BASE_URL", "http://localhost:8005/ingest").rstrip("/")
PLANNER_BASE_URL = os.getenv("PLANNER_BASE_URL", "http://localhost:8005/planner").rstrip("/")

POLL_TIMEOUT_SECONDS = int(os.getenv("PLAN_POLL_TIMEOUT_SECONDS", "300"))
POLL_INTERVAL_SECONDS = float(os.getenv("PLAN_POLL_INTERVAL_SECONDS", "5"))
SCALE_USERS = int(os.getenv("SCALE_USERS", "3"))
REQUESTS_PER_USER = int(os.getenv("REQUESTS_PER_USER", "2"))
STRICT_PLAN_COMPLETION = os.getenv("STRICT_PLAN_COMPLETION", "true").lower() == "true"
EXISTING_SUBJECT_ID = os.getenv("STUDY_PLANNER_SUBJECT_ID")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write_report(report: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


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
            "response_text": response.text[:1500] if response.status_code >= 400 else "",
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
                response = client.get(f"{PLANNER_BASE_URL}/health")
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
    email = f"planner_test_{suffix}@learning.local"
    password = "TestAuto12345"

    register_response = _request(
        client,
        report,
        "POST",
        f"{AUTH_BASE_URL}/register",
        json={"username": f"planner_test_{suffix}", "email": email, "password": password},
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


def _create_subject_via_ingestor(client: httpx.Client, report: dict, token: str) -> int:
    run_id = report["run_id"]
    headers = {"Authorization": f"Bearer {token}"}
    free_time = {"mon": ["09:00"], "wed": ["14:00"], "fri": ["10:00"]}
    pdf_bytes = _build_pdf_bytes(
        "Study planner test document. Algebra foundations. Linear equations. Practice sessions."
    )

    response = _request(
        client,
        report,
        "POST",
        f"{INGESTOR_BASE_URL}/subjects",
        headers=headers,
        data={
            "name": f"Planner Generate Flow {run_id}",
            "target_grade": "8.0",
            "end_date": (date.today() + timedelta(days=30)).isoformat(),
            "free_time": json.dumps(free_time),
        },
        files={
            "file": (
                f"planner-generate-{run_id}.pdf",
                pdf_bytes,
                "application/pdf",
            )
        },
        timeout=60,
        step_name="create_subject_via_ingestor",
    )
    report["checks"]["create_subject_status"] = response.status_code
    response.raise_for_status()

    payload = response.json()
    report["checks"]["subject_created"] = bool(payload.get("id"))
    report["checks"]["subject_id"] = payload.get("id")
    report["checks"]["initial_subject"] = payload
    return int(payload["id"])


def _poll_data_ingestor_completed(client: httpx.Client, report: dict, token: str, subject_id: int) -> dict:
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
            step_name="poll_ingestor_subject",
        )
        response.raise_for_status()
        subjects = response.json()
        last_payload = next((item for item in subjects if item.get("id") == subject_id), {})
        status = last_payload.get("ingest_status")
        if status in {"completed", "failed"}:
            break
        time.sleep(POLL_INTERVAL_SECONDS)

    report["metrics"]["ingestor_poll"] = {
        "poll_count": poll_count,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "final_status": last_payload.get("ingest_status"),
    }
    return last_payload


def _poll_planner_status(client: httpx.Client, report: dict, token: str, subject_id: int) -> dict:
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
            f"{PLANNER_BASE_URL}/subjects/{subject_id}/status",
            headers=headers,
            timeout=20,
            step_name="poll_planner_status",
        )
        response.raise_for_status()
        last_payload = response.json()
        status = last_payload.get("plan_status")
        if status in {"completed", "failed"}:
            break
        time.sleep(POLL_INTERVAL_SECONDS)

    report["metrics"]["planner_poll"] = {
        "poll_count": poll_count,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "final_status": last_payload.get("plan_status"),
        "ingest_status": last_payload.get("ingest_status"),
    }
    return last_payload


def _cleanup_subject(client: httpx.Client, report: dict, token: str, subject_id: int) -> None:
    if EXISTING_SUBJECT_ID:
        report["checks"]["cleanup_skipped"] = "STUDY_PLANNER_SUBJECT_ID was provided"
        return

    headers = {"Authorization": f"Bearer {token}"}
    response = _request(
        client,
        report,
        "DELETE",
        f"{INGESTOR_BASE_URL}/subjects/{subject_id}",
        headers=headers,
        timeout=20,
        step_name="cleanup_subject",
    )
    report["checks"]["cleanup_status"] = response.status_code


@pytest.mark.integration
def test_generate_plan_api_flow():
    report = {
        "run_id": uuid.uuid4().hex[:8],
        "started_at_ms": _now_ms(),
        "config": {
            "auth_base_url": AUTH_BASE_URL,
            "ingestor_base_url": INGESTOR_BASE_URL,
            "planner_base_url": PLANNER_BASE_URL,
            "poll_timeout_seconds": POLL_TIMEOUT_SECONDS,
            "scale_users": SCALE_USERS,
            "requests_per_user": REQUESTS_PER_USER,
            "strict_plan_completion": STRICT_PLAN_COMPLETION,
            "existing_subject_id": EXISTING_SUBJECT_ID,
        },
        "checks": {},
        "metrics": {},
        "steps": [],
        "errors": [],
    }

    subject_id = None
    token = None

    try:
        _scale_health_check(report)

        with httpx.Client(timeout=90) as client:
            token = _create_access_token(client, report)
            headers = {"Authorization": f"Bearer {token}"}

            if EXISTING_SUBJECT_ID:
                subject_id = int(EXISTING_SUBJECT_ID)
                report["checks"]["subject_id"] = subject_id
            else:
                subject_id = _create_subject_via_ingestor(client, report, token)
                ingestor_subject = _poll_data_ingestor_completed(client, report, token, subject_id)
                report["checks"]["ingestor_subject_final"] = ingestor_subject
                assert ingestor_subject.get("ingest_status") == "completed"

            started = time.perf_counter()
            generate_response = _request(
                client,
                report,
                "POST",
                f"{PLANNER_BASE_URL}/subjects/{subject_id}/generate-plan",
                headers=headers,
                json={},
                timeout=30,
                step_name="trigger_generate_plan",
            )
            report["metrics"]["generate_plan_trigger_latency_ms"] = round(
                (time.perf_counter() - started) * 1000,
                2,
            )
            report["checks"]["generate_plan_status"] = generate_response.status_code
            generate_response.raise_for_status()
            report["checks"]["generate_plan_response"] = generate_response.json()

            planner_status = _poll_planner_status(client, report, token, subject_id)
            report["checks"]["planner_final_status"] = planner_status

            if planner_status.get("plan_status") == "completed":
                plan_response = _request(
                    client,
                    report,
                    "GET",
                    f"{PLANNER_BASE_URL}/subjects/{subject_id}/plan",
                    headers=headers,
                    timeout=30,
                    step_name="get_generated_plan",
                )
                report["checks"]["get_plan_status"] = plan_response.status_code
                plan_response.raise_for_status()
                plan_payload = plan_response.json()
                report["checks"]["plan_id"] = plan_payload.get("id")
                report["checks"]["session_count"] = len(plan_payload.get("sessions", []))
                report["checks"]["plan_preview"] = {
                    "subject_id": plan_payload.get("subject_id"),
                    "calendar_synced": plan_payload.get("calendar_synced"),
                    "sessions": plan_payload.get("sessions", [])[:3],
                }

            _cleanup_subject(client, report, token, subject_id)

        assert report["metrics"]["scale_health_check"]["error_count"] == 0
        assert report["checks"]["auth_token_obtained"] is True
        assert report["checks"]["generate_plan_status"] == 200

        if STRICT_PLAN_COMPLETION:
            assert report["metrics"]["planner_poll"]["final_status"] == "completed"
            assert report["checks"].get("session_count", 0) > 0

    except Exception as exc:
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        report["finished_at_ms"] = _now_ms()
        report["duration_ms"] = report["finished_at_ms"] - report["started_at_ms"]
        _write_report(report)
