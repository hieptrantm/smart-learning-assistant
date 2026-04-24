from pydantic import BaseModel
from typing import Any, Dict, Any, List, Optional

class Message(BaseModel):
    role: str
    content: str
    
        
class ChatRequest(BaseModel):
    question: str
    user_id: int = 2
    conversation_id: int = 2
    n_last_messages: int = 5
    stream: bool = True
    
class ChatResponse(BaseModel):
    id: str
    reply: str
    created: int

class ModelData(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str

class ModelList(BaseModel):
    object: str = "list"
    data: List[ModelData]
    
class QuestionOption(BaseModel):
    optionKey: str
    optionText: str
    isCorrect: Optional[bool] = False

class Question(BaseModel):
    type: int
    text: str
    explanation: Optional[str] = None
    options: Optional[List[QuestionOption]] = None  
    
class GenerateQuizResponse(BaseModel):  
	success: bool
	request_id: str
	saved_dir: str
	quiz_data: List[Question]