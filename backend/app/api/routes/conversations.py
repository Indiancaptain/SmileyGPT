from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.models import Conversation, Message, User
from app.schemas.schemas import ConversationCreate, ConversationOut, ConversationUpdate, MessageOut

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def _get_owned_conversation(conversation_id: str, user: User, db: AsyncSession) -> Conversation:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id))
    convo = result.scalar_one_or_none()
    if not convo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return convo


@router.get("", response_model=List[ConversationOut])
async def list_conversations(
    q: Optional[str] = Query(None, description="Full-text search across titles and message content"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
    if q:
        # Search titles directly; join messages for content search
        subq = select(Message.conversation_id).where(Message.content.ilike(f"%{q}%"))
        stmt = stmt.where(or_(Conversation.title.ilike(f"%{q}%"), Conversation.id.in_(subq)))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: ConversationCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    convo = Conversation(user_id=user.id, title=payload.title or "New Conversation", model=payload.model or user.preferred_model)
    db.add(convo)
    await db.commit()
    await db.refresh(convo)
    return convo


@router.get("/{conversation_id}/messages", response_model=List[MessageOut])
async def get_messages(conversation_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _get_owned_conversation(conversation_id, user, db)
    result = await db.execute(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at))
    return result.scalars().all()


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(conversation_id: str, payload: ConversationUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    convo = await _get_owned_conversation(conversation_id, user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(convo, field, value)
    await db.commit()
    await db.refresh(convo)
    return convo


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    convo = await _get_owned_conversation(conversation_id, user, db)
    await db.delete(convo)
    await db.commit()
