import json
import os
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

SERVICE_DIR = Path(__file__).resolve().parents[1]
REPORT_PATH = Path(
    os.getenv(
        "AI_SERVICE_REPORT_PATH",
        str(SERVICE_DIR / "output" / "ai_service_query_quiz_report.json"),
    )
)

AUTH_BASE_URL = os.getenv("AUTH_BASE_URL", "http://localhost:8005/auth").rstrip("/")
INGESTOR_BASE_URL = os.getenv("INGESTOR_BASE_URL", "http://localhost:8005/ingest").rstrip("/")
AI_BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:8005/ai").rstrip("/")

POLL_TIMEOUT_SECONDS = int(os.getenv("AI_TEST_POLL_TIMEOUT_SECONDS", "300"))
POLL_INTERVAL_SECONDS = float(os.getenv("AI_TEST_POLL_INTERVAL_SECONDS", "5"))
STREAM_TIMEOUT_SECONDS = float(os.getenv("AI_STREAM_TIMEOUT_SECONDS", "240"))
SCALE_USERS = int(os.getenv("SCALE_USERS", "100"))
REQUESTS_PER_USER = int(os.getenv("REQUESTS_PER_USER", "2"))
STRICT_QUIZ_TOOL = os.getenv("STRICT_QUIZ_TOOL", "true").lower() == "true"
EXISTING_SUBJECT_ID = os.getenv("AI_TEST_SUBJECT_ID")
EXISTING_USER_ID = os.getenv("AI_TEST_USER_ID")


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
                response = client.get(f"{AI_BASE_URL}/health")
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


