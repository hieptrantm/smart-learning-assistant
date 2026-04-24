import re
import os
from dotenv import load_dotenv

load_dotenv()

# App
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8005"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "Vietnamese")

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testtest")

# Qdrant
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
QDRANT_URL = os.getenv("QDRANT_URL", None)
QDRANT_UPLOAD_BATCH_SIZE = 2

LOWLEVEL_COLLECTION_NAME = "low-level-retrieval"
HIGHLEVEL_COLLECTION_NAME = "high-level-retrieval"
RAW_CHUNKS_COLLECTION_NAME = "raw_chunks"

# Dense embedding
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIM", "1024"))

# LLM
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "")
VLM_MODEL_ID = os.getenv("VLM_MODEL_ID", "")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/authdb",
)

# ── JWT (shared secret with auth-service) ──────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "hiep-tran-thanh-mieu")
ALGORITHM = "HS256"

# ── Study-planner-api URL (to trigger plan generation) ─────────
PLANNER_URL = os.getenv("PLANNER_URL", "http://localhost:8006")


# Prompts
ENTITY_EXTRACTION_SYSTEM_PROMPT = """Bạn là chuyên gia trích xuất thông tin từ văn bản học thuật.
Nhiệm vụ: Trích xuất các ENTITY (thực thể/khái niệm) quan trọng từ đoạn văn bản.

Mỗi entity cần có:
- name: Tên chính xác của entity
- type: Loại entity (CONCEPT, PERSON, ORGANIZATION, EVENT, FORMULA, THEOREM, LAW, TERM)
- description: Mô tả ngắn gọn 1-2 câu

Chỉ trích xuất những entity QUAN TRỌNG, có ý nghĩa học thuật.
KHÔNG trích xuất các từ thông thường, từ nói, hoặc khái niệm quá chung chung.

=== OUTPUT FORMAT ===
[
    {{
        "name": "Tên entity",
        "type": "CONCEPT|PERSON|ORGANIZATION|EVENT|FORMULA|THEOREM|LAW|TERM",
        "description": "Mô tả ngắn gọn về entity này"
    }}
]
"""


ENTITY_EXTRACTION_USER_PROMPT = """Trích xuất các entity quan trọng từ đoạn văn bản sau:

=== CHUNK CONTENT ===
{chunk_content}

Chỉ trả về định dạng JSON hợp lệ, không giải thích thêm."""


RELATION_EXTRACTION_SYSTEM_PROMPT = """Bạn là chuyên gia phân tích quan hệ giữa các khái niệm trong văn bản được cung cấp.
Nhiệm vụ: Xác định các mối quan hệ (relationship) giữa các thực thể entities đã được trích xuất.

Các loại quan hệ phổ biến giữa các thực thể bao gồm:
- DEFINES: A định nghĩa/giải thích B
- CAUSES: A gây ra/dẫn đến B
- PART_OF: A là một phần của B
- RELATED_TO: A liên quan đến B
- PREREQUISITE: Cần hiểu A trước khi học B
- EXAMPLE_OF: A là ví dụ của B
- CONTRASTS: A đối lập/so sánh với B
- APPLIES_TO: A áp dụng cho B
- DERIVED_FROM: A được suy ra từ B

Output phải là định dạng JSON hợp lệ như sau:
=== OUTPUT FORMAT ===
[
    {{
        "source": "Tên entity nguồn",
        "relation": "DEFINES|CAUSES|PART_OF|RELATED_TO|PREREQUISITE|EXAMPLE_OF|CONTRASTS|APPLIES_TO|DERIVED_FROM",
        "target": "Tên entity đích",
        "description": "Mô tả ngắn về quan hệ này",
        "keywords": ["từ khóa chủ đề 1", "từ khóa chủ đề 2"]
    }}
]        
"""

RELATION_EXTRACTION_USER_PROMPT = """Xác định các quan hệ giữa các entity (relationships) trong đoạn văn bản sau:

=== ENTITIES ===
{entities}

=== CHUNK CONTENT (ngữ cảnh) ===
{chunk_content}

Chỉ trả về định dạng JSON hợp lệ, không giải thích thêm."""



CONCEPT_MERGE_SYSTEM_PROMPT = """Bạn là chuyên gia xác định các nhóm thực thể (entity) giống nhau hoặc tương đương

Nhiệm vụ: Xác định các nhóm entity có thể MERGE (gộp) lại thành 1.

Các entity nên được merge nếu:
- Chung là cùng một khái niệm (khác tên gọi)
- Cái này là viết tắt của cái kia
- Cái này là tên tiếng Việt, cái kia là tiếng Anh
- Chung chỉ khác nhau về cách viết hoa/thường

=== OUTPUT FORMAT ===
[
    {{
        "entities": ["Tên entity 1", "Tên entity 2",...],
        "canonical_name": "Tên chuẩn nên giữ lại",
        "reason": "Lý do merge"
    }}
]

Output phải là JSON array hợp lệ."""
CONCEPT_MERGE_USER_PROMPT = """Xác định các cặp entity cần được merge:

=== DANH SÁCH ENTITIES ===
{entities}
Chỉ trả về JSON array. Nếu không có cặp nào cần merge, trả về []."""


