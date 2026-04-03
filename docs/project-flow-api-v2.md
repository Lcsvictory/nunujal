# Project Flow API V2

로그인 이후 프로젝트 생성, 참여 요청, 승인 흐름을 위한 REST API 초안이다.

## 1. 프로젝트 목록

### `GET /api/projects`
- 목적: 현재 로그인 사용자가 참여 중인 프로젝트 목록 조회
- 응답 핵심 필드:
  - `id`
  - `title`
  - `status`
  - `project_role`
  - `position_label`
  - `join_policy`

### `POST /api/projects`
- 목적: 새 프로젝트 생성
- 요청 핵심 필드:
  - `title`
  - `description`
  - `start_date`
  - `end_date`
  - `join_policy`
- 서버 처리:
  - `Project` 생성
  - `join_code` 발급
  - 생성자를 `ProjectMember(LEADER)`로 추가

### `GET /api/projects/{projectId}`
- 목적: 프로젝트 상세 조회

### `PATCH /api/projects/{projectId}`
- 목적: 프로젝트 기본 정보 수정
- 수정 가능 필드:
  - `title`
  - `description`
  - `start_date`
  - `end_date`
  - `status`
  - `join_policy`
  - `join_code_active`
  - `join_code_expires_at`

## 2. 초대코드

### `GET /api/projects/join-preview/{joinCode}`
- 목적: 초대코드 유효성 확인 및 최소 프로젝트 정보 조회
- 응답 핵심 필드:
  - `project_id`
  - `title`
  - `leader_name`
  - `member_count`
  - `join_policy`
  - `join_code_active`

### `POST /api/projects/{projectId}/join-code/regenerate`
- 목적: 팀장이 초대코드를 재발급
- 서버 처리:
  - 새 `join_code` 생성
  - `join_code_created_at` 갱신

## 3. 참여 요청

### `POST /api/project-join-requests`
- 목적: 로그인 사용자가 초대코드로 프로젝트 참여 요청 생성
- 요청 핵심 필드:
  - `join_code`
  - `request_message`
  - `requested_position_label`
- 서버 처리:
  - 코드 유효성 확인
  - 중복 참여 여부 확인
  - `join_policy`가 `AUTO_APPROVE`면 즉시 `ProjectMember` 생성
  - `LEADER_APPROVE`면 `ProjectJoinRequest(PENDING)` 생성

### `GET /api/projects/{projectId}/join-requests`
- 목적: 팀장이 프로젝트 참여 요청 목록 조회
- 응답 핵심 필드:
  - `id`
  - `requester_user`
  - `request_message`
  - `requested_position_label`
  - `request_status`
  - `created_at`

### `GET /api/project-join-requests/me`
- 목적: 현재 로그인 사용자의 참여 요청 목록 조회

### `PATCH /api/projects/{projectId}/join-requests/{requestId}`
- 목적: 팀장이 참여 요청 승인/거절
- 요청 핵심 필드:
  - `request_status`
  - `reviewed_project_role`
  - `reviewed_position_label`
  - `review_note`
- 서버 처리:
  - 승인 시 `ProjectMember` 생성
  - 거절 시 `ProjectJoinRequest` 상태만 변경

## 4. 프로젝트 멤버

### `GET /api/projects/{projectId}/members`
- 목적: 프로젝트 멤버 목록 조회

### `PATCH /api/projects/{projectId}/members/{memberId}`
- 목적: 팀장이 프로젝트 멤버 역할/포지션 수정
- 수정 가능 필드:
  - `project_role`
  - `position_label`
  - `memo`

### `DELETE /api/projects/{projectId}/members/{memberId}`
- 목적: 프로젝트 탈퇴 또는 팀장에 의한 제거
- 서버 처리:
  - 실제 삭제 대신 `left_at` 설정

## 5. 비고

- 메일 발송은 후순위 기능이다.
- 메일을 붙일 때는 아래 이벤트를 기준으로 연결한다.
  - `ProjectJoinRequest` 생성
  - `ProjectJoinRequest` 승인
  - `ProjectJoinRequest` 거절
- 실시간 확인은 우선 polling으로 처리하고, 필요할 때 SSE 또는 WebSocket으로 확장한다.
