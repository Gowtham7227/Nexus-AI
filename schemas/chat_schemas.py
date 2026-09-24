from typing import Any
from pydantic import BaseModel


class CreateConversationRequest(BaseModel):
    title: str | None = "New Conversation"


class UpdateConversationRequest(BaseModel):
    title: str


class ChatRequest(BaseModel):
    question: str
    filenames: list[str] | None = None
    filename: str | None = None
    conversation_id: int | None = None


class FeedbackRequest(BaseModel):
    conversation_id: int
    rating: Any
    message_id: int | None = None
    reason: str | None = None
    feedback_reason: str | None = None
    feedback_text: str | None = None
    note: str | None = None
    latency_perceived: str | None = None
    request_id: str | None = None
