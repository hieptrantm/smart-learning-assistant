import base64
import fitz  # PyMuPDF
from langchain_together import ChatTogether
from langchain_core.messages import HumanMessage, SystemMessage

from rag_config import (
    TOGETHER_API_KEY,
    VLM_MODEL_ID,
    DEFAULT_LANGUAGE,
    FIGURE_SYSTEM_PROMPT,
    FIGURE_USER_PROMPT,
    FORMULA_SYSTEM_PROMPT,
    FORMULA_USER_PROMPT,
)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VLMService:
    """
    Service to handle Visual Language Model (VLM) interactions for describing figures and formulas in PDFs.

    Key Functions:
    - get_b64_image: Extracts a specific region of a PDF page as a base64-encoded image.
    - describe_visual: Uses the VLM to generate descriptions for figures or rewrite formulas based on the extracted image, caption, and context.

    This service is used within the data ingestion pipeline to enhance the extracted content with VLM-generated descriptions, improving the richness of the indexed data.
    """
    def __init__(self, client: ChatTogether = None):
        self.client = client or ChatTogether(api_key=TOGETHER_API_KEY, model=VLM_MODEL_ID)


    def get_b64_image(self, file_path: str, page_index: int, box: dict) -> str | None:
        """Render the bounding-box region of a PDF page to a base64-encoded PNG."""
        try:
            doc = fitz.open(file_path)
            page = doc[page_index]
            rect = fitz.Rect(box["x0"], box["y0"], box["x1"], box["y1"])
            mat = fitz.Matrix(2, 2)  # 2× scale for quality
            pix = page.get_pixmap(matrix=mat, clip=rect)
            encoded_image = base64.b64encode(pix.tobytes("png")).decode("utf-8")
            logger.info(f"Extracted image p{page_index} as base64: {encoded_image[:30]}...")  # Log start of base64 string
            return encoded_image
        except Exception as e:
            logger.error(f"[vlm] Error extracting image p{page_index}: {e}")
            return None


    def describe_visual(
        self,
        encoded_image: str,
        caption: str = "",
        context: str = "",
        box_type: str = "FIGURE",
        language: str | None = None,
    ) -> str:
        """Call the VLM to describe a figure or rewrite a formula from an image."""
        lang = language or DEFAULT_LANGUAGE

        if box_type == "FIGURE":
            sys_prompt = FIGURE_SYSTEM_PROMPT.format(language=lang)
            usr_text = FIGURE_USER_PROMPT.format(caption=caption, context=context)
        else:
            sys_prompt = FORMULA_SYSTEM_PROMPT.format(language=lang)
            usr_text = FORMULA_USER_PROMPT
        
        logger.info(f"VLM system prompt: {sys_prompt}")
        logger.info(f"VLM user text: {usr_text}")
            

        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=[
                {"type": "text", "text": usr_text},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{encoded_image}"},
                },
            ]),
        ]
        try:
            response = self.client.invoke(messages)
        except Exception as e:
            logger.error(f"[vlm] Error invoking VLM: {e}")
            raise
        tag = box_type  # FIGURE or FORMULA
        return f"[{tag}]\n{response.content}\n[/{tag}]"
