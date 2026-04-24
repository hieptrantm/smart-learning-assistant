import yaml
import os
from dotenv import load_dotenv

load_dotenv()

def get_prompts():
    with open('configs/prompts.yml', encoding='utf-8') as promptFile:
        prompts = yaml.safe_load(promptFile)
        promptFile.close()
    return prompts

# MCP server
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8031"))

# Google OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
TOKEN_URI = "https://oauth2.googleapis.com/token"
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# Email (SMTP)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Study Planner")

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# LLM
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

LOWLEVEL_COLLECTION_NAME = "low-level-retrieval"
HIGHLEVEL_COLLECTION_NAME = "high-level-retrieval"
RAW_CHUNKS_COLLECTION_NAME = "raw_chunks"

# VectorDB
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "")
DEFAULT_TOP_K = 5
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "AITeamVN/Vietnamese_Embedding_v2")

# LLM
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "openai/gpt-oss-120b")


SYS_LECTURE_GEN_PROMPT = """
# NHIỆM VỤ  
Bạn là một trợ lý chuyên tạo ra bài giảng chi tiết, dễ hiểu dựa trên hình ảnh bài giảng trong sách giáo khoa và các ghi chú được cung cấp.
Nhiệm vụ của bạn là:
- Tổng hợp thông tin từ hình ảnh và ghi chú
- Giữ nguyên nội dung cốt lõi trong sách
- Diễn giải lại theo cách đơn giản hơn, dễ hiểu hơn cho học sinh
Bài giảng phải được viết như một bài giảng thực sự để học sinh đọc và hiểu bài, không phải bản tóm tắt.

---

# CẤU TRÚC ĐẦU RA (BẮT BUỘC)

Bài giảng phải gồm 3 phần chính theo thứ tự:
1. Mở đầu
2. Nội dung chính (chia theo cấu trúc bài trong sách giáo khoa)
3. Kết luận

---

# YÊU CẦU CHI TIẾT
** 1. Mở đầu **
Phần mở đầu phải:
- Có một câu mở đầu thu hút (liên hệ thực tế hoặc câu hỏi gợi tò mò)
- Giới thiệu ngắn gọn chủ đề của bài học
- Dẫn dắt tự nhiên vào nội dung bài
- Có ít nhất 1 câu hỏi ngắn để thu hút người học

** 2. Nội dung chính (QUAN TRỌNG NHẤT) **
Phần này phải bám đúng cấu trúc của bài học trong sách giáo khoa, không tự ý sắp xếp lại nội dung.
Mỗi phần trong sách cần được trình bày lại theo dạng:

** Phần 1: [Tên nội dung theo sách] **
- Giải thích lại nội dung bằng ngôn ngữ đơn giản hơn
- Làm rõ các khái niệm khó
- Diễn giải các đoạn trong sách theo cách dễ hiểu hơn
- Nếu có định nghĩa → phải giải thích lại theo cách dễ hiểu
- Nếu có ví dụ → diễn giải lại ví dụ đó
Sau mỗi phần nên có:
1 câu hỏi gợi suy nghĩ (ví dụ: “Vì sao…?”, “Điều gì xảy ra nếu…?”)

** Phần 2: [Tên nội dung tiếp theo trong sách] **
Tiếp tục trình bày theo đúng thứ tự trong sách:
- Giải thích đơn giản
- Làm rõ ý chính
- Diễn giải lại nội dung khó
- Gắn với ví dụ thực tế nếu có
- Viết với ngôn ngữ tự nhiên để học sinh dễ đọc, không liệt kê nêu tên trực tiếp các ý tôi đã liệt kê ở trên

** Mục tiêu của phần Nội dung chính **
Bài giảng được tạo ra nhằm:
- Làm rõ các ý trong sách giáo khoa
- Diễn giải nội dung theo cách dễ hiểu hơn
- Giúp học sinh hiểu bản chất chứ không chỉ đọc lại nội dung sách
- Giảng giải một cách mượt mà theo ngôn ngữ tự nhiên, không liệt kê rời rạc

** 3. Kết luận **
Phần kết luận cần:
- Tóm tắt lại những ý quan trọng nhất của bài
- Nhắc lại các khái niệm chính
- Kết thúc bằng một câu hỏi mở để học sinh suy nghĩ thêm

---

# YÊU CẦU BỔ SUNG
- Viết như một bài giảng hoàn chỉnh, không liệt kê rời rạc
- Không được suy diễn nội dung ngoài sách
- Nội dung phải rõ ràng, mạch lạc và dễ hiểu
- Giữ giọng văn giảng dạy tự nhiên
- Giới hạn tối đa 1000 từ
- Không cần nhắc đến hình ảnh, chỉ sử dụng nội dung từ chúng
- Kết hợp các icon thân thiện và dễ nhớ để làm bài giảng sinh động hơn (ví dụ: 📌 cho ý chính, ❓ cho câu hỏi, 💡 cho ví dụ, v.v.)
"""

QA_GEN_PROMPT = """
Images: {images}
User request: {user_prompt}

Please generate a detailed lecture based on the provided images and user request
"""


# Helper structures for quiz generation
quiz_type_mapping = {
"multiple_choice": "Câu hỏi trắc nghiệm lựa chọn 4 đáp án (A, B, C, D).",
"true_false": "Câu hỏi trắc nghiệm đúng/sai.",
"short_answer": "Câu hỏi trả lời ngắn.",
"fill_in_the_blank": "Câu hỏi điền vào chỗ trống."
}
quiz_format_mapping = {
"multiple_choice": """        {{
    "type": 1,    # tương ứng với "multiple_choice"
    "text": "Nội dung câu hỏi?",
    "explanation": "Giải thích đáp án đúng"  # Thêm giải thích cho đáp án đúng,
    "options": [
        {
            "optionKey": "A",
            "optionText": "Option A",
            "isCorrect": true # câu A luôn là đáp án đúng
        },
        {
            "optionKey": "B",
            "optionText": "Option B",
            # "isCorrect": false
        }... # Tiếp tục cho các lựa chọn C, D
    ],  
}}""",
"true_false": """        {{
    "type": 3,    # tương ứng với "true_false"
    "text": "Nội dung câu hỏi đúng/sai?",
    "explanation": "Giải thích đáp án đúng"  # Thêm giải thích cho đáp án đúng,
    "options": [
        {
            "optionKey": "A",
            "optionText": "Đúng",
            "isCorrect": true/false
        },
        {
            "optionKey": "B",
            "optionText": "Sai",
            "isCorrect": false # Nếu A là đúng thì B là sai, và ngược lại
        }
    ] 
}}""",
"short_answer": """        {{
    "type": 4,   # tương ứng với "short_answer"
    "text": "Nội dung câu hỏi trả lời ngắn?",
    "explanation": "Giải thích đáp án đúng"  # Thêm giải thích cho đáp án đúng,
    "options": [
        {
            "optionKey": "A",  # mặc định đáp án là A
            "optionText": "Đáp án trả lời ngắn",
            "isCorrect": true  # mặc định là đúng
        }
    ]
}}""",
"fill_in_the_blank": """        {{
    "type": 2,    # tương ứng với "fill_in_the_blank"
    "text": "Nội dung câu hỏi điền vào chỗ trống: ____?",
    "explanation": "Giải thích đáp án đúng"  # Thêm giải thích cho đáp án đúng,
    "options": [
        {
            "optionKey": "A",  # mặc định đáp án là A
            "optionText": "Đáp án điền vào chỗ trống",
            "isCorrect": true  # mặc định là đúng
        }
    ]
}}"""
}