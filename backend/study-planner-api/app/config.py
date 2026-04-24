"""
config.py -- All environment variables and LLM prompts for study-planner-api.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── App ────────────────────────────────────────────────────────
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8006"))

# ── Database ───────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/authdb",
)

# ── JWT ────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "hiep-tran-thanh-mieu")
ALGORITHM = "HS256"

# ── Data-ingestor ──────────────────────────────────────────────
INGESTOR_URL = os.getenv("INGESTOR_URL", "http://localhost:8005")

# ── Together AI (LLM) ─────────────────────────────────────────
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL_ID", "")

# ── Google Calendar ────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# ── Qdrant ─────────────────────────────────────────────────────
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# ── MCP Server (study-planner-mcp) ────────────────────────────
MCP_HOST = os.getenv("MCP_PLANNER_HOST", "localhost")
MCP_PORT = os.getenv("MCP_PLANNER_PORT", "8031")

# ── Neo4j ──────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
TREE_SUBJECT_ID_SUFFIX = "_tree"

# ── Planner constants ─────────────────────────────────────────
PLANNER_MAX_RETRIES = 3
PLANNER_RETRY_DELAY = 3  # seconds
EMAIL_MAX_RETRIES = 3

# ── Prompts ────────────────────────────────────────────────────

PLANNER_SYSTEM_PROMPT = """Ban la tro ly len ke hoach hoc tap thong minh.

**Thong tin mon hoc:**
- Ten: {subject_name}
- Muc tieu diem: {target_grade}/10
- Ngay hom nay: {today}
- Ngay ket thuc: {end_date}

**Thoi gian ranh hang tuan:**
{free_desc}

**Noi dung tai lieu (excerpts):**
{context_text}

{recommend_section}

**Yeu cau:**
1. Tao lich hoc CHI TIET tu ngay mai den ngay ket thuc.
2. Chi xep lich vao cac khung gio ranh da cho.
3. Moi buoi hoc 1-2 tieng lien tiep.
4. Phan bo noi dung tu de -> kho, co on tap.
5. Tuan cuoi danh cho on tap tong hop.
6. Noi dung moi buoi phai CU THE (khong chung chung).

**Output JSON (KHONG markdown, chi JSON thuan):**
Tra ve mot JSON array, moi phan tu la mot Google Calendar event:
[
  {{
    "summary": "Ten session/bai hoc",
    "location": "Online",
    "description": "Mo ta nhanh noi dung",
    "start": {{
      "dateTime": "YYYY-MM-DDTHH:MM:SS+07:00",
      "timeZone": "Asia/Ho_Chi_Minh"
    }},
    "end": {{
      "dateTime": "YYYY-MM-DDTHH:MM:SS+07:00",
      "timeZone": "Asia/Ho_Chi_Minh"
    }}
  }}
]

Chi tra ve JSON array, khong giai thich."""


OBSERVATION_SYSTEM_PROMPT = """Ban la node dieu phoi cua he thong study planner.
Dua tren trang thai hien tai, hay phan tich va dua ra hanh dong tiep theo.

Trang thai hien tai:
- Buoc truoc: {previous_step}
- Ket qua tool gan nhat: {last_tool_result}
- Loi (neu co): {error}
- So session missed: {missed_count}
- So subject can lap ke hoach: {pending_count}

Neu tat ca session completed, hay danh gia diem so hien tai so voi muc tieu:
- Target grade: {target_grade}
- Diem trung binh hien tai: {avg_score}

Hay tra loi ngan gon: hanh dong tiep theo la gi va tai sao.
Neu can thay doi ke hoach, hay viet recommend cu the."""


OBSERVATION_SCORE_PROMPT = """Diem trung binh hien tai cua sinh vien la {avg_score}/10, muc tieu la {target_grade}/10.
Cac session da hoan thanh: {completed_sessions}
Hay danh gia va de xuat thay doi ke hoach neu can thiet. Tra loi ngan gon."""


EMAIL_SUBJECT_TEMPLATE = "Kế hoạch học tập mới - Môn {subject_name}"

EMAIL_BODY_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2 style="color: #2c3e50;">Kế hoạch học tập môn: {subject_name}</h2>
  <p>Xin chào,</p>
  <p>Hệ thống đã tạo kế hoạch học tập mới cho môn <strong>{subject_name}</strong>.</p>
  <p>Mục tiêu điểm số: <strong>{target_grade}/10</strong></p>
  <h3 style="color: #34495e;">Chi tiết lịch học:</h3>
  <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
    <tr style="background: #3498db; color: white;">
      <th style="padding: 8px; text-align: left;">Thời gian</th>
      <th style="padding: 8px; text-align: left;">Nội dung</th>
    </tr>
    {session_rows}
  </table>
  <p style="margin-top: 20px; color: #7f8c8d; font-size: 12px;">
    Lịch học đã được đồng bộ vào Google Calendar của bạn.
  </p>
</body>
</html>"""

EMAIL_SESSION_ROW = """<tr style="border-bottom: 1px solid #ecf0f1;">
  <td style="padding: 8px;">{start} - {end}</td>
  <td style="padding: 8px;"><strong>{summary}</strong><br><span style="color: #7f8c8d; font-size: 12px;">{description}</span></td>
</tr>"""
