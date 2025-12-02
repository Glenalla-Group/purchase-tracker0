"""
Email data models using Pydantic for validation and serialization.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PubSubMessage(BaseModel):
    """Pub/Sub message structure."""
    data: str  # Base64 encoded data
    messageId: str
    message_id: Optional[str] = None
    publishTime: Optional[str] = None
    publish_time: Optional[datetime] = None
    attributes: Optional[Dict[str, Any]] = None


class PubSubNotification(BaseModel):
    """Gmail Pub/Sub notification payload."""
    message: PubSubMessage
    subscription: str


class EmailData(BaseModel):
    """Structured email data."""
    message_id: str
    thread_id: str
    history_id: Optional[str] = None
    subject: str
    sender: str
    to: List[str] = Field(default_factory=list)
    cc: List[str] = Field(default_factory=list)
    date: Optional[str] = None
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    snippet: Optional[str] = None
    labels: List[str] = Field(default_factory=list)


class ExtractedInfo(BaseModel):
    """Information extracted from email HTML content."""
    email_id: str
    subject: str
    sender: str
    
    # Extracted data - customize based on your needs
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Example fields for purchase tracking
    order_number: Optional[str] = None
    total_amount: Optional[str] = None
    merchant: Optional[str] = None
    purchase_date: Optional[str] = None
    items: List[str] = Field(default_factory=list)
    
    # Metadata
    processed_at: datetime = Field(default_factory=datetime.now)
    extraction_successful: bool = True
    error_message: Optional[str] = None

