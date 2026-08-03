-- ============================================================
-- 민원(PETITION) + 사업(PROJECT) 시드데이터 - 배포용 INSERT
-- 대상 스키마: v40_공공이음_DDL_FK포함_대문자.sql (테이블명 대문자 버전)
--
-- 전제조건 (아래 행이 이미 존재해야 FK가 통과합니다):
--   - DEPARTMENT '01'(교통부) - v40 DDL에 기본 포함됨
--   - USER 20260101, 20260102, 20260106, 20260107 - 별도 사용자 시드 필요
--   - TASK 28, 30, 31 (department_code='01') - 별도 업무 시드 필요
--
-- 원본 스크립트와의 차이점:
--   원본은 PROJECT_MEMBER에서 project_id를 101~104로 하드코딩했는데, 이는 기존 개발 DB의
--   AUTO_INCREMENT 카운터가 이미 100을 넘어 있었기 때문에 우연히 맞았던 값입니다. 이 DDL로
--   새로 만든 DB에 그대로 실행하면 4건의 PROJECT는 실제로 1~4가 배정되어 PROJECT_MEMBER가
--   엉뚱한(존재하지 않는) project_id를 참조하게 됩니다. 그래서 각 PROJECT INSERT 직후
--   LAST_INSERT_ID()를 세션 변수에 담아 실제 배정된 id를 PROJECT_MEMBER에서 그대로 쓰도록
--   바꿨습니다.
-- ============================================================

USE ggieum;

-- ============================================================
-- 민원(PETITION) 시드데이터
-- ============================================================
INSERT INTO PETITION
(title, content, received_at, status_code, task_id, department_code, assignee_user_id, due_date)
VALUES

-- ===== wait(01) =====
('강남대로 신호등 점멸 이상 신고',
'강남대로 사거리 신호등이 반복적으로 점멸하여 차량 통행에 혼선이 발생하고 있습니다. 출퇴근 시간 교통사고 위험이 있으므로 점검을 요청드립니다.',
'2026-07-30 08:40:00','01',31,'01',20260106,DATE_ADD(CURDATE(), INTERVAL 7 DAY)),

('역삼초등학교 어린이보호구역 과속방지시설 설치 요청',
'등교 시간 과속 차량이 많아 학부모들의 민원이 지속적으로 발생하고 있습니다. 과속방지턱 또는 단속시설 설치를 검토해 주시기 바랍니다.',
'2026-07-30 09:25:00','01',31,'01',20260107,DATE_ADD(CURDATE(), INTERVAL 7 DAY)),


-- ===== check(02) =====
('논현역 버스정류장 승차 대기공간 개선 요청',
'출퇴근 시간 승객이 많아 인도까지 줄이 길게 늘어서 매우 혼잡합니다. 승차 대기공간 확장 검토를 요청드립니다.',
'2026-07-28 10:10:00','02',30,'01',20260102,DATE_ADD(CURDATE(), INTERVAL 5 DAY)),

('삼성역 횡단보도 신호시간 연장 요청',
'노약자와 유모차 이용자가 신호 시간 내 횡단을 마치기 어렵습니다. 보행신호 시간을 연장해 주시기 바랍니다.',
'2026-07-28 14:20:00','02',30,'01',20260101,DATE_ADD(CURDATE(), INTERVAL 5 DAY)),


-- ===== progress(03) =====
('테헤란로 포트홀 긴급 보수 요청',
'테헤란로 8차선 도로 중앙부에 깊은 포트홀이 발생하여 차량 파손 및 오토바이 사고 위험이 있습니다. 긴급 보수를 요청드립니다.',
'2026-07-25 09:05:00','03',28,'01',20260106,DATE_ADD(CURDATE(), INTERVAL 3 DAY)),

('불법 주정차 상습구역 단속 요청',
'논현동 영동시장 입구에 불법 주정차 차량이 상습적으로 발생하여 소방차와 구급차 진입이 어렵습니다. 집중 단속을 요청드립니다.',
'2026-07-25 11:20:00','03',31,'01',20260107,DATE_ADD(CURDATE(), INTERVAL 3 DAY)),


-- ===== done(04) =====
('역삼공원 가로등 고장 신고',
'공원 산책로 가로등 4개가 점등되지 않아 야간 보행이 위험했습니다. 빠른 조치를 요청드립니다.',
'2026-07-10 10:00:00','04',28,'01',20260102,'2026-07-17'),

('강남역 버스정류장 노선안내판 교체 요청',
'버스 노선안내판이 훼손되어 노선 정보를 확인하기 어렵다는 민원이 접수되었습니다. 교체를 요청드립니다.',
'2026-07-08 09:00:00','04',30,'01',20260101,'2026-07-15');
-- 민원 시드데이터 끝


