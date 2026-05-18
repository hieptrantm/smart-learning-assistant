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
MCP_URL = os.getenv("MCP_URL", "http://localhost:8002/mcp")

# ── Neo4j ──────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
TREE_SUBJECT_ID_SUFFIX = "_tree"

# ── Planner constants ─────────────────────────────────────────
PLANNER_MAX_RETRIES = 3
PLANNER_RETRY_DELAY = 3  # seconds
EMAIL_MAX_RETRIES = 3
SCHEDULE_TOOL_BATCH_SIZE = int(os.getenv("SCHEDULE_TOOL_BATCH_SIZE", "50"))

# ── SMTP (shared with mcp-server) ─────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Smart Learning Tutor")

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


EMAIL_SUBJECT_TEMPLATE = "📅 Lộ trình học mới - {subject_name}"

EMAIL_BODY_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#e8f4fd;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
  <tr><td align="center" style="padding:48px 16px;">

    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

      <!-- ── HEADER ── -->
      <tr><td style="background:linear-gradient(135deg,#003087 0%,#0077cc 100%);border-radius:20px 20px 0 0;padding:44px 48px 40px;text-align:center;">
        <div style="display:inline-block;background:rgba(255,255,255,0.15);border-radius:50%;width:72px;height:72px;line-height:72px;font-size:36px;">📅</div>
        <h1 style="color:#fff;margin:18px 0 6px;font-size:26px;font-weight:800;letter-spacing:-0.5px;">Lộ trình học đã sẵn sàng!</h1>
        <p style="color:rgba(255,255,255,0.75);margin:0;font-size:15px;">Xin chào <strong style="color:#fff;">{username}</strong> — hệ thống vừa tạo lộ trình mới cho bạn.</p>
      </td></tr>

      <!-- ── STATS BAR ── -->
      <tr><td style="background:#fff;padding:0 48px;">
        <table width="100%" cellpadding="0" cellspacing="0" style="border-bottom:1px solid #f3f4f6;">
          <tr>
            <td style="padding:20px 0;text-align:center;border-right:1px solid #f3f4f6;">
              <div style="font-size:28px;font-weight:800;color:#003087;">{total_sessions}</div>
              <div style="font-size:12px;color:#9ca3af;margin-top:2px;text-transform:uppercase;letter-spacing:0.05em;">Buổi học</div>
            </td>
            <td style="padding:20px 0;text-align:center;">
              <div style="font-size:28px;font-weight:800;color:#003087;">{target_grade}<span style="font-size:18px;font-weight:600;">/10</span></div>
              <div style="font-size:12px;color:#9ca3af;margin-top:2px;text-transform:uppercase;letter-spacing:0.05em;">Mục tiêu điểm</div>
            </td>
          </tr>
        </table>
      </td></tr>

      <!-- ── SUBJECT TAG ── -->
      <tr><td style="background:#fff;padding:24px 48px 8px;">
        <p style="margin:0;font-size:14px;color:#6b7280;">Môn học:
          <span style="display:inline-block;background:#e8f4fd;color:#002b7a;border-radius:6px;padding:3px 10px;font-weight:600;font-size:13px;">{subject_name}</span>
        </p>
      </td></tr>

      <!-- ── SESSION TABLE HEADER ── -->
      <tr><td style="background:#fff;padding:16px 48px 0;">
        <p style="margin:0 0 12px;font-size:15px;font-weight:700;color:#111827;">📋 Chi tiết lịch học</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
          <tr style="background:#003087;">
            <td style="width:36px;padding:11px 12px;"></td>
            <td style="padding:11px 0;color:#fff;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;">Ngày &amp; giờ</td>
            <td style="padding:11px 16px;color:#fff;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;">Nội dung</td>
          </tr>
          {session_rows}
        </table>
      </td></tr>

      <!-- ── CALENDAR NOTE ── -->
      <tr><td style="background:#fff;padding:20px 48px 32px;">
        <div style="background:#f0fdf4;border-radius:10px;padding:14px 18px;border-left:4px solid #10b981;">
          <p style="margin:0;font-size:13px;color:#065f46;">
            ✅ <strong>Lịch đã được đồng bộ vào Google Calendar.</strong>
            Bạn sẽ nhận thông báo nhắc học theo từng buổi.
          </p>
        </div>
      </td></tr>

      <!-- ── FOOTER ── -->
      <tr><td style="background:#f8fafc;border-top:1px solid #e5e7eb;border-radius:0 0 20px 20px;padding:24px 48px;text-align:center;">
        <p style="margin:0 0 4px;color:#6b7280;font-size:13px;font-weight:600;">Smart Learning Assistant</p>
        <p style="margin:0;color:#9ca3af;font-size:12px;">Chúc bạn học tốt và đạt điểm cao! 🚀</p>
      </td></tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""

