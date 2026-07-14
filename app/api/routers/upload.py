from fastapi import APIRouter, Depends, UploadFile, File, status
from pydantic import BaseModel

from app.api.routers.auth import get_current_user
from app.services.s3_service import upload_file_to_s3

router = APIRouter()

class UploadResponse(BaseModel):
    fileName: str
    fileUrl: str

@router.post(
    "",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="파일 업로드",
    dependencies=[Depends(get_current_user)]
)
def upload_file(file: UploadFile = File(...)):
    """
    파일을 S3에 업로드하고, 업로드된 파일의 이름과 URL을 반환합니다.
    """
    file_url = upload_file_to_s3(file)
    return UploadResponse(fileName=file.filename, fileUrl=file_url)