-- ============================================================
-- 사업(PROJECT) 시드데이터 1 - 한강대교 보행환경 개선 사업
-- ============================================================
INSERT INTO PROJECT (name, stage_code, department_code, start_date, deadline, business_content, overview,
sec_overview, sec_background, sec_goals, sec_detailed_plan, sec_schedule, sec_execution_system, sec_budget, sec_expected_effect, sec_post_management, approved_at)
VALUES (
'한강대교 보행환경 개선 사업',
'01',
'01',
'2026-07-01',
'2026-12-31',
'한강대교 보행로 확장 및 안전펜스 설치를 통한 보행 안전 강화 사업',
'한강대교 보행환경 개선을 위한 사업입니다.',

-- sec_overview (Ⅰ. 사업 개요)
'<h2>Ⅰ. 사업 개요</h2>
<p><strong>&nbsp;&nbsp;사업명 :</strong>&nbsp;&nbsp;한강대교 보행환경 개선 사업</p>
<p></p>
<p><strong>&nbsp;&nbsp;사업개요 :</strong>&nbsp;&nbsp;한강대교 보행로 확장 및 안전펜스 설치를 통한 보행자 안전 강화</p>
<p></p>
<p><strong>&nbsp;&nbsp;사업기간 :</strong>&nbsp;&nbsp;2026-07-01 ~ 2026-12-31</p>
<p><strong>&nbsp;&nbsp;사업위치 :</strong>&nbsp;&nbsp;서울시 용산구 ~ 동작구 한강대교 일원</p>
<p><strong>&nbsp;&nbsp;담당부서 :</strong>&nbsp;&nbsp;교통부</p>
<p><strong>&nbsp;&nbsp;참여부서 :</strong>&nbsp;&nbsp;-</p>
<p><strong>&nbsp;&nbsp;담당자 :</strong>&nbsp;&nbsp;김도현</p>
<p><strong>&nbsp;&nbsp;참여부서원 :</strong>&nbsp;&nbsp;이지안, 박서우</p>
<p><strong>&nbsp;&nbsp;총사업비 :</strong>&nbsp;&nbsp;600,000천원</p>
<p><strong>&nbsp;&nbsp;사업유형 :</strong>&nbsp;&nbsp;신규</p>',

-- sec_background (Ⅱ. 추진 배경 및 필요성)
'<h2>Ⅱ. 추진 배경 및 필요성</h2>
<h3>1. 추진 배경</h3>
<p><strong>&nbsp;&nbsp;□ 현재 업무 현황</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 한강대교 보행로 폭 1.2m로 자전거·보행자 혼용 사용 중</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 일 평균 보행자 통행량 약 3,200명, 자전거 약 800대</p>
<p><strong>&nbsp;&nbsp;□ 발생 문제</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 협소한 보행로로 인해 자전거·보행자 충돌 사고 연 12건 발생</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 노후 안전펜스 부식으로 추락 위험 증가</p>
<p><strong>&nbsp;&nbsp;□ 개선 필요성</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 보행로 확장 및 안전펜스 교체를 통한 시민 안전 확보 시급</p>
<h3>2. 사업 필요성</h3>
<p><strong>&nbsp;&nbsp;□ 행정 효율 개선</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 사고 처리 및 민원 대응 비용 절감</p>
<p><strong>&nbsp;&nbsp;□ 업무 처리시간 단축</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 보행로 분리로 보행자·자전거 통행 속도 향상</p>
<p><strong>&nbsp;&nbsp;□ 서비스 품질 향상</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 한강 조망 보행환경 개선으로 시민 만족도 향상</p>',

-- sec_goals (Ⅲ. 사업 목표)
'<h2>Ⅲ. 사업 목표</h2>
<p><strong>&nbsp;&nbsp;□ 최종 목표</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 한강대교 보행로 안전사고 제로화 및 보행 만족도 향상</p>
<p></p>
<p><strong>&nbsp;&nbsp;□ 세부 목표</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;1. 목표: 보행로 확장</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;성과지표: 보행로 폭 1.2m → 2.7m 확장 (500m 구간)</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;2. 목표: 안전펜스 교체</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;성과지표: 노후 안전펜스 500m 전면 교체</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;3. 목표: 보행자 안전사고 감소</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;성과지표: 연간 충돌 사고 12건 → 3건 이하 감소</p>',

-- sec_detailed_plan (Ⅳ. 세부 추진 계획)
'<h2>Ⅳ. 세부 추진 계획</h2>
<h3>1. 사업 내용</h3>
<p>&nbsp;&nbsp;○ 과업 1: 보행로 확장 공사 (500m 구간)</p>
<p>&nbsp;&nbsp;○ 과업 2: 노후 안전펜스 교체 (500m)</p>
<p>&nbsp;&nbsp;○ 과업 3: 자전거·보행자 분리 구획선 도색</p>
<h3>2. 세부 실행 계획</h3>
<p><strong>&nbsp;&nbsp;가. 보행로 확장 공사</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 주요 내용</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 기존 1.2m 보행로를 2.7m로 확장, 자전거 전용 구간 분리</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 추진 방법</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 공개 입찰을 통한 시공사 선정 후 야간 공사로 교통 영향 최소화</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 산출물</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 확장 보행로 500m, 준공 검사 보고서</p>
<p></p>
<p><strong>&nbsp;&nbsp;나. 운영 계획</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 운영 방법</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 준공 후 서울시설공단에 운영 이관</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 담당자</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 교통부 김도현 부장</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 관리 체계</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 연 2회 정기점검 및 이상 발생 시 즉시 보고</p>',

-- sec_schedule (Ⅴ. 추진 일정)
'<h2>Ⅴ. 추진 일정</h2>
<p><strong>&nbsp;&nbsp;사업 일정</strong>&nbsp;(추진 단계별 일정을 월 단위로 작성)</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 계획 수립: 2026년 7월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 설계: 2026년 7월 ~ 8월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 공사 발주 및 착공: 2026년 9월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 시공: 2026년 9월 ~ 11월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 준공 및 검수: 2026년 12월</p>
<p></p>
<p><em>※ 야간 공사 원칙으로 진행하여 한강대교 통행 영향 최소화</em></p>',

-- sec_execution_system (Ⅵ. 사업 추진 체계)
'<h2>Ⅵ. 사업 추진 체계</h2>
<p><strong>&nbsp;&nbsp;총괄 책임자</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 이름: 김도현</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 직책: 교통부 부장</p>
<p></p>
<p><strong>&nbsp;&nbsp;사업 담당 부서</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 부서명: 교통부</p>
<p></p>
<p><strong>&nbsp;&nbsp;협력 기관</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 운영 담당: 서울시설공단</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 시공 담당: 공개입찰 선정 업체</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 협력 기관: 용산구청, 동작구청</p>',

-- sec_budget (Ⅶ. 예산 계획)
'<h2>Ⅶ. 예산 계획</h2>
<p><strong>&nbsp;&nbsp;예산 내역</strong> (단위: 천원)</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 인건비:&nbsp;50,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 설계 및 감리 인력 5명 × 10개월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 공사비:&nbsp;500,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 보행로 확장 공사 및 안전펜스 교체 500m</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 운영비:&nbsp;30,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 공사 기간 중 안전 관리 및 홍보비</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 기타:&nbsp;20,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 준공 검사 및 예비비</p>
<p></p>
<p><strong>&nbsp;&nbsp;합계:</strong>&nbsp;&nbsp;600,000천원 (시비 100%)</p>',

-- sec_expected_effect (Ⅷ. 기대 효과)
'<h2>Ⅷ. 기대 효과</h2>
<h3>1. 정량적 효과</h3>
<p>&nbsp;&nbsp;□ 안전사고 감소</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;기존: 연간 충돌 사고 12건</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;개선: 연간 3건 이하 (75% 감소)</p>
<p></p>
<p>&nbsp;&nbsp;□ 보행자 통행 속도</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;기존: 혼잡으로 평균 도보 속도 저하</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;개선: 분리 구획으로 통행 속도 20% 향상</p>
<p></p>
<p>&nbsp;&nbsp;□ 민원 처리 비용</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;기존: 연간 사고 관련 민원 처리 비용 약 3,000만원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;개선: 50% 절감 예상</p>
<h3>2. 정성적 효과</h3>
<p>&nbsp;&nbsp;□ 보행 안전 강화</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 자전거·보행자 분리로 쾌적하고 안전한 보행환경 조성</p>
<p></p>
<p>&nbsp;&nbsp;□ 시민 만족도 향상</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 한강 조망 보행로 개선으로 관광·여가 만족도 향상</p>
<p></p>
<p>&nbsp;&nbsp;□ 행정 서비스 개선</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 선제적 시설 개선으로 민원 발생 사전 차단</p>',

-- sec_post_management (Ⅸ. 사후 관리 계획)
'<h2>Ⅸ. 사후 관리 계획</h2>
<p><strong>&nbsp;&nbsp;운영기간</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 준공 후 20년 (2027년 1월 ~ 2047년 12월)</p>
<p><strong>&nbsp;&nbsp;관리부서</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 서울시설공단 (교통부 감독)</p>
<p><strong>&nbsp;&nbsp;유지보수 방법</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 연 2회 정기점검 (4월, 10월)</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 안전펜스 부식·파손 발생 시 즉시 보수</p>
<p><strong>&nbsp;&nbsp;개선 계획</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 3년 후 보행량 데이터 분석 후 추가 확장 여부 검토</p>',

NULL
);
SET @proj_hangang = LAST_INSERT_ID();
-- 사업 시드데이터 1 한강대교 보행환경 개선 사업 끝


