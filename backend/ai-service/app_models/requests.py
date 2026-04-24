from pydantic import BaseModel, Field
from typing import List, Dict, Literal, Optional, Any
from fastapi import UploadFile

import config

class Message(BaseModel):
    role: str
    content: str

class S3UploadRequest(BaseModel):
    files: List[UploadFile]
    bucket_name: str
    prefix: str

class DeleteRequest(BaseModel):
    object_keys: List[str] = Field(..., min_length=1, description="A list of exact S3 object keys (e.g., 'prefix/file.pdf') whose corresponding vectors should be deleted.")
    tenant_id: str = Field(..., description="The ID of the tenant whose documents should be deleted.")

class DeleteAllRequest(BaseModel):
    object_keys: List[str] = Field(..., min_length=1, description="A list of exact S3 object keys (e.g., 'prefix/file.pdf') whose corresponding vectors should be deleted.")
    tenant_id: str = Field(..., description="The ID of the tenant whose documents should be deleted.")

class LoginRequest(BaseModel):
    username: str
    password: str
    
class QuestionRequest(BaseModel):
    question: str
    chat_history: List[Message]
    conversation_id: Optional[int] = None
    created_by: Optional[int] = None
    session_id: Optional[str] = None
    
class ChatRequest(BaseModel):
    question: str = "hello"
    user_id: int = 1
    subject_id: int = 1
    stream: bool = True
    lecture_title: str = ""
    lecture_content: str = ""
    
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

class ChatResponse(BaseModel):
    id: str
    reply: str
    created: int
