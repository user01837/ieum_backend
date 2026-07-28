# 직원 간 실시간 채팅 + FCM 푸시 알림 설계

- 작성일: 2026-07-28
- 대상 저장소: `ieum_backend`(API/WebSocket/FCM 발송), `ieum_frontend`(채팅 UI/알림벨/FCM 수신)
- 관련 문서: 없음 (신규 기능)

## 배경 / 목표

지금까지 `ieum_backend`에는 부서 간 소통 수단이 없다. 직원끼리(1:1 또는 여러 명) 실시간으로 대화할 수 있는 채팅 기능과, 새 메시지가 왔을 때 브라우저를 보고 있지 않아도 알 수 있도록 FCM 웹 푸시 알림을 추가한다.

성공 기준:
- 로그인한 두 직원이 같은 방에서 실시간으로 메시지를 주고받을 수 있다 (새로고침 없이).
- 여러 명을 묶은 그룹 채팅방을 만들 수 있다.
- 채팅방을 보고 있지 않은 동안 온 메시지는 헤더 알림벨에 뜨고, 아예 접속해 있지 않았다면 FCM 푸시로도 온다.

## 범위

**포함**
- 1:1 및 그룹(다자간) 텍스트 채팅
- 채팅방 생성(참여자 직접 선택), 목록 조회, 메시지 히스토리 조회
- WebSocket 기반 실시간 송수신
- 헤더 알림벨(새 채팅 메시지 알림 전용, 안읽음 배지)
- FCM 웹 푸시 (오프라인 사용자 대상)

**제외 (v1)**
- 파일/이미지 첨부
- 메시지 수정/삭제
- 읽음 확인(누가 읽었는지 표시) — 안읽음 "개수"만 관리, 읽은 사람 목록은 없음
- 타이핑 표시, 온라인 상태 표시 UI
- 채팅방 이름 변경, 멤버 추가/탈퇴 (그룹방은 생성 시 멤버 확정)
- 여러 서버 인스턴스로의 수평 확장 (현재 Dockerfile은 uvicorn 프로세스 1개 — 배포가 다중 인스턴스로 바뀌면 커넥션 매니저를 Redis pub/sub 등으로 교체해야 함, 이 설계 범위 밖)
- 모바일 네이티브 앱 푸시 (웹 푸시만)
- `type` 필드는 확장 가능하게 열어두지만, v1에서 실제로 발생시키는 알림은 `CHAT_MESSAGE` 하나뿐이다.

## 아키텍처

### 온라인 상태 & 실시간 전달

- 사용자는 로그인 후 앱 전역에서 WebSocket 연결을 하나 맺는다 (`/ws/chat?token=<accessToken>`). 특정 채팅방에 들어갈 때마다 새로 연결하지 않는다 — 그래야 다른 화면에 있어도 새 메시지 도착 시 알림벨을 실시간으로 갱신할 수 있다.
- 서버는 프로세스 메모리에 `user_id → set[WebSocket]`을 들고 있는 커넥션 매니저를 둔다 (탭을 여러 개 열면 여러 연결이 등록됨). 단일 uvicorn 프로세스로만 배포되므로 별도 pub/sub 없이 충분하다.
- 클라이언트는 채팅방에 들어가고 나갈 때 `{"type": "active_room", "room_id": <id | null>}` 를 보내 "지금 보고 있는 방"을 서버에 알린다. 서버는 연결별로 이 값을 들고 있는다.

### 메시지 전송 흐름

1. 클라이언트가 `{"type": "send_message", "room_id": R, "content": "..."}` 를 WS로 보낸다.
2. 서버는 발신자가 R의 멤버인지 검증 후 `CHAT_MESSAGE` 로 저장한다.
3. R의 다른 멤버 각각에 대해:
   - 그 유저의 WS 연결 중 `active_room == R` 인 게 있으면 → 그 연결들에 `new_message` 이벤트만 전송, 알림 생성 안 함.
   - 그 외 연결(다른 화면 보는 중, 즉 온라인이지만 이 방은 아님) → `new_message` 이벤트 전송 + `NOTIFICATION` row 생성 + 클라이언트에 `notification` 이벤트도 함께 전송(벨 실시간 갱신용).
   - 해당 유저의 WS 연결이 하나도 없음(오프라인) → `NOTIFICATION` row 생성 + 등록된 `DEVICE_TOKEN` 전체로 FCM 푸시 발송.
