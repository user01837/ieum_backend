from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional
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

# --- 유사 민원 검색 스키마 ---

class SimilarPetitionsRequest(BaseModel):
    """유사 민원 검색 요청 스키마 (프론트엔드 -> 백엔드)"""
    title: str = Field(..., description="현재 민원의 제목")
    content: str = Field(..., description="현재 민원의 내용")
    department_code: str = Field(..., description="현재 민원의 부서 코드")
    top_k: int = Field(2, description="반환할 최대 결과 수")
    exclude_ids: List[int] = Field([], description="결과에서 제외할 민원 ID 목록")
    min_similarity: float = Field(0.0, description="최소 유사도 (0.0 ~ 100.0)")

class SimilarPetitionResult(BaseModel):
    """유사 민원 검색 결과 항목"""
    complaint_id: int
    title: str
    content: str
    answer: str
    department_code: str
    domain_code: str
    status_code: str
    similarity: float
    rerank_score: float

class SimilarPetitionsResponse(BaseModel):
    """유사 민원 검색 응답 스키마"""
    results: List[SimilarPetitionResult]

# --- 답변 초안 생성 스키마 ---

class DraftAnswerRequest(BaseModel):
    """답변 초안 생성 요청 스키마 (프론트엔드 -> 백엔드)"""
    title: str = Field(..., description="현재 민원의 제목")
    content: str = Field(..., description="현재 민원의 내용")
    department_code: str = Field(..., description="현재 민원의 부서 코드")

class DraftAnswerResponse(BaseModel):
    """답변 초안 생성 응답 스키마"""
    draft: str
    guardrail_triggered: bool
    needs_review: bool

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

@router.post(
    "/draft-answer",
    response_model=DraftAnswerResponse,
    summary="AI 모델 중계 - 답변 초안 생성",
    description="유사 사례를 바탕으로 민원 답변 초안을 생성합니다."
)
async def create_draft_answer(
    request: DraftAnswerRequest,
    current_user: User = Depends(get_current_user)
):
    """
    프론트엔드로부터 민원 제목, 내용을 받아 AI 서버에 답변 초안 생성을 요청하고,
    그 결과를 다시 프론트엔드에 반환합니다.
    """
    async with httpx.AsyncClient() as client:
        try:
            # 1. 프론트에서 받은 제목과 내용을 합쳐 AI가 사용할 complaint_text 생성
            complaint_text = f"{request.title}\n{request.content}"

            # 2. AI 서버로 보낼 요청 데이터 구성
            ai_request_payload = {
                "complaint_text": complaint_text,
                "department_code": request.department_code,
            }

            # 3. AI 서버 엔드포인트 URL 구성 (실제 AI 서버 경로에 따라 수정 필요)
            ai_endpoint_url = f"{settings.AI_SERVER.rstrip('/')}/api/draft"

            # 4. AI 서버에 POST 요청 전송 (생성 작업이므로 타임아웃을 길게 설정)
            response = await client.post(ai_endpoint_url, json=ai_request_payload, timeout=120.0)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"AI 서버에 연결할 수 없습니다: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"AI 서버에서 오류가 발생했습니다: {exc.response.text}")

@router.post(
    "/similar-petitions",
    response_model=SimilarPetitionsResponse,
    summary="AI 모델 중계 - 유사 민원 검색",
    description="민원 내용과 유사한 과거 민원 사례를 AI 서버를 통해 검색합니다."
)
async def find_similar_petitions(
    request: SimilarPetitionsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    프론트엔드로부터 민원 제목, 내용을 받아 AI 서버에 유사 사례 검색을 요청하고,
    그 결과를 다시 프론트엔드에 반환합니다.
    """
    async with httpx.AsyncClient() as client:
        try:
            # 1. 프론트에서 받은 제목과 내용을 합쳐 AI가 사용할 query_text 생성
            query_text = f"{request.title}\n{request.content}"

            # 2. AI 서버로 보낼 요청 데이터 구성
            ai_request_payload = {
                "query_text": query_text,
                "department_code": request.department_code,
                "top_k": request.top_k,
                "exclude_ids": request.exclude_ids,
                "min_similarity": request.min_similarity
            }

            # 3. AI 서버 엔드포인트 URL 구성
            ai_endpoint_url = f"{settings.AI_SERVER.rstrip('/')}/api/similar-cases"

            # 4. AI 서버에 POST 요청 전송
            response = await client.post(ai_endpoint_url, json=ai_request_payload, timeout=60.0)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"AI 서버에 연결할 수 없습니다: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"AI 서버에서 오류가 발생했습니다: {exc.response.text}")