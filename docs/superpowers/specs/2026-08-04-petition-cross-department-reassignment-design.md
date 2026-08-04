# 민원 담당자 타부서 이관 허용 Design

**Goal:** 오분류된 민원의 담당자를 변경할 때 같은 부서 내 인원뿐 아니라 다른 부서 직원에게도 재배정할 수 있게 하고, 그 경우 민원의 소속 부서와 업무분류를 함께 정리한다.

## 배경

현재 민원 상세 화면(`Detail_petition.jsx`)의 "담당자 변경" 기능은 `EmployeeSearchModal`을 `forceDeptScope={true}`로 열어서, 같은 부서 소속 직원으로만 재배정할 수 있다. 하지만 부서 자동분류(`classify-department`)가 오분류될 경우, 현재 방식으로는 잘못 배정된 부서 내에서만 담당자를 바꿀 수 있어 문제를 근본적으로 해결할 수 없다. 오분류를 발견한 담당자가 올바른 부서의 직원에게 직접 이관할 수 있어야 한다.

백엔드 API(`PUT /petitions/{petitionId}/temp-save`)는 이미 담당자를 임의의 `user_id`로 지정할 수 있게 열려 있다 — 부서 제한은 프론트엔드에서만 걸려 있다. `EmployeeSearchModal`은 이미 "범위: 같은 과" / "범위: 전체 부서" 토글과 부서별 드롭다운 필터를 갖추고 있고, 다른 화면(예: 채팅 상대 선택)에서 `forceDeptScope` 없이 이미 사용 중이다.

## 아키텍처

### 프론트엔드 변경

`ieum_frontend/src/pages/Petition/Detail_petition.jsx`에서 `EmployeeSearchModal` 호출 시 전달하는 `forceDeptScope={true}`를 제거한다. 이 prop이 빠지면:
- 모달 하단에 "범위: 같은 과" / "범위: 전체 부서" 토글 버튼이 노출된다.
- "범위: 전체 부서" 선택 시 부서 드롭다운 필터가 노출되어 원하는 부서의 직원을 검색할 수 있다.
- 기존에 `forceDeptScope`일 때만 보이던 "담당자/조직 변경은 같은 과 내에서만 가능" 안내 배지는 자동으로 사라진다 (해당 배지는 `forceDeptScope` 조건부 렌더링이라 추가 코드 불필요).

이 외 `EmployeeSearchModal.jsx` 자체는 수정하지 않는다 — 이미 필요한 기능(전체 부서 검색, 부서 필터)을 다 갖추고 있다.

### 백엔드 변경

`ieum_backend/app/api/routers/petition.py`의 `temp_save_petition` 함수(`PUT /petitions/{complaintId}/temp-save`) 중 담당자 변경 처리 블록을 수정한다.

현재 로직 (담당자 신규 지정/변경 시):
```python
else: # 담당자 신규 지정 또는 변경
    new_assignee = db.query(User).filter(User.user_id == new_assignee_id_str).first()
    if not new_assignee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="새로 지정할 담당자를 찾을 수 없습니다."
        )
    petition.assignee_user_id = new_assignee_id_str
    to_user_id = new_assignee_id_str
```

변경 후:
```python
else: # 담당자 신규 지정 또는 변경
    new_assignee = db.query(User).filter(User.user_id == new_assignee_id_str).first()
    if not new_assignee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="새로 지정할 담당자를 찾을 수 없습니다."
        )

    # 타 부서 직원으로 재배정되는 경우, 민원의 소속 부서도 함께 이동시키고
    # 예전 부서 기준으로 분류되어 있던 task_id는 새 부서에서 의미가 없으므로 초기화한다.
    if new_assignee.department_code != petition.department_code:
        petition.department_code = new_assignee.department_code
        petition.task_id = None

    petition.assignee_user_id = new_assignee_id_str
    to_user_id = new_assignee_id_str
```

담당자 지정 해제(`new_assignee_id_str == ""`) 분기는 수정하지 않는다 — 담당자를 해제해도 민원의 소속 부서는 그대로 유지된다.

## 데이터 흐름

1. 담당자가 민원 상세 화면에서 "담당자 변경" 클릭 → 모달에서 "범위: 전체 부서" 선택 → 부서 필터로 올바른 부서를 고르고 직원 선택
2. 기존 확인 다이얼로그(`window.confirm`) 그대로 노출 — 문구 변경 없음
3. `PUT /petitions/{id}/temp-save` 호출:
   - 새 담당자 조회 (기존과 동일)
   - 새 담당자의 `department_code`가 민원의 현재 `department_code`와 다르면 `petition.department_code`를 새 담당자 부서로 갱신하고 `petition.task_id`를 `None`으로 초기화
   - 같은 부서 내 변경이면 `department_code`/`task_id`는 건드리지 않음 (기존 동작 유지)
   - `petition.assignee_user_id` 갱신 및 `PetitionAssigneeHistory` 이력 기록은 기존 로직 그대로

## 권한

현재 담당자만 담당자 변경(타 부서 포함)을 수행할 수 있다 — 기존 `is_current_assignee` 체크를 그대로 사용하며 추가 권한 체크는 두지 않는다.

## 에러 처리

기존과 동일하다 — 담당자를 찾지 못하면 400, 현재 담당자가 아니면 403. 부서 이동으로 인해 새로 추가되는 에러 케이스는 없다.

## 테스트

- 같은 부서 내 담당자 변경 시 `department_code`/`task_id`가 변하지 않는지 확인
- 다른 부서 담당자로 변경 시 `department_code`가 새 담당자 부서로 바뀌고 `task_id`가 `None`이 되는지 확인
- 담당자 해제(`assigneeUserId=""`) 시 `department_code`가 그대로인지 확인
- 프론트엔드: `Detail_petition.jsx`의 담당자 변경 모달에서 "범위: 전체 부서" 토글과 부서 드롭다운이 정상 노출되는지 확인
