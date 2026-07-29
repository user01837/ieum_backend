# 채팅 기능 확장 (인원 추가 / 방 나가기 / 실시간 알림 수정 / 사업 단톡방 자동생성) 설계

## 배경

기존 1:1/그룹 채팅 + FCM 알림 기능 위에 4가지를 추가한다:

1. 기존 채팅방에 인원 즉시 추가
2. 채팅방 삭제(나가기) 기능
3. 실시간 알림 미반영 버그 수정
4. 사업(프로젝트) 협력자 추가 시 단톡방 자동 생성

동시에 팀원이 별도로 추가한 `ANNOUNCEMENT`(공지사항) 기능으로 인해 실제 운영 공유 DB
스키마가 우리가 마지막으로 캡처한 v36 DDL과 달라졌다. 라이브 DB(`ggieum`)를 직접
조회해 확인한 결과:

- `announcement` 테이블이 이미 존재함 (팀원이 직접 생성, 우리 코드베이스의 어느
  브랜치에도 이 테이블에 대응하는 SQLAlchemy 모델/라우터는 없음 - 별도 브랜치에서
  진행 중인 것으로 보임)
- `notification` 테이블에 `announcement_id`(nullable int, FK → announcement.announcement_id
  ON DELETE CASCADE) 컬럼이 이미 라이브로 추가되어 있음
- `notification.type`의 의미가 `CHAT_MESSAGE | ANNOUNCEMENT`로 확장됨

`ANNOUNCEMENT` 기능 자체(모델/라우터/프론트)는 이번 작업 범위가 아니다(팀원 소유,
아직 이 저장소에 병합되지 않음). 우리가 할 일은 우리 `Notification` 모델을
라이브 스키마와 일치시키는 것뿐이다.

## 1. 채팅방 인원 즉시 추가

**대상:** 그룹방(`is_group=True`)만. 1:1 방에 인원을 추가하면 그룹으로 성격이
바뀌는 문제가 생기므로 이번 범위에서 제외하고 400으로 거부한다.

**권한:** 이미 그 방의 멤버만 인원을 추가할 수 있다.

**엔드포인트:** `POST /chat/rooms/{room_id}/members`
- body: `{ "member_ids": ["20260010", "20260011"] }`
- 이미 멤버인 사번은 조용히 무시(중복 추가 안 함)
- 존재하지 않는 사번이 섞여 있으면 400
- 방이 1:1이면 400
- 요청자가 그 방 멤버가 아니면 403
- 응답: 갱신된 `RoomResponse`(room_id, name, is_group, member_ids)

**실시간 반영 범위:** 방 생성(`POST /chat/rooms`) 때도 상대방에게 WS로 즉시
알리지 않는 것이 기존 동작이므로(다음 폴링/재연결/포커스 시 반영), 인원 추가도
동일하게 맞춘다 - 추가한 사람 화면만 즉시 갱신하고, 새로 추가된 사람은 다음
새로고침/재연결/방 목록 재조회 시 방이 나타난다. WS 브로드캐스트 배관을 새로
만들지 않아 범위를 최소화한다.

**서비스 함수:** `chat_service.add_members_to_room(db, room_id, new_member_ids) -> ChatRoom`

**프론트:** 채팅창 헤더에 "+ 인원 추가" 버튼(그룹방일 때만 노출) → 기존
`EmployeeSearchModal`(multiSelect)을 열되 이미 멤버인 사람은 선택 목록에서 제외 →
확인 시 mutation 호출 → 성공하면 `chatRooms` 쿼리 무효화.

## 2. 채팅방 삭제 = 나만 나가기

카카오톡의 "채팅방 나가기"와 동일한 의미로 확정: 방 자체나 다른 멤버의 대화
기록에는 영향이 없고, 내 목록에서만 사라지고 더 이상 메시지/알림을 받지 않는다.
1:1/그룹 모두 동일하게 적용된다.

**엔드포인트:** `DELETE /chat/rooms/{room_id}`
- 요청자의 `ChatRoomMember` 행을 삭제(하드 삭제 - 별도 이력 컬럼 불필요, YAGNI)
- 요청자의 그 방에 대한 `Notification` 행도 함께 삭제(나간 방의 알림이 알림벨에
  남아있다가 클릭 시 403 나는 것 방지)
- 멤버가 아니면 404
- 이 액션으로 방의 남은 멤버 수가 0이 되어도 방/메시지 자체를 정리하지는 않는다
  (아무도 참조하지 않는 죽은 데이터가 남을 뿐 실질적 해는 없음 - YAGNI, 필요해지면
  별도 배치로 정리)

**서비스 함수:** `chat_service.leave_room(db, room_id, user_id) -> None`

**프론트:** 채팅방 목록의 각 방 항목에 나가기 아이콘/버튼 → 확인 다이얼로그 →
mutation 호출 → 성공 시 `chatRooms` 무효화, 나가는 방이 현재 선택된 방이면
`selectedRoomId`를 null로 되돌림.

