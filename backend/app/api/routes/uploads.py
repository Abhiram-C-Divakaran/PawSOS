from fastapi import APIRouter, Depends, UploadFile, File
from app.models.user import User
from app.config import settings
from app.api.dependencies import get_current_active_user
from app.services.storage_service import storage_service

router = APIRouter()

@router.post("/image", response_model=dict)
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    key = await storage_service.upload_image(file)
    preview_url = storage_service.get_presigned_url(
        key,
        expires_in=settings.S3_PRESIGNED_URL_EXPIRE_SECONDS
    )
    return {
        "image_url": key,
        "preview_url": preview_url,
        "key": key,
        "filename": file.filename
    }

