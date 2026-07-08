import asyncio
import base64
import json
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user
from app.db.session import AsyncSessionLocal, get_db
from app.models.models import Conversation, Message, MessageRole, UploadedFile, User
from app.schemas.schemas import ChatRequest
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service

router = APIRouter(prefix="/chat", tags=["chat"])

MAX_HISTORY_MESSAGES = 20
MAX_IMAGE_ATTACHMENTS = 4


async def _load_image_attachments(attachment_ids: list[str], user: User, db: AsyncSession) -> list[dict]:
    """Fetches owned uploaded files that are images and returns them as
    OpenAI-format image_url content blocks. Non-image or missing files
    are silently skipped rather than failing the whole request."""
    if not attachment_ids:
        return []

    result = await db.execute(
        select(UploadedFile).where(UploadedFile.id.in_(attachment_ids[:MAX_IMAGE_ATTACHMENTS]), UploadedFile.user_id == user.id)
    )
    blocks = []
    for f in result.scalars().all():
        if not f.content_type.startswith("image/"):
            continue
        if not os.path.exists(f.storage_path):
            continue

        def _read_and_encode(path=f.storage_path):
            with open(path, "rb") as fh:
                return base64.b64encode(fh.read()).decode("utf-8")

        encoded = await asyncio.to_thread(_read_and_encode)
        blocks.append({"type": "image_url", "image_url": {"url": f"data:{f.content_type};base64,{encoded}"}})
    return blocks


@router.post("/stream")
async def stream_chat(payload: ChatRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Resolve or create the conversation
    if payload.conversation_id:
        result = await db.execute(select(Conversation).where(Conversation.id == payload.conversation_id, Conversation.user_id == user.id))
        convo = result.scalar_one_or_none()
        if not convo:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    else:
        convo = Conversation(user_id=user.id, title=payload.message[:60], model=payload.model or user.preferred_model)
        db.add(convo)
        await db.commit()
        await db.refresh(convo)

    image_blocks = await _load_image_attachments(payload.attachment_ids, user, db)

    # Persist the user's message immediately (attachments recorded for history/UI display)
    user_msg = Message(
        conversation_id=convo.id,
        role=MessageRole.user,
        content=payload.message,
        attachments=json.dumps(payload.attachment_ids),
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # Build context: recent history + retrieved long-term memory
    history_result = await db.execute(
        select(Message).where(Message.conversation_id == convo.id).order_by(Message.created_at.desc()).limit(MAX_HISTORY_MESSAGES)
    )
    history = list(reversed(history_result.scalars().all()))

    messages = [{"role": "system", "content": "You are SmileyGPT, a helpful, concise AI assistant."}]

    if payload.use_memory:
        memories = await memory_service.retrieve(user.id, payload.message)
        if memories:
            memory_block = "\n".join(f"- {m}" for m in memories)
            messages.append({"role": "system", "content": f"Relevant long-term memory about this user:\n{memory_block}"})

    # Prior turns stay plain-text; only the current turn carries image blocks
    messages += [{"role": m.role.value, "content": m.content} for m in history[:-1]] if history else []

    if image_blocks:
        messages.append({"role": "user", "content": [{"type": "text", "text": payload.message}, *image_blocks]})
    else:
        messages.append({"role": "user", "content": payload.message})

    conversation_id = convo.id
    model = payload.model or convo.model
    has_images = len(image_blocks) > 0

    async def event_generator():
        full_response = ""
        yield f"event: start\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"
        try:
            async for token in llm_service.stream_chat(messages, model=model, has_images=has_images):
                full_response += token
                yield f"event: token\ndata: {json.dumps({'content': token})}\n\n"
        finally:
            # Persist assistant message in its own session (request-scoped
            # session may have already been used for the generator's setup)
            async with AsyncSessionLocal() as save_db:
                assistant_msg = Message(conversation_id=conversation_id, role=MessageRole.assistant, content=full_response)
                save_db.add(assistant_msg)
                await save_db.commit()

            # True fire-and-forget: schedule the memory write as a background
            # task so the client's 'done' event isn't held up waiting on an
            # embedding computation. Exceptions are already caught and logged
            # inside add_memory, so an unretrieved-task-exception is not a risk.
            asyncio.create_task(
                memory_service.add_memory(
                    user.id,
                    f"User asked: {payload.message}\nAssistant replied: {full_response[:500]}",
                    {"conversation_id": conversation_id, "message_id": user_msg.id},
                )
            )
            yield f"event: done\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
