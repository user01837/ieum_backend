from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models.chat import ChatRoom, ChatRoomMember
from app.services import chat_service

router = APIRouter()


class CreateRoomRequest(BaseModel):
    member_ids: list[str] = Field(..., min_length=1, description="나를 제외한 참여자 사번 목록")
    name: Optional[str] = Field(None, description="그룹방 이름 (그룹일 때만 사용, 1:1이면 무시)")


class RoomResponse(BaseModel):
    room_id: int
    name: Optional[str]
    is_group: bool
    member_ids: list[str]


class RoomListItem(BaseModel):
    room_id: int
    name: Optional[str]
    is_group: bool
    member_ids: list[str]
    last_message: Optional[str]
    last_message_at: Optional[str]
    unread_count: int


class AddMembersRequest(BaseModel):
    member_ids: list[str] = Field(..., min_length=1, description="추가할 참여자 사번 목록")


class RenameRoomRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="새 채팅방 이름")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("공백만으로는 채팅방 이름을 지정할 수 없습니다.")
        return stripped


@router.post("/rooms", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    req: CreateRoomRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invalid_ids = [
        uid for uid in req.member_ids
        if not db.query(User.user_id).filter(User.user_id == uid).first()
    ]
    if invalid_ids:
        raise HTTPException(status_code=400, detail=f"존재하지 않는 사용자: {invalid_ids}")

    # 생성자를 제외한 실제 참여자가 있는지 확인
    # USER.user_id는 실제 DB에서 int라 current_user.user_id도 ORM에서 int로 돌아온다.
    # req.member_ids(문자열 목록)와 비교하려면 str로 맞춰야 한다.
    actual_member_ids = [uid for uid in req.member_ids if uid != str(current_user.user_id)]
    if not actual_member_ids:
        raise HTTPException(status_code=400, detail="채팅 상대를 1명 이상 지정해야 합니다.")

    room = chat_service.create_room(db, str(current_user.user_id), req.member_ids, req.name)
    member_ids = [
        str(m.user_id)
        for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room.room_id).all()
    ]
    return RoomResponse(room_id=room.room_id, name=room.name, is_group=room.is_group, member_ids=member_ids)


@router.get("/rooms", response_model=list[RoomListItem])
def list_rooms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rooms = chat_service.list_rooms_for_user(db, str(current_user.user_id))
    return [RoomListItem(**r) for r in rooms]


class MessageResponse(BaseModel):
    message_id: int
    room_id: int
    sender_id: str
    content: str
    created_at: str


@router.get("/rooms/{room_id}/messages", response_model=list[MessageResponse])
def get_room_messages(
    room_id: int,
    before_message_id: Optional[int] = Query(None),
    size: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not chat_service.is_room_member(db, room_id, str(current_user.user_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 채팅방의 멤버가 아닙니다.")

    messages = chat_service.get_messages(db, room_id, before_message_id, size)
    return [
        MessageResponse(
            message_id=m.message_id,
            room_id=m.room_id,
            sender_id=str(m.sender_id),
            content=m.content,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@router.post("/rooms/{room_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_room_read_endpoint(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not chat_service.is_room_member(db, room_id, str(current_user.user_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 채팅방의 멤버가 아닙니다.")
    chat_service.mark_room_read(db, room_id, str(current_user.user_id))


@router.post("/rooms/{room_id}/members", response_model=RoomResponse)
def add_room_members(
    room_id: int,
    req: AddMembersRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    room = db.query(ChatRoom).filter(ChatRoom.room_id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="존재하지 않는 채팅방입니다.")

    if not chat_service.is_room_member(db, room_id, str(current_user.user_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 채팅방의 멤버가 아닙니다.")

    if not room.is_group:
        raise HTTPException(status_code=400, detail="1:1 채팅방에는 인원을 추가할 수 없습니다.")

    invalid_ids = [
        uid for uid in req.member_ids
        if not db.query(User.user_id).filter(User.user_id == uid).first()
    ]
    if invalid_ids:
        raise HTTPException(status_code=400, detail=f"존재하지 않는 사용자: {invalid_ids}")

    chat_service.add_members_to_room(db, room_id, req.member_ids)

    member_ids = [
        str(m.user_id)
        for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room_id).all()
    ]
    return RoomResponse(room_id=room.room_id, name=room.name, is_group=room.is_group, member_ids=member_ids)


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def leave_room_endpoint(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not chat_service.is_room_member(db, room_id, str(current_user.user_id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="존재하지 않는 채팅방이거나 이미 나간 방입니다.")

    chat_service.leave_room(db, room_id, str(current_user.user_id))


@router.patch("/rooms/{room_id}", response_model=RoomResponse)
def rename_room_endpoint(
    room_id: int,
    req: RenameRoomRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    room = db.query(ChatRoom).filter(ChatRoom.room_id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="존재하지 않는 채팅방입니다.")

    if not chat_service.is_room_member(db, room_id, str(current_user.user_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 채팅방의 멤버가 아닙니다.")

    room = chat_service.rename_room(db, room, req.name)

    member_ids = [
        str(m.user_id)
        for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room_id).all()
    ]
    return RoomResponse(room_id=room.room_id, name=room.name, is_group=room.is_group, member_ids=member_ids)
