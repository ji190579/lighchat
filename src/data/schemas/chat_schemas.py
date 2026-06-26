from pydantic import BaseModel
from typing import List, Any, Optional


class ChatRequest(BaseModel):
    message: str
    history: List[Any] = []
    chat_history: List[Any] = []


class ChatResponse(BaseModel):
    history: List[Any]
    reply: str
    chat_history: List[Any]


class ContactRequest(BaseModel):
    name: str
    email: str
    role: str
    experience: Optional[str] = ""
    topic: str
    challenge: str
    timeline: Optional[str] = ""
