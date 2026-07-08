from pydantic import BaseModel
from typing import Optional, Literal


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    customer_external_id: Optional[str] = None   # e.g. "web-guest-123", whatsapp number
    customer_name: Optional[str] = None
    channel: str = "web"


class AnalysisResult(BaseModel):
    intent: str
    sentiment: Literal["positive", "neutral", "negative", "frustrated"]
    sentiment_score: float
    language: str
    should_escalate: bool
    escalate_reason: Optional[str] = None


class TicketCreateResult(BaseModel):
    category: str
    priority: Literal["low", "medium", "high", "urgent"]
    priority_score: float
    summary: str
