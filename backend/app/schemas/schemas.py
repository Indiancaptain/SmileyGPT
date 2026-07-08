from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------- Auth ----------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


# ---------- User ----------
class UserOut(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    avatar_url: str
    role: str
    is_active: bool
    preferred_model: str
    theme: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    preferred_model: Optional[str] = None
    theme: Optional[str] = None


# ---------- Conversation ----------
class ConversationCreate(BaseModel):
    title: Optional[str] = "New Conversation"
    model: Optional[str] = None


class ConversationOut(BaseModel):
    id: str
    title: str
    model: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None


# ---------- Message ----------
class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    attachments: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
    model: Optional[str] = None
    attachment_ids: List[str] = []
    use_memory: bool = True


# ---------- Admin ----------
class AdminStats(BaseModel):
    total_users: int
    total_conversations: int
    total_messages: int
    active_today: int