EMAIL_SESSION_ROW = """<tr style="background:{row_bg};border-bottom:1px solid #f3f4f6;">
  <td style="padding:14px 12px;text-align:center;vertical-align:top;">
    <span style="display:inline-block;background:#e8f4fd;color:#003087;border-radius:50%;width:24px;height:24px;line-height:24px;font-size:11px;font-weight:700;">{idx}</span>
  </td>
  <td style="padding:14px 0;vertical-align:top;white-space:nowrap;">
    <div style="font-size:13px;font-weight:600;color:#374151;">{date}</div>
    <div style="font-size:12px;color:#003087;margin-top:2px;">⏰ {time_start} – {time_end}</div>
  </td>
  <td style="padding:14px 16px;vertical-align:top;">
    <div style="font-size:14px;font-weight:600;color:#111827;">{summary}</div>
    <div style="font-size:12px;color:#6b7280;margin-top:4px;line-height:1.6;">{description}</div>
  </td>
</tr>"""

# ── Quiz result email templates ───────────────────────────────
QUIZ_EMAIL_SUBJECT_PASSED = "🏆 Xuất sắc! Bạn đã pass buổi học - {subject_name}"
QUIZ_EMAIL_SUBJECT_FAILED = "💪 Cố lên! Lộ trình đã được cập nhật - {subject_name}"

