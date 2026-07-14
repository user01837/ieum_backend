import boto3
from botocore.exceptions import NoCredentialsError
from fastapi import UploadFile, HTTPException, status
import uuid

from app.core.config import settings

# 설정 파일에서 AWS 정보를 가져와 S3 클라이언트 생성
s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_S3_REGION
)

def upload_file_to_s3(file: UploadFile) -> str:
    """
    S3에 파일을 업로드하고 파일 URL을 반환합니다.
    """
    # 파일 이름이 중복되지 않도록 UUID를 사용하여 고유한 파일 키 생성
    file_key = f"petitions/{uuid.uuid4()}-{file.filename}"

    try:
        s3_client.upload_fileobj(
            file.file,
            settings.AWS_S3_BUCKET_NAME,
            file_key,
            ExtraArgs={
                "ContentType": file.content_type
            }
        )
        # 업로드된 파일의 URL 생성
        file_url = f"https://{settings.AWS_S3_BUCKET_NAME}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{file_key}"
        return file_url
    except NoCredentialsError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AWS 자격 증명을 찾을 수 없습니다.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"파일 업로드 중 오류 발생: {str(e)}")