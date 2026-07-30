from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile, Form
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models.chat import ChatRoom, ChatRoomMember, ChatMessage
from app.services import chat_service
from app.models.chat_message_attachment import ChatMessageAttachment
from app.services.s3_service import upload_file_to_s3


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


class AttachmentInfo(BaseModel):
    attachment_id: int
    file_url: str
    file_name: str


class MessageResponse(BaseModel):
    message_id: int
    room_id: int
    sender_id: str
    content: Optional[str]
    created_at: str
    attachments: List[AttachmentInfo] = []

@router.post("/rooms/{room_id}/messages", response_model=MessageResponse, summary="메시지 및 파일 전송")
async def send_message_with_attachment(
    room_id: int,
    content: Optional[str] = Form(None),
    files: List[UploadFile] = File(None, description="첨부파일 목록"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    채팅방에 텍스트 메시지나 파일을 전송합니다.
    - 이 API를 통해 메시지가 생성되면, 백엔드에서는 웹소켓을 통해 해당 방의 모든 참여자에게 메시지를 전송(broadcast)해야 합니다.
    """
    if not content and not files:
        raise HTTPException(status_code=400, detail="메시지 내용이나 파일이 하나 이상 있어야 합니다.")

    if not chat_service.is_room_member(db, room_id, str(current_user.user_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 채팅방의 멤버가 아닙니다.")

    # 1. 메시지 생성
    new_message = ChatMessage(
        room_id=room_id,
        sender_id=current_user.user_id,
        content=content or "",
    )
    db.add(new_message)
    db.flush()  # message_id를 할당받기 위해 flush

    # 2. 첨부파일 처리
    db_attachments = []
    if files:
        for file in files:
            file_url = upload_file_to_s3(file, path_prefix="chat")
            attachment = ChatMessageAttachment(
                message_id=new_message.message_id,
                file_url=file_url,
                file_name=file.filename,
            )
            db.add(attachment)
            db_attachments.append(attachment)

    db.commit()
    db.refresh(new_message)

    # 3. 응답 데이터 구성
    attachment_infos = [
        AttachmentInfo(
            attachment_id=att.attachment_id,
            file_url=att.file_url,
            file_name=att.file_name
        ) for att in db_attachments
    ]

    # TODO: 웹소켓을 통해 이 메시지를 채팅방 참여자들에게 전송하는 로직 필요
    # chat_service.broadcast_message(room_id, new_message, attachment_infos)

    return MessageResponse(
        message_id=new_message.message_id,
        room_id=new_message.room_id,
        sender_id=str(new_message.sender_id),
        content=new_message.content,
        created_at=new_message.created_at.isoformat(),
        attachments=attachment_infos
    )

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
    if not messages:
        return []

    # N+1 문제를 방지하기 위해 첨부파일을 한 번의 쿼리로 가져옵니다.
    message_ids = [m.message_id for m in messages]
    attachments_result = db.query(ChatMessageAttachment).filter(
        ChatMessageAttachment.message_id.in_(message_ids)
    ).all()

    # 메시지 ID를 키로 하는 딕셔너리로 변환하여 쉽게 찾을 수 있도록 합니다.
    attachments_map = {}
    for att in attachments_result:
        if att.message_id not in attachments_map:
            attachments_map[att.message_id] = []
        attachments_map[att.message_id].append(AttachmentInfo(
            attachment_id=att.attachment_id,
            file_url=att.file_url,
            file_name=att.file_name
        ))

    # 최종 응답 데이터를 구성합니다.
    response = []
    for m in messages:
        response.append(MessageResponse(
            message_id=m.message_id,
            room_id=m.room_id,
            sender_id=str(m.sender_id),
            content=m.content,
            created_at=m.created_at.isoformat(),
            attachments=attachments_map.get(m.message_id, [])
        ))
    return response


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
