import os
import json
import logging
from typing import List, Dict, Any, Tuple
import json
from dotenv import load_dotenv
from langchain_together import ChatTogether
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
import base64

from rag_config import (
    ENTITY_EXTRACTION_SYSTEM_PROMPT,
    ENTITY_EXTRACTION_USER_PROMPT,
    RELATION_EXTRACTION_SYSTEM_PROMPT,
    RELATION_EXTRACTION_USER_PROMPT,
    CONCEPT_MERGE_SYSTEM_PROMPT,
    CONCEPT_MERGE_USER_PROMPT,
    QUERY_EXPANSION_SYSTEM_PROMPT,
    QUERY_EXPANSION_USER_PROMPT,
    LLM_MODEL_ID,
    TOGETHER_API_KEY
)


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

class LLMService:
    """Call LLM Service using langchain invoke pattern"""
    
    def __init__(self, client: ChatTogether = None):
        self.client = client or ChatTogether(
            model=LLM_MODEL_ID,
            api_key=TOGETHER_API_KEY,
            temperature=0.3
        )
        self.logger = logging.getLogger(self.__class__.__name__)
    
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call LLM using langchain invoke"""
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = self.client.invoke(messages)
            return response.content
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            raise

    async def _acall_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Async call LLM using langchain ainvoke"""
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = await self.client.ainvoke(messages)
            return response.content
        except Exception as e:
            self.logger.error(f"Async LLM call failed: {e}")
            raise
    
    def extract_learning_units(self, document_text: str, 
                               course_context: str = "") -> List[Dict]:
        """
        STEP 1: LLM reads the entire document and extracts Learning Units
        """
        system_prompt = """Bạn là chuyên gia phân tích cấu trúc giáo trình.
Nhiệm vụ: Đọc nội dung tài liệu và trích xuất các đơn vị học tập (Learning Units).

Mỗi Learning Unit là một concept/bài học độc lập có thể dạy riêng.
KHÔNG chia quá nhỏ (1 paragraph) hoặc quá lớn (cả chương).

Output PHẢI là JSON array hợp lệ."""

        user_prompt = f"""Phân tích tài liệu sau và trích xuất Learning Units:

=== CONTEXT ===
{course_context}

=== DOCUMENT CONTENT ===
{document_text[:50000]}  # Giới hạn token

=== OUTPUT FORMAT ===
Trả về JSON array, mỗi item có format:
{{
    "unit_id": "CH[X]_U[Y]",  // X = chapter, Y = unit number
    "title": "Tên bài học/concept",
    "chapter_title": "Tên chương chứa unit này",
    "source_pages": [start_page, end_page],
    "brief_description": "Mô tả ngắn 1-2 câu"
}}

Chỉ trả về JSON, không giải thích thêm."""

        response = self._call_llm(system_prompt, user_prompt)
        
        # Parse JSON
        try:
            # Clean response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            units = json.loads(response)
            return units
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse units JSON: {e}")
            return []
    
    def generate_semantic_profile(self, unit_title: str, 
                                  unit_content: str,
                                  course_context: str = "") -> Dict:
        """
        STEP 2: Semantic Profiling - Sinh metadata cho mỗi Unit
        Đây là phần QUAN TRỌNG NHẤT của High-level
        """
        system_prompt = """Bạn là chuyên gia giáo dục, phân tích nội dung học tập.
Nhiệm vụ: Sinh Semantic Profile cho một Learning Unit.

Profile này dùng để:
- Lập lộ trình học tập
- Đánh giá độ khó
- Xác định mức độ quan trọng cho thi cử
- Xác định prerequisites và relationships

Output PHẢI là JSON object hợp lệ."""

        user_prompt = f"""Phân tích Learning Unit sau:

=== UNIT TITLE ===
{unit_title}

=== COURSE CONTEXT ===
{course_context}

=== UNIT CONTENT ===
{unit_content[:15000]}

=== OUTPUT FORMAT ===
{{
    "difficulty": <1-5, 1=rất dễ, 5=rất khó>,
    "importance": <1-5, 1=ít quan trọng, 5=cực kỳ quan trọng>,
    "learning_time_minutes": <số phút cần để học unit này>,
    "exam_frequency": <1-5, tần suất xuất hiện trong đề thi>,
    "bloom_level": <1-6, theo Bloom's Taxonomy>,
    
    "summary": "<tóm tắt 2-3 câu>",
    
    "key_topics": ["topic1", "topic2", ...],  // 3-7 topics chính
    "keywords": ["keyword1", ...],  // 5-15 keywords cho search
    
    "prerequisites_description": ["Mô tả kiến thức cần có trước"],
    "prerequisite_unit_ids": [],  // Để trống, sẽ resolve sau
    
    "related_topics": ["Topic liên quan ngoài unit này"],
    
    "learning_objectives": [
        "Sau khi học xong, người học có thể...",
        "..."
    ],
    
    "skills_required": ["đọc hiểu", "ghi nhớ", ...],
    "skills_developed": ["phân tích", "so sánh", ...]
}}

Chỉ trả về JSON, không giải thích."""

        response = self._call_llm(system_prompt, user_prompt)
        
        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            profile = json.loads(response)
            return profile
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse profile JSON: {e}")
            return {}
    
    def resolve_prerequisites(self, all_units: List[Dict]) -> List[Dict]:
        """
        STEP 3: Resolve prerequisites giữa các units
        LLM xác định unit nào cần học trước unit nào
        """
        system_prompt = """Bạn là chuyên gia thiết kế chương trình học.
Nhiệm vụ: Xác định quan hệ prerequisite giữa các Learning Units.

Unit A là prerequisite của Unit B nếu:
- Cần hiểu A trước khi học B
- A cung cấp kiến thức nền tảng cho B
- B sử dụng concepts từ A

Output: JSON mapping unit_id -> list of prerequisite unit_ids"""

        # Tạo summary của all units
        units_summary = "\n".join([
            f"- {u['unit_id']}: {u['title']} | Topics: {u.get('key_topics', [])}"
            for u in all_units
        ])

        user_prompt = f"""Xác định prerequisites cho các units sau:

=== DANH SÁCH UNITS ===
{units_summary}

=== OUTPUT FORMAT ===
{{
    "unit_id_1": ["prerequisite_unit_id_a", "prerequisite_unit_id_b"],
    "unit_id_2": [],  // Không có prerequisite
    ...
}}

Chỉ trả về JSON, không giải thích."""

        response = self._call_llm(system_prompt, user_prompt)
        
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            prerequisites_map = json.loads(response)
            
            # Update units với prerequisites
            for unit in all_units:
                unit_id = unit["unit_id"]
                if unit_id in prerequisites_map:
                    unit["prerequisites"] = prerequisites_map[unit_id]
            
            return all_units
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse prerequisites: {e}")
            return all_units
    
    def identify_relationships(self, all_units: List[Dict]) -> List[Tuple[str, str, str]]:
        """
        STEP 4: Xác định relationships (related, similar, contrasts...)
        """
        system_prompt = """Bạn là chuyên gia phân tích kiến thức.
Xác định các quan hệ giữa Learning Units:

Loại quan hệ:
- RELATED: Liên quan về nội dung
- SIMILAR: Tương tự nhau
- CONTRASTS: Đối lập/so sánh
- EXTENDS: Mở rộng từ unit khác
- APPLIES: Áp dụng kiến thức từ unit khác

Output: JSON array of [source_id, relationship, target_id]"""

        units_summary = "\n".join([
            f"- {u['unit_id']}: {u['title']} | Summary: {u.get('summary', '')[:100]}"
            for u in all_units
        ])

        user_prompt = f"""Xác định relationships:

=== UNITS ===
{units_summary}

=== OUTPUT ===
[
    ["CH1_U1", "RELATED", "CH1_U2"],
    ["CH2_U1", "EXTENDS", "CH1_U3"],
    ...
]

Chỉ trả về JSON array."""

        response = self._call_llm(system_prompt, user_prompt)
        
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            relationships = json.loads(response)
            return [tuple(r) for r in relationships]
        except:
            return []

    # =========================================================================
    # HIGH-LEVEL LIGHTRAG METHODS - Entity & Relation Extraction
    # =========================================================================
    
    def _clean_json_response(self, response: str) -> str:
        """Clean LLM response to extract valid JSON"""
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        return response.strip()
    
    def extract_entities_from_chunk(self, chunk_content: str) -> List[Dict]:
        """
        STEP 1: Extract entities from a single chunk
        Returns list of entities with name, type, description
        """
        user_prompt = ENTITY_EXTRACTION_USER_PROMPT.format(
            chunk_content=chunk_content[:8000]  # Limit token
        )
        
        try:
            response = self._call_llm(
                ENTITY_EXTRACTION_SYSTEM_PROMPT, 
                user_prompt
            )
            response = self._clean_json_response(response)
            print(f'LLM Entity Extraction Response for chunk content: {chunk_content[:100]}')
            print(response)
            entities = json.loads(response)
            
            # Validate and clean entities
            valid_entities = []
            for entity in entities:
                if isinstance(entity, dict) and "name" in entity:
                    valid_entities.append({
                        "name": entity.get("name", "").strip(),
                        "type": entity.get("type", "CONCEPT"),
                        "description": entity.get("description", "")
                    })
            
            return valid_entities
        except Exception as e:
            self.logger.error(f"Entity extraction failed: {e}")
            return []

    async def aextract_entities_from_chunk(self, chunk_content: str) -> List[Dict]:
        """Async version of extract_entities_from_chunk"""
        user_prompt = ENTITY_EXTRACTION_USER_PROMPT.format(
            chunk_content=chunk_content[:8000]
        )
        
        try:
            response = await self._acall_llm(
                ENTITY_EXTRACTION_SYSTEM_PROMPT, 
                user_prompt
            )
            response = self._clean_json_response(response)
            logger.info(f'Async Entity Extraction for chunk: {chunk_content[:100]}')
            entities = json.loads(response)
            
            valid_entities = []
            for entity in entities:
                if isinstance(entity, dict) and "name" in entity:
                    valid_entities.append({
                        "name": entity.get("name", "").strip(),
                        "type": entity.get("type", "CONCEPT"),
                        "description": entity.get("description", "")
                    })
            
            return valid_entities
        except Exception as e:
            self.logger.error(f"Async entity extraction failed: {e}")
            return []
    
    def extract_relations_from_chunk(self, entities: List[Dict], chunk_content: str) -> List[Dict]:
        """
        STEP 2: Extract relations between entities based on chunk context
        """
        if len(entities) < 2:
            return []
        
        entities_text = "\n".join([
            f"- {e['name']} ({e['type']}): {e.get('description', '')}"
            for e in entities
        ])
        # logger.info(f"Extracting relations for entities: {entities_text}")
        
        user_prompt = RELATION_EXTRACTION_USER_PROMPT.format(
            entities=entities_text,
            chunk_content=chunk_content[:6000]
        )
        
        try:
            valid_relations = []
            entity_names = {e["name"].lower() for e in entities}
            
            for attempt in range(1, 4):
                try:
                    response = self._call_llm(
                        RELATION_EXTRACTION_SYSTEM_PROMPT,
                        user_prompt
                    )
                    response = self._clean_json_response(response)
                    logger.info(f"LLM Relation Extraction Response (attempt {attempt}): {response}")
                    
                    relations = json.loads(response)
                    
                    for rel in relations:
                        if isinstance(rel, dict):
                            source = rel.get("source", "").strip()
                            target = rel.get("target", "").strip()
                            relation_type = rel.get("relation", "RELATED_TO")
                            
                            if source.lower() in entity_names and target.lower() in entity_names:
                                valid_relations.append({
                                    "source": source,
                                    "relation": relation_type,
                                    "target": target,
                                    "description": rel.get("description", "")
                                })
                    
                    if valid_relations:
                        return valid_relations
                    
                    logger.warning(f"Attempt {attempt}: No valid relations extracted, retrying...")
                
                except json.JSONDecodeError as e:
                    logger.error(f"Attempt {attempt}: Failed to parse relations JSON: {e}")
                except Exception as e:
                    logger.error(f"Attempt {attempt}: LLM call failed: {e}")
            
            logger.warning("All 3 attempts exhausted, returning empty relations.")
            return valid_relations

        except Exception as e:
            self.logger.error(f"Relation extraction failed: {e}")
            return []

    async def aextract_relations_from_chunk(self, entities: List[Dict], chunk_content: str) -> List[Dict]:
        """Async version of extract_relations_from_chunk"""
        if len(entities) < 2:
            return []
        
        entities_text = "\n".join([
            f"- {e['name']} ({e['type']}): {e.get('description', '')}"
            for e in entities
        ])
        
        user_prompt = RELATION_EXTRACTION_USER_PROMPT.format(
            entities=entities_text,
            chunk_content=chunk_content[:6000]
        )
        
        try:
            valid_relations = []
            entity_names = {e["name"].lower() for e in entities}
            
            for attempt in range(1, 4):
                try:
                    response = await self._acall_llm(
                        RELATION_EXTRACTION_SYSTEM_PROMPT,
                        user_prompt
                    )
                    response = self._clean_json_response(response)
                    logger.info(f"Async Relation Extraction (attempt {attempt}): {response}")
                    
                    relations = json.loads(response)
                    
                    for rel in relations:
                        if isinstance(rel, dict):
                            source = rel.get("source", "").strip()
                            target = rel.get("target", "").strip()
                            relation_type = rel.get("relation", "RELATED_TO")
                            
                            if source.lower() in entity_names and target.lower() in entity_names:
                                valid_relations.append({
                                    "source": source,
                                    "relation": relation_type,
                                    "target": target,
                                    "description": rel.get("description", "")
                                })
                    
                    if valid_relations:
                        return valid_relations
                    
                    logger.warning(f"Attempt {attempt}: No valid relations extracted, retrying...")
                
                except json.JSONDecodeError as e:
                    logger.error(f"Attempt {attempt}: Failed to parse relations JSON: {e}")
                except Exception as e:
                    logger.error(f"Attempt {attempt}: Async LLM call failed: {e}")
            
            logger.warning("All 3 attempts exhausted, returning empty relations.")
            return valid_relations

        except Exception as e:
            self.logger.error(f"Async relation extraction failed: {e}")
            return []
    
    def identify_merge_candidates(self, all_entities: List[Dict]) -> List[Dict]:
        """
        STEP 3: Identify entity pairs that should be merged (same concept, different names)
        """
        if len(all_entities) < 2:
            return []
        
        # Get unique entity names
        unique_names = list(set([e["name"] for e in all_entities]))
        
        if len(unique_names) < 2:
            return []
        
        entities_text = "\n".join([f"- {name}" for name in unique_names[:100]])  # Limit
        
        user_prompt = CONCEPT_MERGE_USER_PROMPT.format(entities=entities_text)
        
        try:
            response = self._call_llm(
                CONCEPT_MERGE_SYSTEM_PROMPT,
                user_prompt
            )
            response = self._clean_json_response(response)
            merge_candidates = json.loads(response)
            
            return merge_candidates if isinstance(merge_candidates, list) else []
        except Exception as e:
            self.logger.error(f"Merge identification failed: {e}")
            return []
    
    def generate_merged_description(self, concept_name: str, descriptions: List[str]) -> str:
        """Generate a unified description from multiple descriptions (legacy)"""
        if not descriptions:
            return ""
        
        if len(descriptions) == 1:
            return descriptions[0]
        
        descriptions_text = "\n".join([f"- {desc}" for desc in descriptions[:10]])
        
        system_prompt = "Ban la chuyen gia tong hop kien thuc. Tao description tong hop cho concept. Chi tra ve 1 doan description."
        user_prompt = f'Tong hop description cho concept "{concept_name}":\n{descriptions_text}'
        
        try:
            response = self._call_llm(
                system_prompt,
                user_prompt
            )
            return response.strip()
        except Exception as e:
            self.logger.error(f"Description generation failed: {e}")
            return descriptions[0] if descriptions else ""
    
    def expand_query(self, query: str) -> Dict:
        """
        Expand user query into keywords for high-level retrieval
        """
        user_prompt = QUERY_EXPANSION_USER_PROMPT.format(query=query)
        
        try:
            response = self._call_llm(
                QUERY_EXPANSION_SYSTEM_PROMPT,
                user_prompt
            )
            response = self._clean_json_response(response)
            expanded = json.loads(response)
            
            return {
                "main_concepts": expanded.get("main_concepts", []),
                "related_keywords": expanded.get("related_keywords", []),
                "question_type": expanded.get("question_type", "GENERAL")
            }
        except Exception as e:
            self.logger.error(f"Query expansion failed: {e}")
            return {
                "main_concepts": [query],
                "related_keywords": [],
                "question_type": "GENERAL"
            }

if __name__ == "__main__":
    # Example usage
    llm_service = LLMService()
    sample_text = "Machine learning is a field of artificial intelligence that uses statistical techniques to give computer systems the ability to 'learn' from data, without being explicitly programmed."
    
    entities = llm_service.extract_entities_from_chunk(sample_text)
    print("Extracted Entities:", entities)