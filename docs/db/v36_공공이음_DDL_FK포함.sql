-- ============================================================
-- 공공이음(이음AI) DB DDL - FK 제약조건 포함 버전
-- DBMS: MySQL 8.0
--
-- 이 파일은 실제 운영 공유 DB(192.168.4.122:3306/ggieum)를 2026-07-29 기준으로
-- SHOW CREATE TABLE + 실데이터로 그대로 다시 만들었다.
--
-- v34: TASK 테이블에 소프트 삭제 컬럼 추가 (2026-07-28)
--      is_deleted(TINYINT, 기본값 0) / deleted_at(DATETIME, NULL 가능) 추가.
--      delete_task가 하드 삭제 대신 is_deleted=1 UPDATE로 처리하도록 바뀌어서,
--      TASK_ASSIGNEE 배정 이력과 PETITION.task_id 참조(민원 이력)가 Task 삭제
--      이후에도 그대로 보존되도록 함.
--      참고: 기존에 생성된 PETITION 데이터 중 task_id가 가리키는 TASK 행이
--      실제로는 존재하지 않는 고아 레코드가 2건 있음(petition_id=55, 57,
--      task_id=4) - 과거 하드 삭제 이전에 생긴 것으로 보이며, 이번 변경과
--      무관하게 데이터는 그대로 둔다. 아래 fk_petition_task 제약을 실제 운영
--      DB에 적용하려면 이 2건부터 정리해야 ALTER TABLE이 성공한다.
--
-- v35: PETITION_STATUS 코드 4개로 변경 (2026-07-29)
--      wait(01) 대기중 / check(02) 확인중 / progress(03) 처리중 / done(04) 완료
--      주무관 상세페이지 진입 시 01→02 자동 전환 로직은 백엔드에서 처리
--
-- v36: 실시간 채팅 + FCM 푸시 알림 기능 추가 (2026-07-29)
--      신규 테이블 5개 추가: CHAT_ROOM, CHAT_ROOM_MEMBER, CHAT_MESSAGE,
--      NOTIFICATION, DEVICE_TOKEN (전부 소문자로 실제 생성됨 - 이 DB는
--      lower_case_table_names=1이라 테이블명이 대소문자 구분 없이 소문자로
--      저장된다. USER, PETITION 등 기존 테이블도 전부 동일).
--      이 5개 테이블은 애플리케이션 코드(SQLAlchemy Base.metadata.create_all)로
--      직접 생성했고, 아래 CREATE TABLE 문은 그 결과를 SHOW CREATE TABLE로
--      그대로 뽑은 것이라 실제 운영 DB와 100% 일치한다 - 나머지 기존 19개
--      테이블과 달리 FK 제약조건이 "있어야 할 모습"이 아니라 실제로 걸려 있다.
--      user_id를 참조하는 컬럼(created_by, sender_id, user_id)은 USER.user_id가
--      실제로는 int이므로(SQLAlchemy 모델 파일에는 String(50)으로 선언돼 있지만
--      운영 DB 컬럼은 int) 전부 int로 맞췄다 - 처음에 String(50)으로 만들었다가
--      "Referencing column ... incompatible" 에러(MySQL 8 타입 호환성 검사)로
--      막혀서 발견/수정했다.
--      또한 발견된 것: PETITION_ASSIGNEE_HISTORY에 change_type 컬럼과
--      PETITION_ASSIGNEE_CHANGE_TYPE 공통코드 그룹이 v35 스냅샷 이후 추가되어
--      있었다(01=TRANSFER 인수인계, 02=TEMP_ASSIGN 임시배정, 03=DEPT_TRANSFER
--      부서이동 자동이관) - 이번 채팅 작업과는 무관하지만 라이브 DB에서
--      SHOW CREATE TABLE로 다시 뽑으면서 같이 반영됨.
--
-- 실제 운영 DB에는 지금 common_code -> common_code_group 사이의 FK
-- (fk_commoncode_group), 그리고 이번에 새로 생성한 채팅/알림 테이블 5개의 FK만
-- 실제로 걸려 있고, 나머지 기존 관계는 전부 일반 인덱스뿐이다. 이 파일의 그
-- 나머지 관계에는 FK 제약을 추가한 "있어야 할 모습" 버전이다.
-- ============================================================

-- 테이블 생성 순서와 무관하게(순환 참조 포함) FK를 인라인으로 걸 수 있도록
-- 생성 중에는 FK 검사를 잠시 끈다.
SET FOREIGN_KEY_CHECKS = 0;

CREATE DATABASE IF NOT EXISTS ggieum DEFAULT CHARACTER SET utf8mb4;
USE ggieum;