-- ============================================================
-- 사업(PROJECT) 시드데이터 2 - 서울시 심야버스 노선 확대 사업
-- ============================================================
INSERT INTO PROJECT (name, stage_code, department_code, start_date, deadline, business_content, overview, sec_overview, sec_background, sec_goals, sec_detailed_plan, sec_schedule, sec_execution_system, sec_budget, sec_expected_effect, sec_post_management, approved_at)
VALUES (
'서울시 심야버스 노선 확대 사업',
'01',
'01',
'2026-08-01',
'2026-12-31',
'올빼미버스 노선 추가를 통한 심야 대중교통 서비스 강화',
'심야 시간대 대중교통 공백 해소를 위한 올빼미버스 노선 확대 사업입니다.',

'<h2>Ⅰ. 사업 개요</h2>
<p><strong>&nbsp;&nbsp;사업명 :</strong>&nbsp;&nbsp;서울시 심야버스 노선 확대 사업</p>
<p></p>
<p><strong>&nbsp;&nbsp;사업개요 :</strong>&nbsp;&nbsp;올빼미버스 노선 3개 추가 신설을 통한 심야 대중교통 서비스 강화</p>
<p></p>
<p><strong>&nbsp;&nbsp;사업기간 :</strong>&nbsp;&nbsp;2026-08-01 ~ 2026-12-31</p>
<p><strong>&nbsp;&nbsp;사업위치 :</strong>&nbsp;&nbsp;서울시 전역 (강남, 마포, 노원 구간 중심)</p>
<p><strong>&nbsp;&nbsp;담당부서 :</strong>&nbsp;&nbsp;교통부</p>
<p><strong>&nbsp;&nbsp;참여부서 :</strong>&nbsp;&nbsp;-</p>
<p><strong>&nbsp;&nbsp;담당자 :</strong>&nbsp;&nbsp;김도현</p>
<p><strong>&nbsp;&nbsp;참여부서원 :</strong>&nbsp;&nbsp;이지안, 최하윤</p>
<p><strong>&nbsp;&nbsp;총사업비 :</strong>&nbsp;&nbsp;400,000천원</p>
<p><strong>&nbsp;&nbsp;사업유형 :</strong>&nbsp;&nbsp;신규</p>',

'<h2>Ⅱ. 추진 배경 및 필요성</h2>
<h3>1. 추진 배경</h3>
<p><strong>&nbsp;&nbsp;□ 현재 업무 현황</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 현재 올빼미버스 9개 노선 운행 중, 심야 이용 수요 대비 노선 부족</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 자정 이후 대중교통 공백 구간 다수 존재</p>
<p><strong>&nbsp;&nbsp;□ 발생 문제</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 심야 택시 수요 급증으로 택시 잡기 어려움 민원 연 800건 이상</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 교통 취약계층(노인, 장애인) 심야 이동 수단 부재</p>
<p><strong>&nbsp;&nbsp;□ 개선 필요성</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 심야 대중교통 노선 확대를 통한 시민 이동권 보장 시급</p>
<h3>2. 사업 필요성</h3>
<p><strong>&nbsp;&nbsp;□ 행정 효율 개선</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 심야 교통 민원 처리 업무 감소</p>
<p><strong>&nbsp;&nbsp;□ 업무 처리시간 단축</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 노선 신설로 시민 심야 이동 소요시간 단축</p>
<p><strong>&nbsp;&nbsp;□ 서비스 품질 향상</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 24시간 대중교통 서비스 체계 강화</p>',

'<h2>Ⅲ. 사업 목표</h2>
<p><strong>&nbsp;&nbsp;□ 최종 목표</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 서울시 심야 교통 공백 구간 해소 및 시민 이동권 보장</p>
<p></p>
<p><strong>&nbsp;&nbsp;□ 세부 목표</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;1. 목표: 올빼미버스 노선 확대</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;성과지표: 기존 9개 노선 → 12개 노선으로 확대</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;2. 목표: 배차 간격 단축</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;성과지표: 평균 배차 간격 60분 → 30분으로 단축</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;3. 목표: 심야 이용객 증가</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;성과지표: 심야 대중교통 이용률 25% 향상</p>',

'<h2>Ⅳ. 세부 추진 계획</h2>
<h3>1. 사업 내용</h3>
<p>&nbsp;&nbsp;○ 과업 1: 신규 노선 3개 설계 및 운수업체 선정</p>
<p>&nbsp;&nbsp;○ 과업 2: 시범운행 및 이용객 모니터링</p>
<p>&nbsp;&nbsp;○ 과업 3: 정식 운행 전환 및 홍보</p>
<h3>2. 세부 실행 계획</h3>
<p><strong>&nbsp;&nbsp;가. 노선 설계 및 업체 선정</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 주요 내용</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 강남~마포, 노원~종로, 송파~여의도 3개 구간 노선 설계</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 추진 방법</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 서울시버스운송조합과 협의 후 운수업체 공개 모집</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 산출물</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 노선 설계도, 운수업체 계약서</p>
<p></p>
<p><strong>&nbsp;&nbsp;나. 운영 계획</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 운영 방법</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 자정 ~ 오전 5시 운행, 30분 간격 배차</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 담당자</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 교통부 김도현 부장</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 관리 체계</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 월별 이용객 데이터 분석 및 노선 조정</p>',

'<h2>Ⅴ. 추진 일정</h2>
<p><strong>&nbsp;&nbsp;사업 일정</strong>&nbsp;(추진 단계별 일정을 월 단위로 작성)</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 계획 수립: 2026년 8월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 노선 설계 및 업체 선정: 2026년 8월 ~ 9월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 시범운행: 2026년 10월 ~ 11월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 정식 운행 전환: 2026년 12월</p>
<p></p>
<p><em>※ 시범운행 기간 이용객 피드백 반영하여 노선 최적화 후 정식 전환</em></p>',

'<h2>Ⅵ. 사업 추진 체계</h2>
<p><strong>&nbsp;&nbsp;총괄 책임자</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 이름: 김도현</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 직책: 교통부 부장</p>
<p></p>
<p><strong>&nbsp;&nbsp;사업 담당 부서</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 부서명: 교통부</p>
<p></p>
<p><strong>&nbsp;&nbsp;협력 기관</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 운영 담당: 서울시버스운송조합</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 홍보 담당: 서울시 교통정보과</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 협력 기관: 각 자치구 교통과</p>',

'<h2>Ⅶ. 예산 계획</h2>
<p><strong>&nbsp;&nbsp;예산 내역</strong> (단위: 천원)</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 인건비:&nbsp;20,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 담당 인력 2명 × 5개월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 운행 보조금:&nbsp;350,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 노선 3개 × 시범~정식 운행 운수업체 보조금</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 홍보비:&nbsp;20,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: SNS·현수막·정류장 안내문 제작</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 기타:&nbsp;10,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 예비비</p>
<p></p>
<p><strong>&nbsp;&nbsp;합계:</strong>&nbsp;&nbsp;400,000천원 (시비 100%)</p>',

'<h2>Ⅷ. 기대 효과</h2>
<h3>1. 정량적 효과</h3>
<p>&nbsp;&nbsp;□ 심야 이용객</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;기존: 올빼미버스 일 평균 이용객 12,000명</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;개선: 15,000명으로 25% 증가 목표</p>
<p></p>
<p>&nbsp;&nbsp;□ 심야 택시 민원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;기존: 연 800건</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;개선: 500건 이하로 감소</p>
<p></p>
<p>&nbsp;&nbsp;□ 배차 간격</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;기존: 평균 60분</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;개선: 30분으로 단축</p>
<h3>2. 정성적 효과</h3>
<p>&nbsp;&nbsp;□ 이동권 보장</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 심야 교통 취약계층 이동 편의 향상</p>
<p></p>
<p>&nbsp;&nbsp;□ 시민 만족도 향상</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 24시간 대중교통 서비스로 생활 편의 증대</p>
<p></p>
<p>&nbsp;&nbsp;□ 택시 수급 안정</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 심야 택시 수요 분산으로 택시 잡기 어려움 해소</p>',

'<h2>Ⅸ. 사후 관리 계획</h2>
<p><strong>&nbsp;&nbsp;운영기간</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 정식 운행 전환 후 지속 운영 (2027년 이후 연장 여부 검토)</p>
<p><strong>&nbsp;&nbsp;관리부서</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 교통부 (서울시버스운송조합 협력)</p>
<p><strong>&nbsp;&nbsp;유지보수 방법</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 월별 이용객 데이터 분석 및 노선 최적화</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 분기별 운수업체 운행 실태 점검</p>
<p><strong>&nbsp;&nbsp;개선 계획</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 1년 후 이용 데이터 분석 후 추가 노선 신설 여부 결정</p>',

NULL
);
SET @proj_simya = LAST_INSERT_ID();
-- 사업 시드데이터 2 서울시 심야버스 노선 확대 사업 끝

