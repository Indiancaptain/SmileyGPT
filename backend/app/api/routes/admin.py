from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.models import Conversation, Message, User, UserRole
from app.schemas.schemas import AdminStats, UserOut

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


class RoleUpdate(BaseModel):
    role: UserRole


async def _get_user_or_404(user_id: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.get("/stats", response_model=AdminStats)
async def stats(db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    total_conversations = (await db.execute(select(func.count(Conversation.id)))).scalar_one()
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar_one()

    since = datetime.now(timezone.utc) - timedelta(days=1)
    active_today = (
        await db.execute(select(func.count(func.distinct(Conversation.user_id))).where(Conversation.updated_at >= since))
    ).scalar_one()

    return AdminStats(
        total_users=total_users,
        total_conversations=total_conversations,
        total_messages=total_messages,
        active_today=active_today,
    )


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.patch("/users/{user_id}/toggle-active", response_model=UserOut)
async def toggle_active(user_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account")

    user = await _get_user_or_404(user_id, db)
    user.is_active = not user.is_active
    await db.commit()
    await db.refresh(user)
    logger.info(f"Admin {admin.email} set is_active={user.is_active} for user {user.email}")
    return user


@router.patch("/users/{user_id}/role", response_model=UserOut)
async def update_role(user_id: str, payload: RoleUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    if user_id == admin.id and payload.role != UserRole.admin:
        # Prevents an admin from demoting themselves and losing dashboard
        # access with no other admin able to promote them back.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot remove your own admin role")

    user = await _get_user_or_404(user_id, db)
    user.role = payload.role
    await db.commit()
    await db.refresh(user)
    logger.info(f"Admin {admin.email} set role={user.role.value} for user {user.email}")
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot delete your own account")

    user = await _get_user_or_404(user_id, db)
    logger.info(f"Admin {admin.email} deleted user {user.email}")
    await db.delete(user)  # cascades to conversations/messages/files via FK ondelete
    await db.commit()