4. 발신자 본인에게는 `new_message` 이벤트를 그대로 echo 하여(자기 자신의 연결에도) 여러 탭 동기화를 지원한다.

### FCM 연동

- 백엔드: `firebase-admin` SDK. 서비스 계정 JSON 경로를 `FIREBASE_CREDENTIALS_PATH` 환경변수로 받아 앱 시작 시 `firebase_admin.initialize_app()` 한 번 호출.
- 프론트: Firebase JS SDK(`firebase/messaging`) + `public/firebase-messaging-sw.js` 서비스워커. 로그인 성공 시 알림 권한 요청 → `getToken(messaging, { vapidKey })` → `POST /notifications/device-token` 으로 등록. 로그아웃 시 `DELETE /notifications/device-token`.
- 발송 실패(토큰 만료 등)는 개별 토큰 단위로 무시하고 로깅만 한다 — 한 기기 실패가 다른 기기/인앱 알림에 영향을 주지 않는다.

## 데이터 모델

기존 컨벤션(ALL_CAPS 테이블명, `Integer` PK, `SQLAlchemy` declarative) 그대로 따른다.

```
CHAT_ROOM
  room_id        INT PK AUTOINCREMENT
  name           VARCHAR(100) NULL          -- 그룹방 이름, 없으면 프론트에서 멤버 이름 나열해 표시
  is_group       BOOLEAN NOT NULL            -- false=1:1, true=그룹
  created_by     VARCHAR(50) FK USER.user_id
  created_at     DATETIME

CHAT_ROOM_MEMBER
  room_id        INT FK CHAT_ROOM.room_id
  user_id        VARCHAR(50) FK USER.user_id
  joined_at      DATETIME
  PRIMARY KEY(room_id, user_id)

CHAT_MESSAGE
  message_id     INT PK AUTOINCREMENT
  room_id        INT FK CHAT_ROOM.room_id
  sender_id      VARCHAR(50) FK USER.user_id
  content        TEXT NOT NULL
  created_at     DATETIME

NOTIFICATION
  notification_id INT PK AUTOINCREMENT
  user_id          VARCHAR(50) FK USER.user_id   -- 수신자
  type             VARCHAR(20) NOT NULL           -- 'CHAT_MESSAGE' 고정 (v1)
  room_id          INT NULL FK CHAT_ROOM.room_id
  message_id       INT NULL FK CHAT_MESSAGE.message_id
  is_read          BOOLEAN NOT NULL DEFAULT FALSE
  created_at       DATETIME

DEVICE_TOKEN
  token_id       INT PK AUTOINCREMENT
  user_id        VARCHAR(50) FK USER.user_id
  fcm_token      VARCHAR(255) NOT NULL UNIQUE
  created_at     DATETIME
```

- 알림벨의 안읽음 배지와 채팅방 목록의 안읽음 카운트는 **모두 `NOTIFICATION.is_read`** 를 기준으로 계산한다 (별도 last_read 포인터를 두지 않아 로직이 하나로 통일됨). 방을 열면 `POST /chat/rooms/{room_id}/read` 로 그 방에 대한 내 `NOTIFICATION` 을 모두 `is_read=true` 로 바꾼다.
- 1:1 방 중복 생성 방지: 방 생성 요청의 참여자가 정확히 2명(요청자 포함)이고 `is_group=false` 로 만들 방이면, 그 두 명이 이미 멤버인 `is_group=false` 방이 있는지 먼저 조회하고 있으면 그걸 재사용한다.
- 새 테이블 4개는 alembic이 실사용되지 않는 현재 관례상 `Base.metadata.create_all(bind=engine)` 1회 스크립트로 생성한다 (기존 테이블은 이미 존재하므로 영향 없음).

## API

모든 REST 엔드포인트는 기존 관례대로 `Depends(get_current_user)` 로 인증한다.

