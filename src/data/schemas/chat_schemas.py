from pydantic import BaseModel
from typing import List, Any


class ChatRequest(BaseModel):
    message: str
    history: List[Any] = []
    chat_history: List[Any] = []


class ChatResponse(BaseModel):
    history: List[Any]
    reply: str
    chat_history: List[Any]