## 3. 실시간 알림 미반영 버그 수정

**근본 원인:** 백엔드의 3-way 알림 분기(보는 중 / 다른 화면 / 오프라인)는 이미
정확하고 `test_ws_message_creates_notification_when_elsewhere` 등 기존 테스트로
검증되어 있다. 문제는 프론트 `useChatSocket.js`의 재연결 로직 -
`onopen` 핸들러가 재연결 시 `chatRoomMessages`/`chatRooms`는 무효화하면서
`notifications`는 빠뜨리고 있다. 소켓이 잠깐 끊겼다 재연결되는 동안(네트워크 순단,
백엔드 재시작, 노트북 절전 등) 생성된 알림은 30초 폴링 또는 수동 새로고침 전까지
화면에 나타나지 않는다.

**수정:** 재연결 시 무효화 목록에 `['notifications']`를 추가한다. 한 줄 수정이며
별도 설계 없이 바로 반영한다.

## 4. 사업(프로젝트) 협력자 추가 시 단톡방 자동 생성

**트리거 지점:**
- `POST /projects`(`create_project`): 최초 생성 시 협력자(`memberUserIds`)가 있으면
- `PATCH /projects/{id}`(`update_project`): `ids_to_add`(새로 추가된 협력자)가
  있으면

**방 재사용 추적:** `Project`에 `chat_room_id`(nullable int, FK →
`chat_room.room_id` ON DELETE SET NULL) 컬럼을 새로 추가한다. 이 컬럼으로 이후
협력자가 추가될 때 새 방을 또 만들지 않고 기존 방에 인원만 추가한다.

**동작:**
- 총 참여자(주관자 + 협력자)가 2명 이상이 될 때만 방을 만든다(1인 프로젝트는
  채팅 불필요).
- 방 이름: `f"[사업] {project.name}"`.
- `create_project`: 참여자가 2명 이상이면 `chat_service.create_room`으로 생성하고
  `project.chat_room_id`에 저장.
- `update_project`: `ids_to_add`가 있으면 -
  - `project.chat_room_id`가 이미 있으면 `chat_service.add_members_to_room`으로
    새 협력자만 추가
  - 없으면(최초 생성 시 협력자가 0명이라 방이 없었던 경우) 이 시점에
    주관자+현재 협력자 전원으로 새로 생성
- 협력자가 제거(`ids_to_remove`)되어도 채팅방 멤버십은 건드리지 않는다(요청
  범위 밖 - 채팅 접근을 강제로 뺏는 것은 별도 판단이 필요한 문제라 이번엔 다루지
  않음, 명시적으로 범위 제외).

**주의:** `project.py`가 `chat_service`를 직접 호출하는 구조로 간다(작은 기능
추가 규모에 별도 도메인 서비스 계층을 새로 만드는 것은 과설계).

## DB 변경사항 정리

| 변경 | 대상 | 방법 |
|---|---|---|
| `notification.announcement_id` 컬럼 반영 | `app/models/notification.py` | 모델만 수정 (라이브 DB엔 이미 존재 - 팀원이 추가함) |
| `project.chat_room_id` 컬럼 추가 | `app/models/project.py` + 라이브 DB | 모델 수정 + `ALTER TABLE` 스크립트로 라이브 DB에 실제 반영 (신규 컬럼, 우리가 처음 추가) |
| DDL 문서 갱신 | `docs/db/v39_공공이음_DDL_FK포함.sql` | 라이브 DB `SHOW CREATE TABLE` 재조회로 v36 문서를 대체 (기존 확립된 방법 - mojibake 원본 수동 디코딩 안 함) |

## 테스트 전략

- `chat_service.add_members_to_room` / `leave_room`: 단위 테스트 (신규 유닛)
- `POST /chat/rooms/{id}/members`, `DELETE /chat/rooms/{id}`: 라우터 통합 테스트
  (권한 실패 케이스 포함 - 비멤버 추가 시도, 1:1방 추가 시도, 비멤버 나가기 시도)
- `useChatSocket.js` 재연결 알림 무효화: 기존 재연결 테스트 패턴이 있다면 확장,
  없으면 수동 확인 근거를 report에 남김
- 프로젝트 단톡방 자동생성: `create_project`/`update_project` 통합 테스트에
  케이스 추가 (0명→2명 협력자, 기존 방에 추가 협력자, 1명 유지 시 방 미생성)

## 범위 제외 (YAGNI)

- `ANNOUNCEMENT` 기능 자체 구현 (팀원 소유, 별도 브랜치)
- 그룹방에서 특정 멤버 강제 추방(kick) 기능
- 인원 추가/나가기의 WS 실시간 브로드캐스트 (방 생성과 동일하게 폴링/재연결/포커스
  시 반영으로 충분 - 기존 동작과 일관성 유지)
- 프로젝트 협력자 제거 시 채팅방 멤버 자동 제거
- 마지막 멤버가 나간 빈 채팅방 자동 정리