-- ============================================================
-- 사업(PROJECT) 시드데이터 3 - 광화문 광장 주변 교통체계 개편 사업
-- ============================================================
INSERT INTO PROJECT ( name, stage_code, department_code, start_date, deadline, business_content, overview, sec_overview, sec_background, sec_goals, sec_detailed_plan, sec_schedule, sec_execution_system, sec_budget, sec_expected_effect, sec_post_management, approved_at)
VALUES (
'광화문 광장 주변 교통체계 개편 사업', '02', '01', '2026-01-01', '2026-06-30',
'광화문 광장 주변 교통 흐름 개선 및 보행자 중심 교통체계 구축을 위한 버스 노선 개편, 보행자 우선도로 지정 사업',
'광화문 광장 주변 교통체계를 보행자 중심으로 개편하고 도심 교통 흐름을 개선하는 사업입니다.',

-- Ⅰ. 사업 개요
'<h2>Ⅰ. 사업 개요</h2>
<p><strong>&nbsp;&nbsp;사업명 :</strong>&nbsp;&nbsp;광화문 광장 주변 교통체계 개편 사업</p>
<p></p>
<p><strong>&nbsp;&nbsp;사업개요 :</strong>&nbsp;&nbsp;광화문 광장 주변 교통 흐름 분석을 기반으로 버스 노선 조정 및 보행자 우선도로 지정 등 보행 친화형 교통체계 구축</p>
<p></p>
<p><strong>&nbsp;&nbsp;사업기간 :</strong>&nbsp;&nbsp;2026-01-01 ~ 2026-06-30</p>
<p><strong>&nbsp;&nbsp;사업위치 :</strong>&nbsp;&nbsp;서울시 종로구 광화문 광장 및 세종대로 일원</p>
<p><strong>&nbsp;&nbsp;담당부서 :</strong>&nbsp;&nbsp;교통부</p>
<p><strong>&nbsp;&nbsp;참여부서 :</strong>&nbsp;&nbsp;-</p>
<p><strong>&nbsp;&nbsp;담당자 :</strong>&nbsp;&nbsp;김도현</p>
<p><strong>&nbsp;&nbsp;참여부서원 :</strong>&nbsp;&nbsp;박서우, 정예준</p>
<p><strong>&nbsp;&nbsp;총사업비 :</strong>&nbsp;&nbsp;500백만원</p>
<p><strong>&nbsp;&nbsp;사업유형 :</strong>&nbsp;&nbsp;신규</p>',

-- Ⅱ. 추진 배경 및 필요성
'<h2>Ⅱ. 추진 배경 및 필요성</h2>

<h3>1. 추진 배경</h3>

<p><strong>&nbsp;&nbsp;□ 현재 업무 현황</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 광화문 광장 재조성 이후 주변 교통 환경 변화에 따른 교통 운영 개선 필요성 증가</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 세종대로 일대 출퇴근 시간대 차량 집중으로 교통 혼잡 지속 발생</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 광화문 광장 이용 시민 및 관광객 증가에 따라 보행 중심 교통체계 요구 증가</p>

<p><strong>&nbsp;&nbsp;□ 발생 문제</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 버스, 택시, 승용차 혼재로 보행자 안전사고 위험 증가</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 관광객 보행 동선과 차량 이동 동선 충돌로 교통 관련 민원 연 500건 이상 발생</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 행사 및 집회 등 대규모 인원 밀집 상황 발생 시 교통 운영 대응 필요</p>

<p><strong>&nbsp;&nbsp;□ 개선 필요성</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 차량 중심 교통체계에서 보행자 중심 교통체계로 전환하여 안전한 도심 환경 조성 필요</p>

<h3>2. 사업 필요성</h3>

<p><strong>&nbsp;&nbsp;□ 교통 운영 효율 개선</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 교통량 분석 기반 노선 조정으로 도심 교통 흐름 개선</p>

<p><strong>&nbsp;&nbsp;□ 시민 안전 확보</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 보행자 우선도로 지정 및 차량 통제를 통한 안전한 보행환경 조성</p>

<p><strong>&nbsp;&nbsp;□ 도시 경쟁력 강화</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 광화문 역사·문화 공간 접근성 향상 및 시민 이용 편의 증진</p>',

-- Ⅲ. 사업 목표
'<h2>Ⅲ. 사업 목표</h2>

<p><strong>&nbsp;&nbsp;□ 최종 목표</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 광화문 광장 주변 보행자 중심 교통체계 구축 및 도심 교통 흐름 개선</p>

<p></p>

<p><strong>&nbsp;&nbsp;□ 세부 목표</strong></p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;1. 목표: 교통 흐름 개선</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;성과지표: 주요 구간 평균 통행시간 15% 개선</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;2. 목표: 버스 운영 안정화</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;성과지표: 광화문 경유 버스 노선 5개 조정 및 운행 효율 개선</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;3. 목표: 보행환경 개선</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;성과지표: 세종대로 일대 800m 보행자 우선도로 지정</p>',

-- Ⅳ. 세부 추진 계획
'<h2>Ⅳ. 세부 추진 계획</h2>

<h3>1. 사업 내용</h3>

<p>&nbsp;&nbsp;○ 과업 1: 광화문 일대 교통 현황 조사 및 개선안 수립</p>
<p>&nbsp;&nbsp;○ 과업 2: 버스 노선 개편 및 정류장 운영 개선</p>
<p>&nbsp;&nbsp;○ 과업 3: 보행자 우선도로 지정 및 교통시설 개선</p>
<p>&nbsp;&nbsp;○ 과업 4: 시민 홍보 및 시행 후 운영 모니터링</p>

<h3>2. 세부 실행 계획</h3>

<p><strong>&nbsp;&nbsp;가. 교통 현황 분석 및 개선안 수립</strong></p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 주요 내용</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 광화문 일대 교통량, 보행량 및 차량 흐름 분석</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 추진 방법</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 현장 조사 및 교통 데이터 분석을 통한 개선 방향 도출</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 산출물</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 교통 개선 검토 보고서 및 운영 개선안</p>

<p></p>

<p><strong>&nbsp;&nbsp;나. 버스 노선 개편</strong></p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 주요 내용</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 광화문 경유 주요 버스 노선 5개 조정 및 우회 운영 검토</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 추진 방법</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 서울시버스운송조합 및 관계 기관 협의를 통한 노선 개편 추진</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 산출물</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 노선 변경 고시문, 정류장 안내 시설 개선 자료</p>

<p></p>

<p><strong>&nbsp;&nbsp;다. 보행자 우선도로 조성</strong></p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 주요 내용</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 세종대로 일대 800m 구간 보행자 우선도로 지정 및 시설 개선</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 추진 방법</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 교통안전시설 설치 및 차량 통행 관리 체계 구축</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 산출물</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 보행자 우선도로 지정 자료 및 시설물 설치 결과 보고서</p>

<p></p>

<p><strong>&nbsp;&nbsp;라. 운영 계획</strong></p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 운영 방법</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 보행자 우선도로 구간 차량 진입 관리 및 지속 모니터링 실시</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 담당자</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 교통부 김도현 부장</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 관리 체계</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 종로구청 및 경찰서 협업을 통한 교통 관리 체계 운영</p>',

-- Ⅴ. 추진 일정
'<h2>Ⅴ. 추진 일정</h2>

<p><strong>&nbsp;&nbsp;사업 일정</strong> (추진 단계별 일정을 월 단위로 작성)</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 교통 현황 조사 및 사업 계획 수립: 2026년 1월 ~ 2월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 주민 의견 수렴 및 관계 기관 협의: 2026년 2월 ~ 3월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 버스 노선 개편 및 시설 개선 설계: 2026년 3월 ~ 4월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 보행자 우선도로 시설 설치 및 홍보: 2026년 4월 ~ 5월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 시행 및 운영 점검: 2026년 6월</p>

<p></p>

<p><em>※ 관계 기관 협의 및 시민 의견 수렴 결과에 따라 일정 일부 조정 가능</em></p>',

-- Ⅵ. 사업 추진 체계
'<h2>Ⅵ. 사업 추진 체계</h2>

<p><strong>&nbsp;&nbsp;총괄 책임자</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 이름: 김도현</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 직책: 교통부 부장</p>

<p></p>

<p><strong>&nbsp;&nbsp;사업 담당 부서</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 부서명: 교통부</p>

<p></p>

<p><strong>&nbsp;&nbsp;협력 기관</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 교통 운영 협력: 종로구청 교통과</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 단속 협력: 종로경찰서</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 노선 협력: 서울시버스운송조합</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 협의 기관: 서울교통공사, 지역 주민협의체</p>',

-- Ⅶ. 예산 계획
'<h2>Ⅶ. 예산 계획</h2>

<p><strong>&nbsp;&nbsp;예산 내역</strong> (단위: 천원)</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 인건비:&nbsp;30,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 사업 담당 인력 운영 및 행정 지원 인력 3명 × 6개월</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 교통시설 개선비:&nbsp;300,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 보행자 우선도로 시설물 설치 및 교통 안내 시설 개선</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 교통 분석 용역비:&nbsp;100,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 교통량 분석, 노선 개편 검토 및 개선안 수립</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 홍보 및 시민소통비:&nbsp;50,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 주민 의견 수렴, 안내 홍보물 제작 및 온라인 홍보</p>

<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 기타:&nbsp;20,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 예비비 및 운영 조정 비용</p>

<p></p>

<p><strong>&nbsp;&nbsp;합계:</strong>&nbsp;&nbsp;500,000천원 (국비 200,000천원, 시비 300,000천원)</p>',

-- Ⅷ. 기대 효과
'<h2>Ⅷ. 기대 효과</h2>

<h3>1. 정량적 효과</h3>

<p>&nbsp;&nbsp;□ 교통사고 감소</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;기존: 광화문 일대 연간 교통사고 40건</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;개선 목표: 교통사고 발생 35% 감소</p>

<p></p>

<p>&nbsp;&nbsp;□ 교통 민원 감소</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;기존: 연간 교통 관련 민원 약 500건</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;개선 목표: 연간 민원 300건 이하 관리</p>

<p></p>

<p>&nbsp;&nbsp;□ 버스 운행 안정화</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;기존: 출퇴근 시간 평균 15분 지연 발생</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;개선 목표: 평균 지연시간 5분 이하 단축</p>


<h3>2. 정성적 효과</h3>

<p>&nbsp;&nbsp;□ 보행 안전 강화</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 차량 중심 공간을 보행 친화 공간으로 개선하여 안전한 도시 환경 조성</p>

<p></p>

<p>&nbsp;&nbsp;□ 관광 환경 개선</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 광화문 역사·문화 공간 접근성 향상으로 시민 및 관광객 만족도 증대</p>

<p></p>

<p>&nbsp;&nbsp;□ 도심 교통 운영 개선</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 교통 흐름 분석 기반 운영으로 효율적인 도심 교통 관리 체계 구축</p>',

-- Ⅸ. 사후 관리 계획
'<h2>Ⅸ. 사후 관리 계획</h2>

<p><strong>&nbsp;&nbsp;운영기간</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 시행 후 지속 운영 및 정기적인 효과 분석 실시</p>

<p><strong>&nbsp;&nbsp;관리부서</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 교통부 (종로구청 및 관계 기관 협력)</p>

<p><strong>&nbsp;&nbsp;유지관리 방법</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 분기별 교통량 및 보행량 데이터 분석</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 보행자 우선도로 시설물 연 2회 정기 점검</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 시민 의견 및 민원 데이터를 기반으로 지속적인 교통 운영 개선</p>

<p><strong>&nbsp;&nbsp;개선 계획</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 시행 6개월 후 교통 변화 분석 결과를 기반으로 추가 노선 조정 및 운영 개선 검토</p>',

'2026-06-30 00:00:00'
);
SET @proj_gwanghwamun = LAST_INSERT_ID();
-- 사업 시드데이터 3 광화문 광장 주변 교통체계 개편 사업 끝

