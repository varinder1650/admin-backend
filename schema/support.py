from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class SupportCategory(str, Enum):
    ORDER_INQUIRY = "order_inquiry"
    DELIVERY_ISSUE = "delivery_issue"
    PAYMENT_ISSUE = "payment_issue"
    PRODUCT_FEEDBACK = "product_feedback"
    APP_FEEDBACK = "app_feedback"
    TECHNICAL_ISSUE = "technical_issue"
    ACCOUNT_ISSUE = "account_issue"
    OTHER = "other"

class SupportTicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

class ProductRequestStatus(str, Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ADDED = "added"

class SupportTicketCreate(BaseModel):
    category: SupportCategory
    subject: str = Field(..., min_length=5, max_length=200)
    message: str = Field(..., min_length=10, max_length=2000)
    order_id: Optional[str] = None

class SupportTicketResponse(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    user_name: str
    user_email: str
    category: SupportCategory
    subject: str
    message: str
    order_id: Optional[str] = None
    status: SupportTicketStatus = SupportTicketStatus.OPEN
    admin_response: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True

class ProductRequestCreate(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=200)
    brand: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    description: str = Field(..., min_length=10, max_length=1000)
    # estimated_price: Optional[float] = Field(None, gt=0)
    # why_needed: str = Field(..., min_length=10, max_length=500)

class ProductRequestResponse(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    user_name: str
    user_email: str
    product_name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    description: str
    # estimated_price: Optional[float] = None
    # why_needed: str
    status: ProductRequestStatus = ProductRequestStatus.PENDING
    admin_notes: Optional[str] = None
    votes: int = 0  # Other users can upvote requests
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True

class TicketMessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)

class TicketMessage(BaseModel):
    _id: str
    message: str
    sender_type: str  # 'user' or 'admin'
    sender_name: str
    sender_id: str
    created_at: datetime
    attachments: Optional[List[str]] = []

class TicketDetailResponse(BaseModel):
    _id: str
    category: str
    subject: str
    message: str
    status: str
    priority: str = "medium"
    created_at: datetime
    updated_at: datetime
    user_id: str
    user_name: str
    user_email: str
    assigned_to: Optional[str] = None
    admin_response: Optional[str] = None
    messages: List[TicketMessage] = []
    order_id: Optional[str] = None