| Method | Path | 설명 |
|---|---|---|
| POST | `/chat/rooms` | 참여자 user_id 목록(+ 그룹일 경우 선택적 `name`)으로 방 생성 (1:1 중복 시 기존 방 반환) |
| GET | `/chat/rooms` | 내 채팅방 목록 (마지막 메시지 미리보기, 안읽음 수, 멤버 이름) |
| GET | `/chat/rooms/{room_id}/messages` | 메시지 히스토리, `before_message_id` 커서 + `size` 페이지네이션 |
| POST | `/chat/rooms/{room_id}/read` | 해당 방의 내 알림 전부 읽음 처리 |
| GET | `/notifications` | 알림벨 드롭다운용 최근 알림 목록 (최근 N건) |
| POST | `/notifications/device-token` | FCM 토큰 등록 (있으면 upsert) |
| DELETE | `/notifications/device-token` | FCM 토큰 해제 (로그아웃 시, body에 토큰 값) |
| WS | `/ws/chat?token=<accessToken>` | 실시간 송수신 (`send_message`, `active_room`) / 서버→클라 (`new_message`, `notification`) |

WS 인증은 브라우저 WebSocket API가 커스텀 헤더를 지원하지 않으므로 쿼리 파라미터로 accessToken을 받아 기존 `jwt.decode` 로직과 동일하게 검증한다 (헤더 대신 쿼리라는 차이만 있음).

## 프론트엔드

- **사이드바**: 기존 `민원 처리` 등과 같은 스타일로 `채팅` 메뉴 추가 (`/chat`).
- **채팅 페이지**: 좌측 방 목록(안읽음 배지 포함) + 우측 메시지 스레드. "새 채팅" 버튼 클릭 시 기존 `EmpSearchModal` 재사용해 1명 이상 선택 → 방 생성 후 이동.
- **헤더**: `안녕하세요, {name}님` 왼쪽에 알림벨 아이콘 추가. 안읽음 개수 배지, 클릭 시 최근 알림 드롭다운. 알림 클릭 시 해당 채팅방으로 이동 + 읽음 처리.
- **`useChatSocket` 훅**: 로그인 상태에서 WS를 열고, `new_message`/`notification` 이벤트를 React Query 캐시(`chat/rooms`, `chat/rooms/{id}/messages`, `notifications`)에 반영. 라우팅으로 현재 보고 있는 room_id가 바뀔 때마다 `active_room` 메시지를 서버로 보낸다.
- **FCM**: 로그인 성공 후 알림 권한을 요청하고 토큰을 발급받아 백엔드에 등록. `firebase-messaging-sw.js` 를 `public/` 에 추가해 백그라운드 푸시를 처리한다.

## 사전 준비 (사용자가 직접 해야 하는 부분)

1. Firebase 콘솔에서 프로젝트 생성.
2. 프로젝트 설정 → 서비스 계정 → 새 비공개 키 생성(JSON) → 백엔드 서버에 안전하게 배치, `.env`에 `FIREBASE_CREDENTIALS_PATH` 로 경로 지정.
3. 프로젝트 설정 → Cloud Messaging → 웹 구성 → 웹 푸시 인증서(VAPID 키) 생성 → 프론트 `.env`에 `VITE_FIREBASE_VAPID_KEY` 등으로 지정.
4. 프론트 Firebase 웹 앱 등록 후 발급되는 `apiKey`/`projectId`/`messagingSenderId`/`appId` 를 프론트 `.env`에 지정.

## 에러 처리

- WS 연결 시 토큰이 없거나 유효하지 않으면 연결을 즉시 종료(정책 코드 4401 등)한다.
- 방 멤버가 아닌 사용자가 `send_message`/`active_room`/히스토리 조회를 시도하면 무시(WS) 또는 403(REST) 처리한다.
- FCM 발송 실패(개별 토큰 만료 등)는 그 토큰만 로깅 후 건너뛰고, 만료가 확인된 토큰(`UNREGISTERED` 에러)은 `DEVICE_TOKEN`에서 삭제한다.
- WS 연결이 끊기면 커넥션 매니저에서 해당 연결을 제거한다 (재연결은 프론트에서 지수 백오프로 재시도).

## 테스트 방침

- 백엔드: REST 엔드포인트(방 생성/중복 방지, 메시지 히스토리 페이지네이션, 알림 읽음 처리)는 일반 API 테스트로 검증. WS 흐름(온라인/다른방/오프라인 3단계 분기)은 `TestClient`의 WebSocket 테스트 유틸로 커버.
- 프론트: 브라우저에서 두 계정으로 로그인해 실시간 송수신, 알림벨 배지, FCM 권한 요청 플로우를 수동 확인 (FCM 실제 수신은 Firebase 프로젝트 설정 완료 후 확인 가능).