-- ============================================================
-- 사업(PROJECT) 시드데이터 4 - 서울역 환승센터 혼잡 개선 사업
-- ============================================================
INSERT INTO PROJECT (
name,
stage_code,
department_code,
start_date,
deadline,
business_content,
overview,
sec_overview,
sec_background,
sec_goals,
sec_detailed_plan,
sec_schedule,
sec_execution_system,
sec_budget,
sec_expected_effect,
sec_post_management,
approved_at
)
VALUES (
'서울역 환승센터 혼잡 개선 사업',
'02',
'01',
'2026-02-01',
'2026-07-31',
'서울역 환승 이용객 증가에 따른 환승 동선 개선 및 스마트 안내 시스템 구축을 통한 대중교통 이용 편의 향상 사업',
'서울역 환승센터 내 이용객 이동 동선을 개선하고 스마트 안내 체계를 구축하여 대중교통 환승 효율을 높이는 사업입니다.',

'<h2>Ⅰ. 사업 개요</h2>
<p><strong>&nbsp;&nbsp;사업명 :</strong>&nbsp;&nbsp;서울역 환승센터 혼잡 개선 사업</p>
<p></p>
<p><strong>&nbsp;&nbsp;사업개요 :</strong>&nbsp;&nbsp;서울역 환승센터 이용객 증가에 대응하기 위한 환승 동선 재설계 및 스마트 안내 시스템 구축</p>
<p></p>
<p><strong>&nbsp;&nbsp;사업기간 :</strong>&nbsp;&nbsp;2026-02-01 ~ 2026-07-31</p>
<p><strong>&nbsp;&nbsp;사업위치 :</strong>&nbsp;&nbsp;서울시 용산구 서울역 및 환승센터 일원</p>
<p><strong>&nbsp;&nbsp;담당부서 :</strong>&nbsp;&nbsp;교통부</p>
<p><strong>&nbsp;&nbsp;참여부서 :</strong>&nbsp;&nbsp;-</p>
<p><strong>&nbsp;&nbsp;담당자 :</strong>&nbsp;&nbsp;김도현</p>
<p><strong>&nbsp;&nbsp;참여부서원 :</strong>&nbsp;&nbsp;이지안, 최하윤, 강채윤</p>
<p><strong>&nbsp;&nbsp;총사업비 :</strong>&nbsp;&nbsp;700백만원</p>
<p><strong>&nbsp;&nbsp;사업유형 :</strong>&nbsp;&nbsp;신규</p>',

'<h2>Ⅱ. 추진 배경 및 필요성</h2>
<h3>1. 추진 배경</h3>
<p><strong>&nbsp;&nbsp;□ 현재 업무 현황</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 서울역은 KTX, 수도권 전철, 버스 등 다양한 교통수단이 집중되는 서울의 대표적인 광역 환승 거점</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 일 평균 이용객 증가로 출퇴근 시간대 환승 공간 내 혼잡 지속 발생</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 철도·지하철·버스 간 환승 동선이 명확하게 구분되지 않아 이용객 불편 증가</p>


<p><strong>&nbsp;&nbsp;□ 발생 문제</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 환승 구간 병목 현상으로 평균 이동 시간이 증가하고 이용객 대기 발생</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 노후화된 안내 시설로 목적지 탐색 관련 민원 지속 발생</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 대규모 행사 및 출퇴근 시간 이용객 집중 시 안전 관리 필요성 증가</p>
<p><strong>&nbsp;&nbsp;□ 개선 필요성</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 이용객 이동 패턴 분석을 기반으로 환승 동선을 재구성하고 스마트 안내 체계를 구축할 필요</p>


<h3>2. 사업 필요성</h3>
<p><strong>&nbsp;&nbsp;□ 교통 운영 효율 개선</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 환승 흐름 분석을 통한 공간 재배치로 대중교통 이용 효율 향상</p>
<p><strong>&nbsp;&nbsp;□ 시민 편의 향상</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 실시간 안내 정보를 제공하여 이용객 길찾기 불편 해소</p>
<p><strong>&nbsp;&nbsp;□ 안전한 환승 환경 조성</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 혼잡 구간 개선을 통한 이용객 안전 확보 및 사고 예방</p>',

'<h2>Ⅲ. 사업 목표</h2>
<p><strong>&nbsp;&nbsp;□ 최종 목표</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 서울역 환승센터 이용객 이동 효율 개선 및 스마트 환승 환경 구축</p>
<p></p>
<p><strong>&nbsp;&nbsp;□ 세부 목표</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;1. 목표: 환승 동선 개선</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;성과지표: 주요 혼잡 구간 3개소 동선 재설계 및 이동 체계 개선</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;2. 목표: 스마트 안내 시스템 구축</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;성과지표: 디지털 안내 시스템 20개소 설치 및 실시간 정보 제공 체계 구축</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;3. 목표: 이용객 편의 향상</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;성과지표: 평균 환승 이동시간 기존 대비 20% 단축</p>',

'<h2>Ⅳ. 세부 추진 계획</h2>
<h3>1. 사업 내용</h3>
<p>&nbsp;&nbsp;○ 과업 1: 서울역 환승 공간 이용 현황 조사 및 개선안 수립</p>
<p>&nbsp;&nbsp;○ 과업 2: 주요 환승 동선 재설계 및 안내 체계 개선</p>
<p>&nbsp;&nbsp;○ 과업 3: 스마트 디지털 안내 시스템 구축</p>
<p>&nbsp;&nbsp;○ 과업 4: 시범 운영 및 이용객 의견 반영</p>


<h3>2. 세부 실행 계획</h3>
<p><strong>&nbsp;&nbsp;가. 환승 동선 분석 및 개선</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 주요 내용</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- KTX, 지하철, 버스 간 주요 이동 경로 분석 및 혼잡 구간 개선</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 추진 방법</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 이용객 이동 데이터 분석 및 현장 조사를 통한 개선 방향 도출</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 산출물</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 환승 동선 개선 설계안 및 운영 개선 보고서</p>
<p></p>
<p><strong>&nbsp;&nbsp;나. 스마트 안내 시스템 구축</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 주요 내용</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 환승 경로, 출입구 위치, 교통 정보를 제공하는 디지털 안내판 설치</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 추진 방법</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 관계 기관 협의를 통한 설치 위치 선정 및 시스템 구축</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 산출물</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 스마트 안내 시스템 설치 결과 보고서</p>
<p></p>
<p><strong>&nbsp;&nbsp;다. 운영 계획</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 운영 방법</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 안내 시스템 정보 업데이트 및 이용 현황 지속 모니터링</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 담당자</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 교통부 김도현 부장</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 관리 체계</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 코레일 및 서울교통공사 협업 체계 운영</p>',

'<h2>Ⅴ. 추진 일정</h2>
<p><strong>&nbsp;&nbsp;사업 일정</strong> (추진 단계별 일정을 월 단위로 작성)</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 현황 조사 및 사업 계획 수립: 2026년 2월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 환승 동선 분석 및 설계: 2026년 3월 ~ 4월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 스마트 안내 시스템 구축: 2026년 4월 ~ 6월</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 시범 운영 및 개선 사항 반영: 2026년 7월</p>
<p></p>
<p><em>※ 서울역 이용객 불편 최소화를 위해 단계별 공사 및 운영 적용</em></p>',

'<h2>Ⅵ. 사업 추진 체계</h2>
<p><strong>&nbsp;&nbsp;총괄 책임자</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 이름: 김도현</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 직책: 교통부 부장</p>
<p></p>
<p><strong>&nbsp;&nbsp;사업 담당 부서</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 부서명: 교통부</p>
<p></p>
<p><strong>&nbsp;&nbsp;협력 기관</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 운영 협력: 코레일</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 시설 협력: 서울교통공사</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 행정 협력: 용산구청</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;□ 시공 담당: 공개입찰 선정 업체</p>',

'<h2>Ⅶ. 예산 계획</h2>
<p><strong>&nbsp;&nbsp;예산 내역</strong> (단위: 천원)</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 인건비:&nbsp;50,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 사업 관리 및 설계·감리 담당 인력 운영 비용</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 환승 시설 개선비:&nbsp;400,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 환승 동선 재설계 및 이동 안내 시설 개선</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 스마트 안내 시스템 구축비:&nbsp;220,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 디지털 안내판 20개소 설치 및 시스템 구축</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;○ 기타 운영비:&nbsp;30,000천원</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;산출 근거: 홍보, 시범 운영 및 예비 비용</p>
<p></p>
<p><strong>&nbsp;&nbsp;합계:</strong>&nbsp;&nbsp;700,000천원 (국비 400,000천원, 시비 300,000천원)</p>',

'<h2>Ⅷ. 기대 효과</h2>

<h3>1. 정량적 효과</h3>
<p>&nbsp;&nbsp;□ 환승 이동시간 개선</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;기존: 평균 환승 이동시간 약 25분</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;개선 목표: 평균 20분 이하로 단축</p>
<p></p>
<p>&nbsp;&nbsp;□ 길찾기 관련 민원 감소</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;기존: 연간 안내 관련 민원 약 1,200건</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;개선 목표: 연간 민원 600건 이하 관리</p>
<p></p>
<p>&nbsp;&nbsp;□ 환승 공간 혼잡 개선</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;기존: 출퇴근 시간대 주요 구간 혼잡 지속</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;개선 목표: 주요 병목 구간 혼잡도 30% 개선</p>

<h3>2. 정성적 효과</h3>
<p>&nbsp;&nbsp;□ 이용객 편의 향상</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 스마트 안내 시스템을 통한 직관적인 환승 정보 제공</p>
<p></p>
<p>&nbsp;&nbsp;□ 안전한 환승 환경 조성</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 혼잡 구간 동선 분리를 통한 보행 안전 확보</p>
<p></p>
<p>&nbsp;&nbsp;□ 광역 교통 거점 기능 강화</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 서울역 환승 편의 개선을 통한 대표 교통 거점 역할 강화</p>',

'<h2>Ⅸ. 사후 관리 계획</h2>
<p><strong>&nbsp;&nbsp;운영기간</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 준공 후 지속 운영 및 정기적인 성과 분석 실시</p>
<p><strong>&nbsp;&nbsp;관리부서</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 교통부 (코레일 및 서울교통공사 협력 운영)</p>
<p><strong>&nbsp;&nbsp;유지보수 방법</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 스마트 안내 시스템 월 1회 점검 및 정보 업데이트</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 환승 시설물 연 2회 정기 점검 실시</p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 이용객 의견 및 민원 분석을 통한 운영 개선</p>
<p><strong>&nbsp;&nbsp;개선 계획</strong></p>
<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- 사업 시행 1년 후 이용 데이터 분석을 통해 추가 동선 개선 및 시스템 고도화 검토</p>',
'2026-07-31 00:00:00'
);
SET @proj_seoulstation = LAST_INSERT_ID();
-- 사업 시드데이터 4 서울역 환승센터 혼잡 개선 사업 끝

-- ============================================================
-- 사업멤버 시드데이터
-- (원본은 project_id를 101~104로 하드코딩했으나, 새 DB에 배포 시 실제 AUTO_INCREMENT
--  값과 어긋나므로 위에서 캡처한 세션 변수를 사용한다)
-- ============================================================
INSERT INTO PROJECT_MEMBER (
    project_id,
    user_id,
    role_code
)
VALUES
(@proj_hangang,      '20260101', '01'),
(@proj_hangang,      '20260102', '02'),
(@proj_hangang,      '20260106', '02'),

(@proj_simya,        '20260102', '01'),
(@proj_simya,        '20260106', '02'),
(@proj_simya,        '20260107', '02'),

(@proj_gwanghwamun,  '20260106', '01'),
(@proj_gwanghwamun,  '20260101', '02'),
(@proj_gwanghwamun,  '20260102', '02'),

(@proj_seoulstation, '20260107', '01'),
(@proj_seoulstation, '20260102', '02'),
(@proj_seoulstation, '20260106', '02');
