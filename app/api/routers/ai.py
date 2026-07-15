from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List
import httpx

from app.api.routers.auth import get_current_user
from app.models.user import User
from app.core.config import settings

class LegalChatRequest(BaseModel):
    """챗봇 질문 요청 스키마"""
    question: str = Field(..., description="사용자의 질문")

class ReferencedArticle(BaseModel):
    """참고 법령 정보 스키마"""
    law_title: str
    article_no: str
    article_title: str
    document: str
    similarity: float

class LegalChatResponse(BaseModel):
    """챗봇 답변 응답 스키마"""
    answer: str
    referenced_articles: List[ReferencedArticle]

# --- 라우터 ---

router = APIRouter()

@router.post(
    "/legal-chat",
    response_model=LegalChatResponse,
    summary="AI 모델 중계 - 법률 챗봇",
    description="프론트엔드의 요청을 AI 서버로 전달하고 그 결과를 반환하는 중계 API입니다."
)
async def proxy_legal_chat(
    request: LegalChatRequest,
    current_user: User = Depends(get_current_user) # API 보호를 위해 인증 추가
):
    """
    프론트엔드로부터 질문을 받아 AI 서버에 전달하고, 그 결과를 다시 프론트엔드에 반환합니다.
    """
    async with httpx.AsyncClient() as client:
        try:
            # AI 서버의 베이스 URL(settings.AI_SERVER)에 특정 엔드포인트 경로를 추가합니다.
            # .env.local의 AI_SERVER 값 예시: http://localhost:8001
            # 만약 AI 서버의 실제 경로가 다르다면 이 아랫줄의 경로를 수정해야 합니다.
            ai_endpoint_url = f"{settings.AI_SERVER.rstrip('/')}/api/legal-chat"

            # AI 서버에 POST 요청 전송
            response = await client.post(
                ai_endpoint_url,
                json={"question": request.question},
                timeout=60.0  # AI 응답 시간을 고려하여 타임아웃을 넉넉하게 설정
            )
            response.raise_for_status()  # 2xx가 아닌 응답 코드는 예외 발생
            return response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"AI 서버에 연결할 수 없습니다: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"AI 서버에서 오류가 발생했습니다: {exc.response.text}")