PROFILING_SYSTEM_PROMPT = """Bạn là chuyên gia tổng hợp thông tin về một thực thể dựa trên các đoạn văn bản có chứa thông tin về thực thể đó.
Nhiệm vụ: Đọc tất cả các đoạn văn bản chứa thông tin về một thực thể và viết bản mô tả tổng hợp, chi tiết, chính xác nhất.

Yêu cầu:
- Tổng hợp từ tất cả các nguồn
- Chi tiết, chính xác (3-6 câu)
- Giữ nguyên thuật ngữ chuyên ngành

Chỉ trả về đoạn mô tả, không giải thích thêm."""

PROFILING_USER_PROMPT = """Viết mô tả tổng hợp cho thực thể "{entity_name}" (loại: {entity_type}) dựa trên các đoạn văn bản sau:

=== NỘI DUNG TỪ CÁC ĐOẠN VĂN BẢN ===
{source_chunks}

=== OUTPUT ===
Trả về 1 đoạn mô tả tổng hợp chi tiết (3-6 câu)."""



QUERY_EXPANSION_SYSTEM_PROMPT = """Bạn là chuyên gia mở rộng truy vấn tìm kiếm.
Nhiệm vụ: Từ câu hỏi của user, sinh ra các keywords/concepts liên quan để tìm kiếm trong Knowledge Graph.

Phân loại keywords:
- main_concepts: tên thực thể cụ thể, thuật ngữ kỹ thuật (low-level search)
- related_keywords: khái niệm trừu tượng, chủ đề rộng (high-level search)

Output PHAI la JSON object hop le."""



QUERY_EXPANSION_USER_PROMPT = """Mở rộng câu hỏi sau thành các keywords tìm kiếm:

=== CÂU HỎI ===
{query}

=== OUTPUT FORMAT ===
{{
    "main_concepts": ["concept chính 1", "concept chính 2"],
    "related_keywords": ["keyword liên quan 1", "keyword 2", ...],
    "question_type": "DEFINITION|COMPARISON|CAUSE_EFFECT|EXAMPLE|APPLICATION|GENERAL"
}}

Chỉ trả về JSON, không giải thích thêm."""



FIGURE_SYSTEM_PROMPT = """
You are a helpful assistant that generates detailed descriptions for images in academic documents. 
Given an image and its caption and context, generate a detailed description.
You must answer below 500 words.
You must answer in {language}.
"""
FIGURE_USER_PROMPT = """Please generate a detailed description for the following image based on its caption and context.\n
Caption: {caption}
Context: {context}
"""



FORMULA_SYSTEM_PROMPT = """
You are an expert assistant in understanding formulas in academic documents.
Given an image of a formula, please Rewrite the formula in LaTeX format exactly as it appears in the image.
You must write the formula in LaTeX format.
You must write in 1 line without any explanation.
You must answer in {language}.
"""

FORMULA_USER_PROMPT = """Please generate a clear rewrite the formula in LaTeX format\n
"""

figure_prompt = FIGURE_USER_PROMPT
formula_prompt = FORMULA_USER_PROMPT
 
# Heading classification
_LEVEL1 = [
    r"^(Chương|CHƯƠNG)\s+[IVXLCDM]+",
    r"^(Chương|CHƯƠNG)\s+\d+",
    r"^(Part|PART)\s+[IVXLCDM]+",
    r"^(Part|PART)\s+\d+",
    r"^(Chapter|CHAPTER)\s+[IVXLCDM]+",
    r"^(Chapter|CHAPTER)\s+\d+",
    r"^(Section|SECTION)\s+\d+",
    r"^(Phần|PHẦN)\s+[IVXLCDM]+",
    r"^(Phần|PHẦN)\s+\d+",
]
_LEVEL2 = [
    r"^[IVXLCDM]+\.",
    r"^[A-Z]\.",
    r"^[IVXLCDM]+\s+[A-Za-z]",
    r"^(§)\s+\d+",
]
_LEVEL3 = [
    r"^\d+\.",
    r"^\d+\.\d+",
    r"^\d+\s+[A-Za-z]",
]


# ── Tree-based indexing ────────────────────────────────────────
TREE_SUBJECT_ID_SUFFIX = "_tree"
TREE_EDGE_DEFINE = "DEFINE"
TREE_ROOT_LABEL = "TreeRoot"
TREE_NODE_LABEL = "TreeNode"

PROMPT_ROOT_DESCRIPTION = """Bạn là chuyên gia tổng hợp kiến thức. Hãy viết mô tả tổng quan (3-5 câu) cho môn học/chủ đề "{subject_id}" dựa trên các khái niệm chính sau:
{node_names}
Chỉ trả về đoạn mô tả, không giải thích thêm."""

PROMPT_DEFINE_DESCRIPTION = """Hãy viết đoạn mô tả ngắn gọn (1-2 câu) giải thích vì sao khái niệm "{node_name}" là một thành phần quan trọng của môn "{subject_id}".
Mô tả hiện tại: {node_description}
Chỉ trả về đoạn mô tả, không giải thích thêm."""

PROMPT_TAG_DESCRIPTION = """Hãy viết mô tả ngắn gọn (1-2 câu) về mối liên hệ giữa "{source_name}" và "{target_name}".
Loại quan hệ: {rel_type}
Mô tả quan hệ: {rel_description}
Mô tả target: {target_description}
Chỉ trả về đoạn mô tả, không giải thích thêm."""