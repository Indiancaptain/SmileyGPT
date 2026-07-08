import asyncio
import io
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.models import UploadedFile, User

logger = get_logger(__name__)
router = APIRouter(prefix="/files", tags=["files"])

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif", "application/pdf", "text/plain", "text/markdown"}
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


def _verify_file_contents(contents: bytes, claimed_type: str) -> bool:
    """
    The client-supplied Content-Type header is untrusted input — a
    malicious payload can claim to be `image/png` while actually being
    something else entirely. This checks the *actual* bytes match the
    claimed type before we persist the file or later feed it to the
    vision model as a trusted image.
    """
    if claimed_type in IMAGE_TYPES:
        try:
            with Image.open(io.BytesIO(contents)) as img:
                img.verify()
            return True
        except (UnidentifiedImageError, OSError, ValueError):
            return False

    if claimed_type == "application/pdf":
        return contents[:5] == b"%PDF-"

    # text/plain, text/markdown: any byte sequence can technically be
    # treated as text, so there's no meaningful magic-byte check here.
    return True


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported file type: {file.content_type}")

    if not file.filename:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "File must have a filename")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_MB:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"File exceeds {settings.MAX_UPLOAD_MB}MB limit")

    if not await asyncio.to_thread(_verify_file_contents, contents, file.content_type):
        logger.warning(f"Rejected upload from user {user.id}: content did not match claimed type {file.content_type}")
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "File content does not match its declared type",
        )

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{os.path.basename(file.filename)}"
    storage_path = os.path.join(settings.UPLOAD_DIR, safe_name)

    def _write():
        with open(storage_path, "wb") as f:
            f.write(contents)

    await asyncio.to_thread(_write)

    record = UploadedFile(
        user_id=user.id,
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=len(contents),
        storage_path=storage_path,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return {
        "id": record.id,
        "filename": record.filename,
        "content_type": record.content_type,
        "size_bytes": record.size_bytes,
        "is_image": record.content_type.startswith("image/"),
    }