-- ------------------------------------------------------------
-- 0. COMMON_CODE_GROUP - 공통 코드 그룹 마스터
-- ------------------------------------------------------------
DROP TABLE IF EXISTS common_code_group;
CREATE TABLE common_code_group (
  group_code  varchar(30)  NOT NULL COMMENT '그룹 코드 (예: POSITION, USER_STATUS)',
  group_name  varchar(100) NOT NULL COMMENT '그룹명 (예: 직급, 계정상태)',
  description varchar(200) DEFAULT NULL COMMENT '그룹 설명',
  use_yn      char(1)      NOT NULL DEFAULT 'Y' COMMENT 'Y=사용, N=미사용',
  sort_order  int          NOT NULL DEFAULT '0',
  PRIMARY KEY (group_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO common_code_group (group_code, group_name, description, sort_order) VALUES
('POSITION',                     '직급',              '부서 내 직급 구분 (부장/팀장/주무관)', 1),
('SYSTEM_ROLE',                  '시스템 권한',        '계정의 시스템 접근 권한 구분', 2),
('USER_STATUS',                  '계정 상태',          '재직/휴직/퇴직 등 계정의 재직 상태', 3),
('CHANGE_TYPE',                  '인사이동 유형',      '전입/전출/신규충원 등 인사발령 구분', 4),
('ASSIGNEE_ACTION',              '담당자 배정 이력',   'Task 담당자 배정/해제 이력 구분', 5),
('PETITION_STATUS',              '민원 처리 상태',     '민원 작성/처리 진행 단계', 6),
('PROJECT_STAGE',                '사업 진행 단계',     '사업계획서 기획~승인 진행 단계', 7),
('PROJECT_ROLE',                 '사업 참여 역할',     '사업계획서에 대한 주관/협력 역할 구분', 8),
('LEGAL_SOURCE_TYPE',            '법령 등록 방식',     '법령 문서가 시스템에 등록된 경로(수동/API)', 9),
('KNOWLEDGE_CATEGORY',           '지식카드 분류',      '업무 노하우(지식카드)의 주제 분류', 10),
('KNOWLEDGE_SCOPE',              '지식카드 공개범위',  '지식카드를 열람할 수 있는 범위(부서 한정/전체)', 11),
('LOG_SOURCE',                   '지식카드 생성 경로', '지식카드(노하우)가 담당자 직접 작성인지, 민원/사업 완료 시 자동 연결된 것인지 구분', 12),
('PETITION_ASSIGNEE_CHANGE_TYPE','민원 담당자 변경 유형','민원 담당자 배정 방식 구분 (인수인계/임시 배정/부서이동 자동 이관)', 13);

-- ------------------------------------------------------------
-- 1. COMMON_CODE - 그룹별 실제 코드값
-- ------------------------------------------------------------
DROP TABLE IF EXISTS common_code;
CREATE TABLE common_code (
  group_code  varchar(30)  NOT NULL COMMENT 'common_code_group.group_code 참조',
  code        varchar(10)  NOT NULL COMMENT '그룹 내 코드값 (01, 02, 03 ...)',
  name        varchar(100) NOT NULL COMMENT '실제 표시값 (예: 팀장, 전입, wait)',
  description varchar(200) DEFAULT NULL COMMENT '코드 설명',
  use_yn      char(1)      NOT NULL DEFAULT 'Y' COMMENT 'Y=사용, N=미사용',
  sort_order  int          NOT NULL DEFAULT '0',
  PRIMARY KEY (group_code, code),
  CONSTRAINT fk_commoncode_group FOREIGN KEY (group_code) REFERENCES common_code_group (group_code) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO common_code (group_code, code, name, description, use_yn, sort_order) VALUES
('ASSIGNEE_ACTION', '01', '배정', 'Task 담당자로 배정됨', 'Y', 1),
('ASSIGNEE_ACTION', '02', '해제', 'Task 담당자에서 해제됨', 'Y', 2),
('CHANGE_TYPE', '01', '전입', '다른 부서에서 해당 부서로 이동', 'Y', 1),
('CHANGE_TYPE', '02', '전출', '해당 부서에서 다른 부서로 이동', 'Y', 2),
('CHANGE_TYPE', '03', '신규충원', '신규 입사자 배치', 'Y', 3),
('KNOWLEDGE_CATEGORY', '01', '민원처리', '민원 처리 관련 노하우', 'Y', 1),
('KNOWLEDGE_CATEGORY', '02', '사업추진', '사업/프로젝트 추진 관련 노하우', 'Y', 2),
('KNOWLEDGE_CATEGORY', '03', '예산', '예산 편성 및 집행 관련 노하우', 'Y', 3),
('KNOWLEDGE_CATEGORY', '04', '인허가', '인허가 처리 관련 노하우', 'Y', 4),
('KNOWLEDGE_CATEGORY', '05', '실패사례', '실수 및 개선 방법 기록', 'Y', 5),
('KNOWLEDGE_CATEGORY', '99', '기타', '기타 업무 노하우', 'Y', 99),
('KNOWLEDGE_SCOPE', '01', 'dept', '내 부서 인원만 열람 가능', 'Y', 1),
('KNOWLEDGE_SCOPE', '02', 'all', '전체 부서 열람 가능', 'Y', 2),
('LEGAL_SOURCE_TYPE', '01', '수동업로드', '관리자가 직접 PDF 업로드', 'Y', 1),
('LEGAL_SOURCE_TYPE', '02', 'API연동', '국가법령정보센터 API로 자동 수집(PDF/XML)', 'Y', 2),
('LOG_SOURCE', '01', 'direct', '담당자가 지식베이스에서 직접 작성', 'Y', 1),
('LOG_SOURCE', '02', 'petition', '민원 완료 시 특이사항 입력으로 자동 연결', 'Y', 2),
('LOG_SOURCE', '03', 'project', '사업 완료 시 특이사항 입력으로 자동 연결', 'Y', 3),
('PETITION_ASSIGNEE_CHANGE_TYPE', '01', 'TRANSFER', '인수인계 - 정식 담당자 변경', 'Y', 1),
('PETITION_ASSIGNEE_CHANGE_TYPE', '02', 'TEMP_ASSIGN', '임시 배정 - 부재 등 일시적 대리 처리', 'Y', 2),
('PETITION_ASSIGNEE_CHANGE_TYPE', '03', 'DEPT_TRANSFER', '부서이동으로 인한 자동 이관', 'Y', 3),
('PETITION_STATUS', '01', 'wait', '민원 접수 후 미열람 상태', 'Y', 1),
('PETITION_STATUS', '02', 'check', '상세페이지 진입 시 전환', 'Y', 2),
('PETITION_STATUS', '03', 'progress', '[저장] 버튼 클릭 시 전환', 'Y', 3),
('PETITION_STATUS', '04', 'done', '[완료] 버튼 클릭 시 전환', 'Y', 4),
('POSITION', '01', '부장', '부서장 - Task 배정/담당자 변경 권한', 'Y', 1),
('POSITION', '02', '팀장', '팀 리더', 'Y', 2),
('POSITION', '03', '주무관', '실무 담당자', 'Y', 3),
('PROJECT_ROLE', '01', '주관', '기획서 작성 권한 보유 (프로젝트당 1명)', 'Y', 1),
('PROJECT_ROLE', '02', '협력', '참여만, 작성 권한 없음', 'Y', 2),
('PROJECT_STAGE', '01', '기획중', '기획서 작성/저장 단계', 'Y', 1),
('PROJECT_STAGE', '02', '승인완료', '기획 승인 완료', 'Y', 2),
('SYSTEM_ROLE', '01', '일반사용자', '일반 직원 계정', 'Y', 1),
('SYSTEM_ROLE', '02', '시스템관리자', '관리자페이지 접근 및 전체 조직 인사이동 처리 권한', 'Y', 2),
('USER_STATUS', '01', '재직', '정상 재직 중인 계정', 'Y', 1),
('USER_STATUS', '02', '휴직', '휴직 중인 계정', 'Y', 2),
('USER_STATUS', '03', '퇴직', '퇴직 처리된 계정', 'Y', 3);

-- ------------------------------------------------------------
-- 2. DEPARTMENT - 부서
-- ------------------------------------------------------------
DROP TABLE IF EXISTS department;
CREATE TABLE department (
  department_code        varchar(10)  NOT NULL COMMENT '부서 코드 (01, 02 ...)',
  name                    varchar(100) NOT NULL COMMENT '부서명',
  parent_department_code varchar(10)  DEFAULT NULL COMMENT '상위 부서 코드 (조직도 계층)',
  head_user_id            int          DEFAULT NULL COMMENT '부서장 사번 - Task 배정/담당자 변경 권한자',
  PRIMARY KEY (department_code),
  KEY idx_department_parent (parent_department_code),
  KEY idx_department_head_user (head_user_id),
  CONSTRAINT fk_department_parent FOREIGN KEY (parent_department_code) REFERENCES department (department_code) ON DELETE SET NULL,
  CONSTRAINT fk_department_head FOREIGN KEY (head_user_id) REFERENCES `user` (user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO department (department_code, name, parent_department_code, head_user_id) VALUES
('01', '교통부', NULL, NULL),
('02', '주택·건축부', NULL, NULL),
('03', '환경부', NULL, NULL),
('04', '복지부', NULL, NULL),
('05', '안전부', NULL, NULL),
('06', '경제·산업부', NULL, NULL),
('07', '문화·체육·관광부', NULL, NULL),
('08', '행정·일반부', NULL, NULL),
('09', '관리자', NULL, NULL);

-- ------------------------------------------------------------
-- 3. USER - 사용자
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  user_id              int          NOT NULL COMMENT '사번 - 로그인 아이디로 사용 (예: 20260001)',
  name                 varchar(50)  NOT NULL COMMENT '이름',
  password             varchar(255) NOT NULL COMMENT '비밀번호 (bcrypt 해시)',
  position_code        varchar(10)  DEFAULT NULL COMMENT 'POSITION: 01=부장, 02=팀장, 03=주무관',
  department_code      varchar(10)  DEFAULT NULL COMMENT '소속 부서',
  system_role_code     varchar(10)  DEFAULT NULL COMMENT 'SYSTEM_ROLE: 01=일반사용자, 02=시스템관리자',
  status_code          varchar(10)  DEFAULT NULL COMMENT 'USER_STATUS: 01=재직, 02=휴직, 03=퇴직',
  predecessor_user_id  int          DEFAULT NULL COMMENT '전임자 사번 (NULL=전임자 없음)',
  refresh_token        varchar(512) DEFAULT NULL COMMENT '로그아웃 시 NULL로 초기화',
  token_expires_at     datetime     DEFAULT NULL COMMENT 'refresh_token 만료 시각',
  last_login_at        datetime     DEFAULT NULL COMMENT '최근 로그인 시각',
  must_change_password tinyint(1)   NOT NULL DEFAULT '0' COMMENT '1=임시 비밀번호 상태 → 로그인 후 변경 안내',
  created_at           datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at           datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  KEY idx_user_department (department_code),
  KEY idx_user_predecessor (predecessor_user_id),
  CONSTRAINT fk_user_department FOREIGN KEY (department_code) REFERENCES department (department_code) ON DELETE SET NULL,
  CONSTRAINT fk_user_predecessor FOREIGN KEY (predecessor_user_id) REFERENCES `user` (user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 4. TASK - 업무 (v34: 소프트 삭제 컬럼 추가)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS task;
CREATE TABLE task (
  task_id         int          NOT NULL AUTO_INCREMENT,
  name            varchar(200) NOT NULL COMMENT '업무명',
  department_code varchar(10)  DEFAULT NULL COMMENT '소속 부서',
  is_deleted      tinyint(1)   NOT NULL DEFAULT '0',
  deleted_at      datetime     DEFAULT NULL,
  PRIMARY KEY (task_id),
  KEY idx_task_department (department_code),
  CONSTRAINT fk_task_department FOREIGN KEY (department_code) REFERENCES department (department_code) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 5. TASK_ASSIGNEE - 업무 담당자
-- ------------------------------------------------------------
DROP TABLE IF EXISTS task_assignee;
CREATE TABLE task_assignee (
  task_assignee_id int      NOT NULL AUTO_INCREMENT,
  task_id          int      NOT NULL,
  user_id          int      NOT NULL COMMENT '담당자 사번 (복수 가능)',
  assigned_at      datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (task_assignee_id),
  UNIQUE KEY uq_task_assignee (task_id, user_id),
  KEY idx_task_assignee_user (user_id),
  CONSTRAINT fk_ta_task FOREIGN KEY (task_id) REFERENCES task (task_id) ON DELETE CASCADE,
  CONSTRAINT fk_ta_user FOREIGN KEY (user_id) REFERENCES `user` (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 6. PETITION - 민원
-- ------------------------------------------------------------
DROP TABLE IF EXISTS petition;
CREATE TABLE petition (
  petition_id       int          NOT NULL AUTO_INCREMENT,
  title             varchar(255) NOT NULL COMMENT '민원 제목',
  content           text         NOT NULL COMMENT '민원 내용',
  received_at       datetime     DEFAULT NULL COMMENT '민원 접수일시 (외부 API 값)',
  status_code       varchar(10)  DEFAULT NULL COMMENT 'PETITION_STATUS: wait / check / progress / done',
  task_id           int          DEFAULT NULL COMMENT '연결된 업무',
  department_code   varchar(10)  DEFAULT NULL COMMENT '담당 부서',
  assignee_user_id  int          DEFAULT NULL COMMENT '현재 담당자 사번, 부서장이 변경 가능',
  manual_answer     text         COMMENT '담당자가 작성한 답변 내용 ([저장] 시 누적)',
  due_date          date         DEFAULT NULL COMMENT '처리기한',
  answered_at       datetime     DEFAULT NULL COMMENT '[작성 완료] 버튼 클릭 시각',
  created_at        datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (petition_id),
  KEY idx_petition_task (task_id),
  KEY idx_petition_department (department_code),
  KEY idx_petition_assignee (assignee_user_id),
  -- 주의: petition_id=55,57(task_id=4)이 가리키는 TASK 행이 실제로 없는 고아
  -- 레코드다 (v34 노트 참고). 이 FK를 실제 운영 DB에 적용하려면 이 2건부터
  -- 정리해야 ALTER TABLE이 성공한다.
  CONSTRAINT fk_petition_task FOREIGN KEY (task_id) REFERENCES task (task_id) ON DELETE SET NULL,
  CONSTRAINT fk_petition_department FOREIGN KEY (department_code) REFERENCES department (department_code) ON DELETE SET NULL,
  CONSTRAINT fk_petition_assignee FOREIGN KEY (assignee_user_id) REFERENCES `user` (user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 7. PETITION_ATTACHMENT - 민원 첨부파일
-- ------------------------------------------------------------
DROP TABLE IF EXISTS petition_attachment;
CREATE TABLE petition_attachment (
  attachment_id   int          NOT NULL AUTO_INCREMENT,
  petition_id     int          NOT NULL COMMENT '연결된 민원',
  file_url        varchar(500) NOT NULL COMMENT '파일 저장 경로',
  file_name       varchar(255) NOT NULL COMMENT '원본 파일명',
  is_staff_upload tinyint(1)   NOT NULL DEFAULT '0' COMMENT '1=담당자 업로드, 0=민원인 업로드',
  is_deleted      tinyint(1)   NOT NULL DEFAULT '0' COMMENT '1=삭제됨, 0=정상',
  deleted_at      datetime     DEFAULT NULL COMMENT '삭제 처리 시각',
  PRIMARY KEY (attachment_id),
  KEY idx_attachment_petition (petition_id),
  CONSTRAINT fk_pa_petition FOREIGN KEY (petition_id) REFERENCES petition (petition_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 8. PETITION_ASSIGNEE_HISTORY - 민원 담당자 변경 이력
--    (v36 스냅샷에서 새로 발견: change_type 컬럼 - v35 이후 추가된 것으로 보임)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS petition_assignee_history;
CREATE TABLE petition_assignee_history (
  history_id   int      NOT NULL AUTO_INCREMENT,
  petition_id  int      NOT NULL COMMENT '연결된 민원',
  from_user_id int      DEFAULT NULL COMMENT '이전 담당자 사번, NULL=최초 배정',
  to_user_id   int      NOT NULL COMMENT '새 담당자 사번',
  change_type  char(2)  NOT NULL DEFAULT '01' COMMENT '변경 유형: 01=TRANSFER(인수인계), 02=TEMP_ASSIGN(임시 배정)',
  changed_at   datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '변경 시각',
  PRIMARY KEY (history_id),
  KEY idx_pah_petition (petition_id),
  KEY idx_pah_from_user (from_user_id),
  KEY idx_pah_to_user (to_user_id),
  CONSTRAINT fk_pah_petition FOREIGN KEY (petition_id) REFERENCES petition (petition_id) ON DELETE CASCADE,
  CONSTRAINT fk_pah_from_user FOREIGN KEY (from_user_id) REFERENCES `user` (user_id) ON DELETE SET NULL,
  CONSTRAINT fk_pah_to_user FOREIGN KEY (to_user_id) REFERENCES `user` (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 9. PROJECT - 사업/프로젝트
-- ------------------------------------------------------------
DROP TABLE IF EXISTS project;
CREATE TABLE project (
  project_id           int          NOT NULL AUTO_INCREMENT,
  name                 varchar(200) NOT NULL COMMENT '사업명',
  stage_code           varchar(10)  DEFAULT NULL COMMENT 'PROJECT_STAGE: 01=기획중, 02=승인완료',
  task_id              int          DEFAULT NULL COMMENT '연결된 업무',
  department_code      varchar(10)  DEFAULT NULL COMMENT '담당 부서 (유사사례·AI초안 학습·접근 범위)',
  deadline             date         DEFAULT NULL COMMENT '사업 마감기한',
  start_date           date         DEFAULT NULL COMMENT '사업 시작일',
  business_content     text         COMMENT '사업 내용',
  overview             text         COMMENT '개요',
  report_content       text         COMMENT '기획서 본문 - 주관자만 작성 가능, 최종본만 유지',
  approved_at          datetime     DEFAULT NULL COMMENT 'stage_code=02(승인완료) 전환 시각',
  created_at           datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at           datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  sec_overview         text,
  sec_background       text,
  sec_goals            text,
  sec_detailed_plan    text,
  sec_schedule         text,
  sec_execution_system text,
  sec_budget           text,
  sec_expected_effect  text,
  sec_post_management  text,
  cover_title          varchar(200) DEFAULT NULL COMMENT '표지 제목 (사용자 수정 가능)',
  PRIMARY KEY (project_id),
  KEY idx_project_task (task_id),
  KEY idx_project_department (department_code),
  CONSTRAINT fk_project_task FOREIGN KEY (task_id) REFERENCES task (task_id) ON DELETE SET NULL,
  CONSTRAINT fk_project_department FOREIGN KEY (department_code) REFERENCES department (department_code) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 10. PROJECT_MEMBER - 프로젝트 참여자
-- ------------------------------------------------------------
DROP TABLE IF EXISTS project_member;
CREATE TABLE project_member (
  project_member_id int         NOT NULL AUTO_INCREMENT,
  project_id        int         NOT NULL COMMENT '연결된 프로젝트',
  user_id           int         NOT NULL COMMENT '참여자 사번',
  role_code         varchar(10) DEFAULT NULL COMMENT 'PROJECT_ROLE: 01=주관, 02=협력',
  invited_by        int         DEFAULT NULL COMMENT '초대한 사용자 사번',
  joined_at         datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (project_member_id),
  KEY idx_pm_project (project_id),
  KEY idx_pm_user (user_id),
  KEY idx_pm_invited_by (invited_by),
  CONSTRAINT fk_pm_project FOREIGN KEY (project_id) REFERENCES project (project_id) ON DELETE CASCADE,
  CONSTRAINT fk_pm_user FOREIGN KEY (user_id) REFERENCES `user` (user_id) ON DELETE CASCADE,
  CONSTRAINT fk_pm_invited_by FOREIGN KEY (invited_by) REFERENCES `user` (user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 11. LEGAL_DOCUMENT - 법령 문서
-- ------------------------------------------------------------
DROP TABLE IF EXISTS legal_document;
CREATE TABLE legal_document (
  legal_document_id int          NOT NULL AUTO_INCREMENT,
  title             varchar(200) NOT NULL COMMENT '법령명 (예: 지방세법 시행령)',
  file_url          varchar(500) NOT NULL COMMENT '법령 원문 파일 경로 (PDF 또는 XML)',
  source_type       varchar(10)  DEFAULT NULL COMMENT 'LEGAL_SOURCE_TYPE: 01=수동업로드, 02=API연동',
  law_api_id        varchar(50)  DEFAULT NULL COMMENT '국가법령정보센터 API 법령 고유ID - API연동 건만 존재, 개정 재조회용',
  effective_date    date         DEFAULT NULL COMMENT '시행일 (선택)',
  uploaded_by       int          DEFAULT NULL COMMENT '업로드한 관리자 사번 - API연동 건은 NULL(시스템 자동 수집)',
  uploaded_at       datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (legal_document_id),
  KEY idx_legal_document_uploaded_by (uploaded_by),
  CONSTRAINT fk_ld_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES `user` (user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 12. PERSONNEL_CHANGE - 인사이동 이력
-- ------------------------------------------------------------
DROP TABLE IF EXISTS personnel_change;
CREATE TABLE personnel_change (
  personnel_change_id  int         NOT NULL AUTO_INCREMENT,
  user_id              int         NOT NULL COMMENT '이동/충원 대상자 사번',
  change_type_code     varchar(10) DEFAULT NULL COMMENT 'CHANGE_TYPE: 01=전입, 02=전출, 03=신규충원',
  from_department_code varchar(10) DEFAULT NULL COMMENT '이동 전 부서',
  to_department_code   varchar(10) DEFAULT NULL COMMENT '이동 후 부서',
  processed_by         int         DEFAULT NULL COMMENT '처리한 시스템관리자 사번',
  processed_at         datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (personnel_change_id),
  KEY idx_pc_user (user_id),
  KEY idx_pc_from_department (from_department_code),
  KEY idx_pc_to_department (to_department_code),
  KEY idx_pc_processed_by (processed_by),
  CONSTRAINT fk_pc_user FOREIGN KEY (user_id) REFERENCES `user` (user_id) ON DELETE CASCADE,
  CONSTRAINT fk_pc_from_dept FOREIGN KEY (from_department_code) REFERENCES department (department_code) ON DELETE SET NULL,
  CONSTRAINT fk_pc_to_dept FOREIGN KEY (to_department_code) REFERENCES department (department_code) ON DELETE SET NULL,
  CONSTRAINT fk_pc_processed_by FOREIGN KEY (processed_by) REFERENCES `user` (user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 13. TASK_REASSIGNMENT - 인사이동에 따른 Task 재배정 이력
-- ------------------------------------------------------------
DROP TABLE IF EXISTS task_reassignment;
CREATE TABLE task_reassignment (
  reassignment_id     int         NOT NULL AUTO_INCREMENT,
  personnel_change_id int         DEFAULT NULL COMMENT '연결된 인사이동 (NULL 가능)',
  task_id             int         NOT NULL COMMENT '재배정된 Task',
  user_id             int         NOT NULL COMMENT '배정/해제 대상자 사번',
  action_code         varchar(10) DEFAULT NULL COMMENT 'ASSIGNEE_ACTION: 01=배정, 02=해제',
  reassigned_at       datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (reassignment_id),
  KEY idx_tr_personnel_change (personnel_change_id),
  KEY idx_tr_task (task_id),
  KEY idx_tr_user (user_id),
  CONSTRAINT fk_tr_pc FOREIGN KEY (personnel_change_id) REFERENCES personnel_change (personnel_change_id) ON DELETE SET NULL,
  CONSTRAINT fk_tr_task FOREIGN KEY (task_id) REFERENCES task (task_id) ON DELETE CASCADE,
  CONSTRAINT fk_tr_user FOREIGN KEY (user_id) REFERENCES `user` (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 지식베이스 테이블
-- ============================================================

-- ------------------------------------------------------------
-- 14. KNOWLEDGE - 지식 카드
-- ------------------------------------------------------------
DROP TABLE IF EXISTS knowledge;
CREATE TABLE knowledge (
  knowledge_id    int          NOT NULL AUTO_INCREMENT,
  task_id         int          DEFAULT NULL COMMENT '연결된 Task (NULL=보관함 상태, Task 삭제 시 NULL로 변경)',
  department_code varchar(10)  NOT NULL COMMENT '작성 당시 소속 부서 - Task 삭제 후에도 부서 귀속 유지',
  title           varchar(200) NOT NULL COMMENT '지식 카드 제목 (담당자가 직접 작성 또는 Task 생성 시 자동 부여)',
  category_code   varchar(10)  DEFAULT NULL COMMENT 'KNOWLEDGE_CATEGORY: 01=민원처리, 02=사업추진, 03=예산, 04=인허가, 05=실패사례, 99=기타',
  summary         text         COMMENT '핵심 요약 - 신규 담당자가 바로 쓸 수 있는 실무 정보',
  warning_note    text         COMMENT '주의사항 - 카드 상세 빨간 뱃지 표시, 반드시 숙지해야 할 예외/금지 사항',
  scope_code      varchar(10)  NOT NULL DEFAULT '01' COMMENT 'KNOWLEDGE_SCOPE: 01=dept(내 부서만), 02=all(전체 부서) — 기본값: 내 부서',
  created_by      int          NOT NULL COMMENT '최초 작성자 사번 (Task 생성 시 부장 사번 자동 입력)',
  updated_by      int          DEFAULT NULL COMMENT '최종 수정자 사번',
  created_at      datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  is_deleted      tinyint(1)   NOT NULL DEFAULT '0',
  deleted_at      datetime     DEFAULT NULL,
  PRIMARY KEY (knowledge_id),
  KEY idx_k_task (task_id),
  KEY idx_k_department (department_code),
  KEY idx_k_created_by (created_by),
  CONSTRAINT fk_k_task FOREIGN KEY (task_id) REFERENCES task (task_id) ON DELETE SET NULL,
  CONSTRAINT fk_k_department FOREIGN KEY (department_code) REFERENCES department (department_code) ON DELETE RESTRICT,
  CONSTRAINT fk_k_created_by FOREIGN KEY (created_by) REFERENCES `user` (user_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 15. KNOWLEDGE_TAG - 태그 목록
-- ------------------------------------------------------------
DROP TABLE IF EXISTS knowledge_tag;
CREATE TABLE knowledge_tag (
  tag_id          int         NOT NULL AUTO_INCREMENT,
  department_code varchar(10) NOT NULL COMMENT '태그 소속 부서 - 부서별로 태그 독립 관리',
  name            varchar(50) NOT NULL COMMENT '태그명',
  created_by      int         NOT NULL COMMENT '생성자 사번',
  created_at      datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (tag_id),
  UNIQUE KEY uq_tag_dept_name (department_code, name),
  KEY idx_tag_department (department_code),
  KEY idx_tag_created_by (created_by),
  CONSTRAINT fk_kt_department FOREIGN KEY (department_code) REFERENCES department (department_code) ON DELETE CASCADE,
  CONSTRAINT fk_kt_created_by FOREIGN KEY (created_by) REFERENCES `user` (user_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 16. KNOWLEDGE_LOG - 노하우 (지식 카드 본문 이력)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS knowledge_log;
CREATE TABLE knowledge_log (
  log_id       int        NOT NULL AUTO_INCREMENT,
  knowledge_id int        NOT NULL COMMENT '연결된 지식 카드',
  user_id      int        NOT NULL COMMENT '최초 작성자 사번',
  content      text       NOT NULL COMMENT '노하우 내용 (최신 내용만 유지)',
  updated_by   int        DEFAULT NULL COMMENT '최종 수정자 사번 (최초 작성 시 NULL)',
  is_deleted   tinyint(1) NOT NULL DEFAULT '0' COMMENT '1=삭제됨, 0=정상',
  deleted_at   datetime   DEFAULT NULL COMMENT '삭제 처리 시각',
  created_at   datetime   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   datetime   NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (log_id),
  KEY idx_kl_card (knowledge_id),
  KEY idx_kl_user (user_id),
  KEY idx_kl_updated_by (updated_by),
  CONSTRAINT fk_kl_knowledge FOREIGN KEY (knowledge_id) REFERENCES knowledge (knowledge_id) ON DELETE CASCADE,
  CONSTRAINT fk_kl_user FOREIGN KEY (user_id) REFERENCES `user` (user_id) ON DELETE RESTRICT,
  CONSTRAINT fk_kl_updated_by FOREIGN KEY (updated_by) REFERENCES `user` (user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 17. KNOWLEDGE_LOG_TAG - 노하우 - 태그 N:M
-- ------------------------------------------------------------
DROP TABLE IF EXISTS knowledge_log_tag;
CREATE TABLE knowledge_log_tag (
  log_tag_id int NOT NULL AUTO_INCREMENT,
  log_id     int NOT NULL COMMENT '연결된 노하우',
  tag_id     int NOT NULL COMMENT '연결된 태그',
  PRIMARY KEY (log_tag_id),
  UNIQUE KEY uq_log_tag (log_id, tag_id),
  KEY idx_klt_log (log_id),
  KEY idx_klt_tag (tag_id),
  CONSTRAINT fk_klt_log FOREIGN KEY (log_id) REFERENCES knowledge_log (log_id) ON DELETE CASCADE,
  CONSTRAINT fk_klt_tag FOREIGN KEY (tag_id) REFERENCES knowledge_tag (tag_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 18. KNOWLEDGE_ATTACHMENT - 지식 카드 첨부파일
-- ------------------------------------------------------------
DROP TABLE IF EXISTS knowledge_attachment;
CREATE TABLE knowledge_attachment (
  attachment_id int          NOT NULL AUTO_INCREMENT,
  knowledge_id  int          NOT NULL COMMENT '연결된 지식 카드',
  file_url      varchar(500) NOT NULL COMMENT '파일 저장 경로',
  file_name     varchar(255) NOT NULL COMMENT '원본 파일명',
  uploaded_by   int          NOT NULL COMMENT '업로드한 사용자 사번',
  is_deleted    tinyint(1)   NOT NULL DEFAULT '0' COMMENT '1=삭제됨, 0=정상 (소프트 삭제)',
  deleted_at    datetime     DEFAULT NULL COMMENT '삭제 처리 시각 (is_deleted=1일 때만 값 존재)',
  uploaded_at   datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (attachment_id),
  KEY idx_ka_card (knowledge_id),
  KEY idx_ka_uploaded_by (uploaded_by),
  CONSTRAINT fk_ka_knowledge FOREIGN KEY (knowledge_id) REFERENCES knowledge (knowledge_id) ON DELETE CASCADE,
  CONSTRAINT fk_ka_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES `user` (user_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 채팅 / 알림 테이블 (v36 신규)
-- 실제 운영 DB에 이미 생성되어 있는 상태 그대로 - FK도 실제로 걸려 있음
-- ============================================================

-- ------------------------------------------------------------
-- 19. CHAT_ROOM - 채팅방 (1:1 또는 그룹)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS chat_room;
CREATE TABLE chat_room (
  room_id    int          NOT NULL AUTO_INCREMENT,
  name       varchar(100) DEFAULT NULL COMMENT '그룹방 이름 - 1:1 방은 NULL(프론트에서 상대 이름을 나열해 표시)',
  is_group   tinyint(1)   NOT NULL COMMENT '0=1:1, 1=그룹(멤버 3명 이상)',
  created_by int          NOT NULL COMMENT '방 생성자 사번',
  created_at datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (room_id),
  KEY idx_chat_room_created_by (created_by),
  CONSTRAINT fk_chat_room_created_by FOREIGN KEY (created_by) REFERENCES `user` (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 20. CHAT_ROOM_MEMBER - 채팅방 참여자
--     동일한 두 사람의 1:1 방 중복 생성은 애플리케이션(chat_service.create_room)
--     에서 방지 - DB 레벨 유니크 제약은 없음(그룹방은 멤버 조합이 자유로워야 함)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS chat_room_member;
CREATE TABLE chat_room_member (
  room_id   int      NOT NULL,
  user_id   int      NOT NULL,
  joined_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (room_id, user_id),
  KEY idx_chat_room_member_user (user_id),
  CONSTRAINT fk_chat_room_member_room FOREIGN KEY (room_id) REFERENCES chat_room (room_id),
  CONSTRAINT fk_chat_room_member_user FOREIGN KEY (user_id) REFERENCES `user` (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 21. CHAT_MESSAGE - 채팅 메시지 (텍스트 전용, v1 범위)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS chat_message;
CREATE TABLE chat_message (
  message_id int      NOT NULL AUTO_INCREMENT,
  room_id    int      NOT NULL COMMENT '연결된 채팅방',
  sender_id  int      NOT NULL COMMENT '발신자 사번',
  content    text     NOT NULL,
  created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (message_id),
  KEY idx_chat_message_room (room_id),
  KEY idx_chat_message_sender (sender_id),
  CONSTRAINT fk_chat_message_room FOREIGN KEY (room_id) REFERENCES chat_room (room_id),
  CONSTRAINT fk_chat_message_sender FOREIGN KEY (sender_id) REFERENCES `user` (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 22. NOTIFICATION - 인앱 알림 (헤더 알림벨 + 채팅방 목록 안읽음 배지가
--     이 테이블 하나를 공유 - is_read 기준으로 두 UI 모두 계산)
--     type은 지금은 'CHAT_MESSAGE' 하나뿐이지만, 나중에 다른 알림 종류로
--     확장할 수 있도록 필드만 열어둔 것
-- ------------------------------------------------------------
DROP TABLE IF EXISTS notification;
CREATE TABLE notification (
  notification_id int          NOT NULL AUTO_INCREMENT,
  user_id          int          NOT NULL COMMENT '알림 수신자 사번',
  type             varchar(20)  NOT NULL COMMENT '알림 종류 - v1은 CHAT_MESSAGE 고정',
  room_id          int          DEFAULT NULL COMMENT '연결된 채팅방 (있는 경우)',
  message_id       int          DEFAULT NULL COMMENT '연결된 메시지 (있는 경우)',
  is_read          tinyint(1)   NOT NULL DEFAULT '0',
  created_at       datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (notification_id),
  KEY idx_notification_user (user_id),
  KEY idx_notification_room (room_id),
  KEY idx_notification_message (message_id),
  CONSTRAINT fk_notification_user FOREIGN KEY (user_id) REFERENCES `user` (user_id),
  CONSTRAINT fk_notification_room FOREIGN KEY (room_id) REFERENCES chat_room (room_id),
  CONSTRAINT fk_notification_message FOREIGN KEY (message_id) REFERENCES chat_message (message_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------------
-- 23. DEVICE_TOKEN - FCM 웹 푸시 기기 토큰 (사용자당 여러 브라우저/기기 지원)
--     같은 fcm_token이 이미 다른 사용자로 등록돼 있으면 upsert로 소유자를
--     재할당한다 (기기 공유 시나리오) - app/api/routers/notification.py 참고
-- ------------------------------------------------------------
DROP TABLE IF EXISTS device_token;
CREATE TABLE device_token (
  token_id   int          NOT NULL AUTO_INCREMENT,
  user_id    int          NOT NULL,
  fcm_token  varchar(255) NOT NULL,
  created_at datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (token_id),
  UNIQUE KEY uq_device_token_fcm_token (fcm_token),
  KEY idx_device_token_user (user_id),
  CONSTRAINT fk_device_token_user FOREIGN KEY (user_id) REFERENCES `user` (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- FK 검사 재활성화
SET FOREIGN_KEY_CHECKS = 1;
