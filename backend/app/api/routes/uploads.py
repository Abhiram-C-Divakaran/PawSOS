from fastapi import APIRouter, Depends, UploadFile, File
from app.models.user import User
from app.api.dependencies import get_current_active_user
from app.services.storage_service import storage_service

router = APIRouter()

@router.post("/image", response_model=dict)
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    image_url = await storage_service.upload_image(file)
    return {
        "image_url": image_url,
        "filename": file.filename
    }
