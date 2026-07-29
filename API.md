# Ieum-Back API 명세서

이 문서는 `ieum-back` 프로젝트의 API를 설명합니다.

---

## 목차

- [Admin API (`/admin`)](#admin-api-admin)
- [AI API (`/ai`)](#ai-api-ai)
- [Auth API (`/auth`)](#auth-api-auth)
- [Dashboard API (`/dashboard`)](#dashboard-api-dashboard)
- [Department API (`/departments`)](#department-api-departments)
- [Knowledge API (`/knowledge`)](#knowledge-api-knowledge)
- [Petition API (`/petitions`)](#petition-api-petitions)
- [Project API (`/projects`)](#project-api-projects)
- [Task API (`/tasks`)](#task-api-tasks)
- [Upload API (`/upload`)](#upload-api-upload)
- [User API (`/users`)](#user-api-users)

---

## Admin API (`/admin`)

관리자 기능 관련 API입니다. (Prefix: `/admin`)

| Endpoint | Method | 설명 | 요청/응답 |
| --- | --- | --- | --- |
| `/users` | `GET` | **직원 목록 조회 (관리자용)**<br/>- 페이지네이션, 필터, 검색을 통해 직원을 조회합니다. | **Query:** `departmentCode`, `status`, `keyword`, `page`, `size`<br/>**Response:** `PaginatedUserManagementResponse` |
| `/users` | `POST` | **신규 직원 생성 (관리자용)**<br/>- 신규 직원을 시스템에 등록합니다. | **Request:** `UserCreationRequest`<br/>**Response:** `UserCreationResponse` |
| `/users/{userId}` | `PATCH` | **직원 정보 수정 (관리자용)**<br/>- 특정 직원의 정보를 수정합니다. | **Path:** `userId`<br/>**Request:** `UserUpdateRequest`<br/>**Response:** `UserUpdateResponse` |
| `/users/{userId}/reset-password` | `POST` | **직원 비밀번호 초기화 (관리자용)**<br/>- 특정 직원의 비밀번호를 기본값으로 초기화합니다. | **Path:** `userId`<br/>**Response:** `PasswordResetResponse` |
| `/stats` | `GET` | **관리자 대시보드 통계 조회**<br/>- 총 직원 수, 상태별 직원 수, 부서 수 등을 조회합니다. | **Response:** `AdminStatsResponse` |

## AI API (`/ai`)

AI 모델 중계 관련 API입니다. (Prefix: `/ai`)

| Endpoint | Method | 설명 | 요청/응답 |
| --- | --- | --- | --- |
| `/legal-chat` | `POST` | **AI 모델 중계 - 법률 챗봇**<br/>- AI 서버의 법률 챗봇 기능을 중계합니다. | **Request:** `LegalChatRequest`<br/>**Response:** `LegalChatResponse` |
| `/draft-answer` | `POST` | **AI 모델 중계 - 답변 초안 생성**<br/>- 민원 내용 기반으로 AI 답변 초안 생성을 중계합니다. | **Request:** `DraftAnswerRequest`<br/>**Response:** `DraftAnswerResponse` |
| `/similar-petitions` | `POST` | **AI 모델 중계 - 유사 민원 검색**<br/>- 민원 내용과 유사한 과거 민원 검색을 중계합니다. | **Request:** `SimilarPetitionsRequest`<br/>**Response:** `SimilarPetitionsResponse` |

## Auth API (`/auth`)

인증 및 권한 관련 API입니다. (Prefix: `/auth`)

| Endpoint | Method | 설명 | 요청/응답 |
| --- | --- | --- | --- |
| `/login` | `POST` | **사용자 로그인 및 토큰 발급**<br/>- 로그인 성공 시 Access/Refresh 토큰을 발급합니다. | **Request:** `UserLoginRequest`<br/>**Response:** `TokenResponse` |
| `/me` | `GET` | **현재 로그인된 사용자 정보 조회**<br/>- Access Token으로 현재 사용자 정보를 가져옵니다. | **Response:** `UserInfo` |
| `/logout` | `POST` | **사용자 로그아웃**<br/>- 서버에 저장된 Refresh Token을 무효화합니다. | **Request:** `RefreshTokenRequest`<br/>**Response:** 204 No Content |
| `/refresh` | `POST` | **Access Token 갱신**<br/>- Refresh Token으로 새로운 Access Token을 발급받습니다. | **Request:** `RefreshTokenRequest`<br/>**Response:** `AccessTokenResponse` |
| `/password` | `POST` | **비밀번호 변경**<br/>- 현재 로그인된 사용자의 비밀번호를 변경합니다. | **Request:** `PasswordChangeRequest`<br/>**Response:** 204 No Content |

## Dashboard API (`/dashboard`)

부서 관리 페이지의 대시보드 관련 API입니다. (Prefix: `/dashboard`)

| Endpoint | Method | 설명 | 요청/응답 |
| --- | --- | --- | --- |
| `/complaints/summary` | `GET` | **이번달 민원 건수**<br/>- 이번달의 민원 상태별 건수를 조회합니다. | **Query:** `department_code`<br/>**Response:** `ComplaintSummaryResponse` |
| `/complaints/due-soon` | `GET` | **처리기한 임박 민원 목록 (D-3 이내)**<br/>- 처리기한이 3일 이내인 민원 목록을 조회합니다. | **Query:** `department_code`<br/>**Response:** `List[DueSoonItem]` |
| `/tasks/summary` | `GET` | **Task 현황**<br/>- 부서의 Task 현황(총, 미배정 등)을 조회합니다. | **Query:** `department_code`<br/>**Response:** `TaskSummaryResponse` |

## Department API (`/departments`)

부서 및 조직도 관련 API입니다. (Prefix: `/departments`)

| Endpoint | Method | 설명 | 요청/응답 |
| --- | --- | --- | --- |
| `/` | `GET` | **부서 목록 조회**<br/>- 시스템의 모든 부서 목록을 조회합니다. | **Response:** `List[DepartmentResponse]` |
| `/{department_code}/members` | `GET` | **특정 부서의 조직원 목록 조회**<br/>- 조직도 표시에 사용됩니다. | **Path:** `department_code`<br/>**Response:** `List[MemberResponse]` |

## Home API (`/home`)

사용자 홈 대시보드 관련 API입니다. (Prefix: `/home`)

| Endpoint | Method | 설명 | 요청/응답 |
| --- | --- | --- | --- |
| `/` | `GET` | **사용자 홈 대시보드 데이터 조회**<br/>- 일반 사용자의 홈 화면에 필요한 데이터를 종합하여 반환합니다. | **Response:** `HomeDashboardResponse` |

## Knowledge API (`/knowledge`)

지식 베이스 관련 API입니다. (Prefix: `/knowledge`)

| Endpoint | Method | 설명 | 요청/응답 |
| --- | --- | --- | --- |
| `/` | `GET` | **지식베이스 목록 조회**<br/>- 페이지네이션, 필터, 검색을 지원합니다. | **Query:** `task_id`, `category_code`, `scope_code`, `department_code`, `keyword`, `page`, `size`<br/>**Response:** `KnowledgeListResponse` |
| `/` | `POST` | **지식 베이스 항목 생성**<br/>- `multipart/form-data` 형식으로 파일을 함께 업로드합니다. | **Request (Form):** `title`, `category_code`, `scope_code`, `summary`, `warning_note`, `task_id`, `files`<br/>**Response:** `KnowledgeCreateResponse` |
| `/{knowledge_id}` | `GET` | **지식 카드 상세 조회**<br/>- 특정 지식 카드의 상세 내용을 조회합니다. | **Path:** `knowledge_id`<br/>**Response:** `KnowledgeDetailResponse` |
| `/{knowledge_id}` | `PATCH` | **지식 베이스 항목 수정**<br/>- `multipart/form-data` 형식으로 정보 수정 및 파일 추가/삭제를 처리합니다. | **Path:** `knowledge_id`<br/>**Request (Form):** `title`, `category_code`, `scope_code`, `summary`, `warning_note`, `deleted_attachment_ids`, `files`<br/>**Response:** `KnowledgeUpdateResponse` |
| `/{knowledge_id}` | `DELETE` | **지식 베이스 항목 삭제**<br/>- 지식 카드를 소프트 삭제합니다. | **Path:** `knowledge_id`<br/>**Response:** 204 No Content |
| `/tags` | `GET` | **부서별 태그 목록 조회**<br/>- 특정 부서의 모든 태그를 조회합니다. | **Query:** `department_code`<br/>**Response:** `List[TagResponse]` |
| `/tags` | `POST` | **새 태그 생성**<br/>- 특정 부서에 새로운 태그를 추가합니다. | **Request:** `TagCreateRequest`<br/>**Response:** `TagResponse` |
| `/{knowledge_id}/logs` | `POST` | **노하우(로그) 생성**<br/>- 지식 카드에 새로운 노하우 항목을 추가합니다. | **Path:** `knowledge_id`<br/>**Request:** `LogCreateRequest`<br/>**Response:** `LogResponse` |
| `/logs/{log_id}` | `PATCH` | **노하우(로그) 수정**<br/>- 기존 노하우의 내용이나 태그를 수정합니다. | **Path:** `log_id`<br/>**Request:** `LogUpdateRequest`<br/>**Response:** `LogResponse` |
| `/logs/{log_id}` | `DELETE` | **노하우(로그) 삭제**<br/>- 노하우 항목을 소프트 삭제합니다. | **Path:** `log_id`<br/>**Response:** 204 No Content |

## Petition API (`/petitions`)

민원 처리 관련 API입니다. (Prefix: `/petitions`)

| Endpoint | Method | 설명 | 요청/응답 |
| --- | --- | --- | --- |
| `/external` | `POST` | **외부 시스템 민원 접수**<br/>- 외부 채널(국민신문고 등)에서 API 키 인증을 통해 민원을 접수합니다. | **Request:** `ExternalPetitionRequest`<br/>**Header:** `X-API-Key`<br/>**Response:** `ExternalPetitionResponse` |
| `/` | `GET` | **민원 목록 조회**<br/>- 페이지네이션, 필터(범위, 상태, 업무), 정렬, 검색을 지원합니다. | **Query:** `scope`, `status`, `page`, `size`, `sort`, `taskId`, `departmentCode`, `keyword`<br/>**Response:** `PaginatedPetitionResponse` |
| `/{complaintId}` | `GET` | **민원 상세 조회**<br/>- 특정 민원의 상세 정보를 조회합니다. | **Path:** `complaintId`<br/>**Response:** `PetitionDetailResponse` |
| `/{complaintId}/temp-save` | `PUT` | **민원 답변 임시저장 및 담당자 변경**<br/>- 답변을 임시저장하고 담당자를 변경할 수 있습니다. `multipart/form-data` 형식입니다. | **Path:** `complaintId`<br/>**Request (Form):** `manualAnswer`, `assigneeUserId`, `files`<br/>**Response:** `{"message": "저장 되었습니다."}` |
| `/{complaintId}/answer` | `POST` | **민원 답변 완료**<br/>- 답변을 최종 제출하고 민원 상태를 '완료'로 변경합니다. `multipart/form-data` 형식입니다. | **Path:** `complaintId`<br/>**Request (Form):** `manualAnswer`, `files`<br/>**Response:** `{"message": "답변이 완료되었습니다."}` |
| `/attachments/{attachmentId}` | `DELETE` | **첨부파일 삭제 (소프트 삭제)**<br/>- 민원에 첨부된 파일을 소프트 삭제합니다. | **Path:** `attachmentId`<br/>**Response:** `DeleteAttachmentResponse` |

## Project API (`/projects`)

사업/과제 관리 관련 API입니다. (Prefix: `/projects`)

| Endpoint | Method | 설명 | 요청/응답 |
| --- | --- | --- | --- |
| `/` | `GET` | **프로젝트 목록 조회**<br/>- 범위, 단계, 부서, 키워드로 프로젝트를 검색합니다. | **Query:** `scope`, `stage`, `page`, `size`, `keyword`, `department_code`<br/>**Response:** `ProjectListResponse` |
| `/` | `POST` | **새 프로젝트 생성**<br/>- 새로운 프로젝트를 생성하고 담당자를 지정합니다. | **Request:** `ProjectCreateRequest`<br/>**Response:** `ProjectCreateResponse` |
| `/{projectId}` | `GET` | **프로젝트 상세 조회**<br/>- 특정 프로젝트의 상세 정보를 조회합니다. | **Path:** `projectId`<br/>**Response:** `ProjectDetailResponse` |
| `/{projectId}` | `PATCH` | **프로젝트 저장**<br/>- 프로젝트의 정보를 수정하고 저장합니다. | **Path:** `projectId`<br/>**Request:** `ProjectUpdateRequest`<br/>**Response:** `ProjectDetailResponse` |
| `/{projectId}/approve` | `POST` | **기획서 승인완료**<br/>- 프로젝트 상태를 '승인완료'로 변경합니다. | **Path:** `projectId`<br/>**Response:** `{"message": "승인완료 처리되었습니다."}` |
| `/{projectId}/delete` | `DELETE` | **프로젝트 삭제**<br/>- '저장' 상태인 프로젝트를 삭제합니다. | **Path:** `projectId`<br/>**Response:** 200 OK |
| `/{projectId}/ai-draft` | `POST` | **AI 기획서 초안 생성**<br/>- AI를 이용해 사업 기획서의 초안을 생성합니다. | **Path:** `projectId`<br/>**Response:** `AiDraftResponse` |
| `/{projectId}/export` | `GET` | **기획서 내보내기**<br/>- 프로젝트 기획서를 지정된 형식(pdf, docx, hwpx)의 파일로 다운로드합니다. | **Path:** `projectId`<br/>**Query:** `format`<br/>**Response:** File Stream |

## Task API (`/tasks`)

담당 업무(Task) 관리 API입니다. (Prefix: `/tasks`)

| Endpoint | Method | 설명 | 요청/응답 |
| --- | --- | --- | --- |
| `/my-tasks` | `GET` | **내 담당 업무 목록 조회**<br/>- 현재 로그인한 사용자가 담당하는 모든 업무 목록을 조회합니다. | **Response:** `List[MyTaskResponse]` |
| `/` | `GET` | **Task 목록 조회**<br/>- 특정 부서의 모든 Task와 담당자 목록을 조회합니다. | **Query:** `department_code`<br/>**Response:** `List[TaskListItem]` |
| `/` | `POST` | **새 Task 생성**<br/>- 특정 부서에 새로운 Task를 생성합니다. | **Query:** `department_code`<br/>**Request:** `TaskCreateRequest`<br/>**Response:** `TaskCreateResponse` |
| `/{taskId}` | `DELETE` | **Task 삭제**<br/>- Task와 관련된 모든 담당자 지정을 해제하고 Task를 삭제합니다. | **Path:** `taskId`<br/>**Response:** 200 OK |
| `/{taskId}/assignees` | `POST` | **담당자 지정**<br/>- Task에 담당자를 지정합니다. | **Path:** `taskId`<br/>**Request:** `AssigneeRequest`<br/>**Response:** 200 OK |
| `/{taskId}/assignees/{userId}` | `DELETE` | **담당자 해제**<br/>- Task에 지정된 담당자를 해제합니다. | **Path:** `taskId`, `userId`<br/>**Response:** 200 OK |

## Upload API (`/upload`)

파일 업로드 공통 API입니다. (Prefix: `/upload`)

| Endpoint | Method | 설명 | 요청/응답 |
| --- | --- | --- | --- |
| `/` | `POST` | **파일 업로드**<br/>- `multipart/form-data`로 파일을 S3에 업로드하고 URL을 반환합니다. | **Request:** `File`<br/>**Response:** `UploadResponse` |

## User API (`/users`)

사용자 검색 관련 API입니다. (Prefix: `/users`)

| Endpoint | Method | 설명 | 요청/응답 |
| --- | --- | --- | --- |
| `/search` | `GET` | **사용자 목록 조회 및 검색**<br/>- 범위(같은 과, 전체), 부서, 키워드로 사용자를 검색합니다. | **Query:** `scope`, `departmentCode`, `keyword`<br/>**Response:** `list[UserSearchResult]` |
