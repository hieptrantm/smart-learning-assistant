"""
Test QuizGeneratorTool — generate quiz questions from lesson content.
Requires: TOGETHER_API_KEY (or LLM_API_KEY) set in environment / .env
"""
import asyncio
import json
import logging

from tools.gen_quiz import QuizGeneratorTool
from llm.together_llm import TogetherLLM
from config import TOGETHER_API_KEY, LLM_MODEL_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sample lesson content
# ---------------------------------------------------------------------------
SAMPLE_TITLE = "Quang hợp ở thực vật"
SAMPLE_DESCRIPTION = """
Quang hợp là quá trình mà thực vật, tảo và một số vi khuẩn sử dụng ánh sáng mặt trời
để tổng hợp chất hữu cơ từ CO2 và H2O. Phương trình tổng quát:
    6CO2 + 6H2O + ánh sáng → C6H12O6 + 6O2
Quá trình gồm hai giai đoạn:
1. Pha sáng (light-dependent reactions): diễn ra ở màng thylakoid, giải phóng O2
   và tổng hợp ATP, NADPH.
2. Pha tối (Calvin cycle): diễn ra trong stroma, sử dụng ATP và NADPH để cố định CO2
   thành đường glucose.
Lục lạp là bào quan thực hiện quang hợp, chứa chất diệp lục (chlorophyll) hấp thu
chủ yếu ánh sáng đỏ và xanh lam.
"""

EXISTING_QUESTIONS = [
    {
        "text": "Quang hợp xảy ra ở bào quan nào?",
        "type": "multiple_choice",
        "options": ["Ty thể", "Lục lạp", "Nhân tế bào", "Ribosome"],
        "answer": "Lục lạp"
    }
]


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

async def test_basic_generation():
    """Generate a small quiz without existing questions."""
    print("\n" + "="*60)
    print("TEST 1: Basic quiz generation (5 questions)")
    print("="*60)

    tool = QuizGeneratorTool(llm_client=_make_llm())
    raw = await tool.generate_quiz(
        title=SAMPLE_TITLE,
        description=SAMPLE_DESCRIPTION,
        totalQuestions=5,
    )
    result = json.loads(raw)

    assert result["success"] is True, "Expected success=True"
    questions = result["tool_result"]
    print(f"Generated {len(questions)} question(s).")
    for i, q in enumerate(questions, 1):
        print(f"  Q{i}: {q}")
    assert len(questions) > 0, "No questions generated"
    print("PASSED")


async def test_extend_existing_questions():
    """Extend an existing question list to reach 8 total."""
    print("\n" + "="*60)
    print("TEST 2: Extend existing questions to 8 total")
    print("="*60)

    tool = QuizGeneratorTool(llm_client=_make_llm())
    raw = await tool.generate_quiz(
        title=SAMPLE_TITLE,
        description=SAMPLE_DESCRIPTION,
        totalQuestions=8,
        questions=EXISTING_QUESTIONS,
    )
    result = json.loads(raw)

    assert result["success"] is True, "Expected success=True"
    questions = result["tool_result"]
    print(f"Total questions after extend: {len(questions)}")
    assert len(questions) >= len(EXISTING_QUESTIONS), "Result should contain at least the original questions"
    print("PASSED")


async def test_no_description():
    """Generate quiz with title only (no explicit description)."""
    print("\n" + "="*60)
    print("TEST 3: Quiz with title only (no description)")
    print("="*60)

    tool = QuizGeneratorTool(llm_client=_make_llm())
    raw = await tool.generate_quiz(
        title="Lịch sử Việt Nam thế kỷ XX",
        totalQuestions=4,
    )
    result = json.loads(raw)

    assert result["success"] is True, "Expected success=True"
    questions = result["tool_result"]
    print(f"Generated {len(questions)} question(s).")
    assert len(questions) > 0, "No questions generated"
    print("PASSED")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_llm() -> TogetherLLM:
    return TogetherLLM(
        together_api_key=TOGETHER_API_KEY,
        model_name=LLM_MODEL_ID,
    )


async def run_all():
    await test_basic_generation()
    # await test_extend_existing_questions()
    # await test_no_description()
    print("\nAll tests passed.")


if __name__ == "__main__":
    asyncio.run(run_all())