QUIZ_EMAIL_BODY_PASSED = """<!DOCTYPE html>
<html lang="vi">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f0fdf4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 20px;">
  <tr><td align="center">
    <table width="580" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
      <!-- Header -->
      <tr><td style="background:linear-gradient(135deg,#10b981,#059669);padding:40px;text-align:center;">
        <div style="font-size:56px;line-height:1;">🏆</div>
        <h1 style="color:#fff;margin:14px 0 4px;font-size:26px;font-weight:800;">Xuất sắc!</h1>
        <p style="color:rgba(255,255,255,0.85);margin:0;font-size:14px;">Bạn đã hoàn thành bài kiểm tra thành công</p>
      </td></tr>
      <!-- Score card -->
      <tr><td style="padding:36px 40px 0;">
        <p style="color:#374151;font-size:15px;margin:0 0 24px;">Xin chào <strong>{username}</strong>,</p>
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:14px;padding:28px;text-align:center;margin:0 0 24px;">
          <p style="color:#6b7280;font-size:13px;margin:0 0 6px;text-transform:uppercase;letter-spacing:0.05em;">Điểm đạt được</p>
          <div style="font-size:58px;font-weight:900;color:#10b981;line-height:1;">{score}%</div>
          <p style="color:#9ca3af;font-size:13px;margin:8px 0 16px;">Mục tiêu: <strong style="color:#10b981;">{target_score}%</strong></p>
          <!-- Progress bar -->
          <div style="background:#d1fae5;border-radius:999px;height:10px;overflow:hidden;">
            <div style="background:linear-gradient(90deg,#10b981,#34d399);height:100%;width:{score}%;border-radius:999px;"></div>
          </div>
        </div>
        <!-- Subject info -->
        <div style="background:#f8fafc;border-radius:10px;padding:14px 18px;margin:0 0 24px;border-left:4px solid #10b981;">
          <p style="margin:0;color:#374151;font-size:14px;">📚 Môn học: <strong>{subject_name}</strong></p>
        </div>
        <!-- Motivation -->
        <div style="background:#fffbeb;border-radius:10px;padding:18px;margin:0 0 28px;border:1px solid #fde68a;">
          <p style="margin:0;color:#92400e;font-size:14px;line-height:1.7;">✨ {motivation}</p>
        </div>
      </td></tr>
      <!-- Footer -->
      <tr><td style="background:#f8fafc;border-top:1px solid #e5e7eb;padding:24px 40px;text-align:center;">
        <p style="color:#9ca3af;font-size:12px;margin:0;">Tiếp tục duy trì phong độ! Hệ thống đã sẵn sàng cho buổi học tiếp theo. 🚀</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""

QUIZ_EMAIL_BODY_FAILED = """<!DOCTYPE html>
<html lang="vi">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#fff7ed;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 20px;">
  <tr><td align="center">
    <table width="580" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
      <!-- Header -->
      <tr><td style="background:linear-gradient(135deg,#f59e0b,#d97706);padding:40px;text-align:center;">
        <div style="font-size:56px;line-height:1;">💪</div>
        <h1 style="color:#fff;margin:14px 0 4px;font-size:26px;font-weight:800;">Chưa đạt lần này!</h1>
        <p style="color:rgba(255,255,255,0.85);margin:0;font-size:14px;">Nhưng đừng nản — lộ trình đã được điều chỉnh lại cho bạn</p>
      </td></tr>
      <!-- Score card -->
      <tr><td style="padding:36px 40px 0;">
        <p style="color:#374151;font-size:15px;margin:0 0 24px;">Xin chào <strong>{username}</strong>,</p>
        <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:14px;padding:28px;text-align:center;margin:0 0 24px;">
          <p style="color:#6b7280;font-size:13px;margin:0 0 6px;text-transform:uppercase;letter-spacing:0.05em;">Điểm đạt được</p>
          <div style="font-size:58px;font-weight:900;color:#f59e0b;line-height:1;">{score}%</div>
          <p style="color:#9ca3af;font-size:13px;margin:8px 0 16px;">Mục tiêu: <strong style="color:#f59e0b;">{target_score}%</strong></p>
          <!-- Progress bar -->
          <div style="background:#fed7aa;border-radius:999px;height:10px;overflow:hidden;">
            <div style="background:linear-gradient(90deg,#f59e0b,#fbbf24);height:100%;width:{score}%;border-radius:999px;"></div>
          </div>
        </div>
        <!-- Subject info -->
        <div style="background:#f8fafc;border-radius:10px;padding:14px 18px;margin:0 0 24px;border-left:4px solid #f59e0b;">
          <p style="margin:0;color:#374151;font-size:14px;">📚 Môn học: <strong>{subject_name}</strong></p>
        </div>
        <!-- Plan updated notice -->
        <div style="background:#eff6ff;border-radius:10px;padding:18px;margin:0 0 16px;border:1px solid #bfdbfe;">
          <p style="margin:0;color:#1e40af;font-size:14px;line-height:1.7;">🔄  Hệ thống đã điều chỉnh lại lịch học để ôn tập lại phần bạn chưa nắm vững. Kiểm tra Google Calendar để xem lịch mới nhé!</p>
        </div>
        <!-- Motivation -->
        <div style="background:#fffbeb;border-radius:10px;padding:18px;margin:0 0 28px;border:1px solid #fde68a;">
          <p style="margin:0;color:#92400e;font-size:14px;line-height:1.7;">✨ <strong></strong> {motivation}</p>
        </div>
      </td></tr>
      <!-- Footer -->
      <tr><td style="background:#f8fafc;border-top:1px solid #e5e7eb;padding:24px 40px;text-align:center;">
        <p style="color:#9ca3af;font-size:12px;margin:0;">Mỗi lần thất bại là một bước tiến gần hơn đến thành công. Chúc bạn học tốt! 📖</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""

QUIZ_PASSED_MOTIVATIONS = [
    "Kết quả tuyệt vời! Sự kiên trì và nỗ lực của bạn đã được đền đáp. Hãy tiếp tục giữ vững phong độ này nhé!",
    "Bạn đang đi đúng hướng! Điểm số này cho thấy bạn đã nắm vững kiến thức rất tốt. Chuẩn bị cho thách thức tiếp theo thôi!",
    "Thành tích đáng tự hào! Hệ thống đã sẵn sàng lộ trình tiếp theo để bạn khám phá những kiến thức mới hơn.",
    "Xuất sắc! Bạn đã chứng minh được năng lực của mình. Hãy duy trì thói quen học tốt này!",
]

QUIZ_FAILED_MOTIVATIONS = [
    "Đừng nản lòng! Mỗi lần thử là một lần học. Lộ trình đã được điều chỉnh để giúp bạn ôn lại những phần còn yếu.",
    "Thất bại là bước đệm để thành công. Hệ thống đã cập nhật lịch học phù hợp hơn — hãy cố gắng thêm một lần nữa nhé!",
    "Kiến thức cần được lặp lại nhiều lần mới thấm sâu. Lộ trình mới sẽ giúp bạn củng cố lại nền tảng vững chắc hơn.",
    "Không sao cả! Quan trọng là bạn đang tiến bộ từng ngày. Hãy xem lại lộ trình và tiếp tục nào!",
]