def _create_access_token(client: httpx.Client, report: dict) -> tuple[str, int]:
    suffix = uuid.uuid4().hex[:10]
    email = f"ai_test_{suffix}@learning.local"
    password = "TestAuto12345"

    register_response = _request(
        client,
        report,
        "POST",
        f"{AUTH_BASE_URL}/register",
        json={"username": f"ai_test_{suffix}", "email": email, "password": password},
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
    me_response = _request(
        client,
        report,
        "GET",
        f"{AUTH_BASE_URL}/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
        step_name="auth_me",
    )
    report["checks"]["auth_me_status"] = me_response.status_code
    me_response.raise_for_status()
    user_id = int(me_response.json()["id"])

    report["checks"]["auth_token_obtained"] = bool(token)
    report["checks"]["user_id"] = user_id
    return token, user_id


def _create_subject_via_ingestor(client: httpx.Client, report: dict, token: str) -> int:
    run_id = report["run_id"]
    headers = {"Authorization": f"Bearer {token}"}
    free_time = {"mon": ["09:00"], "wed": ["14:00"], "fri": ["10:00"]}
    pdf_bytes = _build_pdf_bytes(
        "AI service test document. Algebra foundations. Linear equations use variables to model straight lines."
    )

    response = _request(
        client,
        report,
        "POST",
        f"{INGESTOR_BASE_URL}/subjects",
        headers=headers,
        data={
            "name": f"AI Query Quiz Flow {run_id}",
            "target_grade": "8.0",
            "end_date": (date.today() + timedelta(days=30)).isoformat(),
            "free_time": json.dumps(free_time),
        },
        files={
            "file": (
                f"ai-query-quiz-{run_id}.pdf",
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


def _parse_stream_event(raw_payload: str) -> dict[str, Any]:
    if raw_payload == "[DONE]":
        return {"type": "done"}
    try:
        return json.loads(raw_payload)
    except json.JSONDecodeError:
        return {"type": "raw", "content": raw_payload}


def _stream_chat(client: httpx.Client, report: dict, step_name: str, payload: dict) -> dict:
    url = f"{AI_BASE_URL}/v1/chat/completions/stream"
    started = time.perf_counter()
    tokens = []
    events = []
    tool_results = []
    errors = []
    status_code = None

    with client.stream("POST", url, json=payload, timeout=STREAM_TIMEOUT_SECONDS) as response:
        status_code = response.status_code
        if response.status_code >= 400:
            body = response.read().decode("utf-8", errors="replace")
            report["steps"].append(
                {
                    "name": step_name,
                    "method": "POST",
                    "url": url,
                    "status_code": response.status_code,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "response_text": body[:1500],
                }
            )
            response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue
            if not line.startswith("data: "):
                continue
            event = _parse_stream_event(line[len("data: "):])
            events.append(event)
            event_type = event.get("type")
            if event_type == "token":
                tokens.append(event.get("content", ""))
            elif event_type == "tool_result":
                tool_results.append(event)
            elif event_type == "error":
                errors.append(event)
            elif event_type == "done":
                break

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    reply = "".join(tokens)
    event_type_counts: dict[str, int] = {}
    for event in events:
        event_type = str(event.get("type", "unknown"))
        event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1

    summary = {
        "status_code": status_code,
        "latency_ms": latency_ms,
        "event_count": len(events),
        "event_type_counts": event_type_counts,
        "events_preview": events[:10],
        "token_event_count": len(tokens),
        "tool_result_count": len(tool_results),
        "tool_names": [item.get("tool_name") for item in tool_results],
        "error_count": len(errors),
        "reply_length": len(reply),
        "reply_preview": reply[:500],
        "tool_results_preview": tool_results[:2],
        "errors": errors,
    }
    report["steps"].append(
        {
            "name": step_name,
            "method": "POST",
            "url": url,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "response_text": "",
        }
    )
    return summary


def _extract_quiz_question_count(stream_summary: dict) -> int:
    total = 0
    for tool_event in stream_summary.get("tool_results_preview", []):
        result = tool_event.get("result")
        if isinstance(result, list):
            total += len(result)
    return total


def _cleanup_subject(client: httpx.Client, report: dict, token: str, subject_id: int) -> None:
    if EXISTING_SUBJECT_ID:
        report["checks"]["cleanup_skipped"] = "AI_TEST_SUBJECT_ID was provided"
        return

    response = _request(
        client,
        report,
        "DELETE",
        f"{INGESTOR_BASE_URL}/subjects/{subject_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
        step_name="cleanup_subject",
    )
    report["checks"]["cleanup_status"] = response.status_code


@pytest.mark.integration
def test_ai_service_query_and_generate_quiz_flow():
    report = {
        "run_id": uuid.uuid4().hex[:8],
        "started_at_ms": _now_ms(),
        "config": {
            "auth_base_url": AUTH_BASE_URL,
            "ingestor_base_url": INGESTOR_BASE_URL,
            "ai_base_url": AI_BASE_URL,
            "poll_timeout_seconds": POLL_TIMEOUT_SECONDS,
            "stream_timeout_seconds": STREAM_TIMEOUT_SECONDS,
            "scale_users": SCALE_USERS,
            "requests_per_user": REQUESTS_PER_USER,
            "strict_quiz_tool": STRICT_QUIZ_TOOL,
            "existing_subject_id": EXISTING_SUBJECT_ID,
            "existing_user_id": EXISTING_USER_ID,
        },
        "checks": {},
        "metrics": {},
        "steps": [],
        "errors": [],
    }

    token = None
    subject_id = None

    try:
        _scale_health_check(report)

        with httpx.Client(timeout=90) as client:
            token, user_id = _create_access_token(client, report)
            if EXISTING_SUBJECT_ID:
                subject_id = int(EXISTING_SUBJECT_ID)
                user_id = int(EXISTING_USER_ID or user_id)
                report["checks"]["subject_id"] = subject_id
                report["checks"]["user_id"] = user_id
            else:
                subject_id = _create_subject_via_ingestor(client, report, token)
                ingestor_subject = _poll_data_ingestor_completed(client, report, token, subject_id)
                report["checks"]["ingestor_subject_final"] = ingestor_subject
                assert ingestor_subject.get("ingest_status") == "completed"

            common_payload = {
                "user_id": user_id,
                "subject_id": subject_id,
                "stream": True,
                "lecture_title": "Algebra foundations",
                "lecture_content": (
                    "Algebra foundations include variables, constants, expressions, and linear equations. "
                    "A linear equation can model a straight line and often has one unknown variable."
                ),
            }

            query_summary = _stream_chat(
                client,
                report,
                "query_question_stream",
                {
                    **common_payload,
                    "question": "Giải thích ngắn gọn phương trình bậc nhất là gì, dựa trên nội dung buổi học.",
                },
            )
            report["checks"]["query_stream"] = query_summary

            quiz_summary = _stream_chat(
                client,
                report,
                "generate_quiz_stream",
                {
                    **common_payload,
                    "question": (
                        "BẮT BUỘC sử dụng tool generate_quiz. Không tự trả lời bằng chữ thường. "
                        "Hãy tạo 4 câu hỏi quiz về Algebra foundations và linear equations từ nội dung buổi học hiện tại. "
                        "Nếu cần gọi tool, hãy dùng đúng format hệ thống với tool_name generate_quiz và arguments JSON gồm "
                        "{\"title\":\"Algebra foundations\", \"description\":\"Algebra foundations include variables, constants, expressions, and linear equations. A linear equation can model a straight line and often has one unknown variable.\", \"totalQuestions\":4}."
                    ),
                },
            )
            quiz_question_count = _extract_quiz_question_count(quiz_summary)
            quiz_summary["quiz_question_count_from_tool_preview"] = quiz_question_count
            report["checks"]["quiz_stream"] = quiz_summary

            _cleanup_subject(client, report, token, subject_id)

        assert report["metrics"]["scale_health_check"]["error_count"] == 0
        assert report["checks"]["auth_token_obtained"] is True
        assert report["checks"]["query_stream"]["status_code"] == 200
        assert report["checks"]["query_stream"]["error_count"] == 0
        assert report["checks"]["query_stream"]["reply_length"] > 0
        assert report["checks"]["quiz_stream"]["status_code"] == 200
        assert report["checks"]["quiz_stream"]["error_count"] == 0

        if STRICT_QUIZ_TOOL:
            assert "generate_quiz" in report["checks"]["quiz_stream"]["tool_names"]
            assert report["checks"]["quiz_stream"]["tool_result_count"] > 0

    except Exception as exc:
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        report["finished_at_ms"] = _now_ms()
        report["duration_ms"] = report["finished_at_ms"] - report["started_at_ms"]
        _write_report(report)
