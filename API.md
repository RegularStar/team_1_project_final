# SkillBridge API Guide

> 기본 도메인  
> - 로컬(Compose): `http://localhost:8080/api/`  
> - 프로덕션: `https://skillbridge.app/api/`

모든 API는 JSON 응답을 기본으로 하며, 인증이 필요한 엔드포인트는 `Authorization: Bearer <access_token>` 헤더를 요구합니다.

---

## 인증 & 계정

| 기능 | 메서드 | 엔드포인트 | 요청 예시 | 비고 |
| --- | --- | --- | --- | --- |
| JWT 발급 | POST | `/users/token/` | `{ "username": "tester", "password": "p@ssw0rd" }` | 응답: `{"access": "...", "refresh": "..."}` |
| JWT 갱신 | POST | `/users/token/refresh/` | `{ "refresh": "<refresh_token>" }` | 새로운 access 토큰 발급 |
| 회원가입 | POST | `/users/register/` | `{ "username": "tester", "email": "test@example.com", "password": "p@ssw0rd!!", "name": "홍길동", "phone": "010-0000-0000" }` | 누구나 호출 가능 |
| 내 정보 | GET | `/users/me/` | 헤더에 Bearer 토큰 | 본인 프로필 확인 |

---

## 자격증 & 태그

### 태그
| 기능 | 메서드 | 엔드포인트 | 요청 예시 | 비고 |
| --- | --- | --- | --- | --- |
| 태그 목록 | GET | `/tags/` | `/tags/?search=데이터&page=1&page_size=30` | 검색/정렬 지원 |
| 태그 생성 | POST | `/tags/` | `{ "name": "AI" }` | 관리자만 |
| 태그 수정 | PATCH | `/tags/{id}/` | `{ "name": "머신러닝" }` | 관리자만 |
| 태그 삭제 | DELETE | `/tags/{id}/` | - | 관리자만 |

**태그 일괄 업로드 (관리자)**  
`POST /tags/upload/tags/` (`multipart/form-data`)  
- 필드: `file=@tags.xlsx`  
- 쿼리 파라미터: `?sheet=<시트명>` (없으면 첫 시트)  
- 필수 컬럼: `name` (옵션: `id`)  
- 응답: `{ "created": 3, "updated": 1, "errors": [] }` (에러 존재 시 `HTTP 207`)

### 자격증
| 기능 | 메서드 | 엔드포인트 | 요청 예시 | 비고 |
| --- | --- | --- | --- | --- |
| 자격증 목록 | GET | `/certificates/` | `/certificates/?tags=AI,보안&type=국가공인&ordering=-total_applicants` | 태그/종류 필터 지원 |
| 자격증 상세 | GET | `/certificates/{id}/` | `/certificates/101/` | 응답에 `tags`(PK 리스트) 포함 |
| 자격증 생성 | POST | `/certificates/` | `{ "name": "...", "overview": "...", ... }` | 관리자만 |
| 자격증 수정 | PATCH | `/certificates/{id}/` | `{ "overview": "업데이트" }` | 관리자만 |
| 자격증 삭제 | DELETE | `/certificates/{id}/` | - | 관리자만 |

**자격증-태그 매핑 일괄 업로드 (관리자)**  
`POST /certificates/upload/certificate-tags/` (`multipart/form-data`)  
- 필수 컬럼: `certificate_id` 또는 `certificate_name`, 그리고 `tags`(이름 목록) 또는 `tag_ids`  
- 태그가 없으면 해당 자격증의 태그를 초기화합니다.  
- 응답: `{ "updated_certificates": 12, "cleared_certificates": 2, "created_tags": 4, "errors": [] }`

**자격증 마스터 업로드 (관리자)**  
`POST /certificates/upload/certificates/` (`multipart/form-data`)  
- 필수 컬럼: `id`, `name`  
- 옵션: `overview`, `job_roles`, `exam_method`, `eligibility`, `authority`, `type`, `homepage`, `rating`, `expected_duration`, `expected_duration_major`, `tags`  
- 존재하는 `id`는 업데이트, 없으면 동일 PK로 생성합니다.

### 단계 & 통계
| 기능 | 메서드 | 엔드포인트 | 요청 예시 | 비고 |
| --- | --- | --- | --- | --- |
| 단계 목록 | GET | `/phases/?certificate={id}` | `/phases/?certificate=101` | |
| 단계 생성 | POST | `/phases/` | `{ "certificate": 101, "phase_name": "필기", "phase_type": "객관식" }` | 관리자만 |
| 단계 수정 | PATCH | `/phases/{id}/` | `{ "phase_type": "실기" }` | 관리자만 |
| 단계 삭제 | DELETE | `/phases/{id}/` | - | 관리자만 |

| 기능 | 메서드 | 엔드포인트 | 요청 예시 | 비고 |
| --- | --- | --- | --- | --- |
| 통계 목록 | GET | `/statistics/?certificate={id}` | `/statistics/?certificate=101&year=2024` | |
| 통계 생성 | POST | `/statistics/` | `{ "certificate": 101, "exam_type": "필기", "year": "2024", "session": 1, "registered": 120, "applicants": 110, "passers": 70, "pass_rate": 63.6 }` | 관리자만 |
| 통계 수정 | PATCH | `/statistics/{id}/` | `{ "pass_rate": 64.0 }` | 관리자만 |
| 통계 삭제 | DELETE | `/statistics/{id}/` | - | 관리자만 |

**단계 일괄 업로드 (관리자)**  
`POST /phases/upload/phases/` (`multipart/form-data`)  
- 필수: `phase_name`, 자격증 식별(`certificate_id` 혹은 `certificate_name`)  
- 옵션: `phase_type`, `id` (존재 시 업데이트)  
- 응답: `{ "created": 5, "updated": 3 }`

**통계 일괄 업로드 (관리자)**  
`POST /statistics/upload/statistics/` (`multipart/form-data`)  
- 필수: `certificate_id` 또는 `certificate_name`, `exam_type`, `year`  
- `pass_rate`는 `0~1` 또는 `0~100` 모두 허용 (내부에서 %)로 변환  
- 응답: `{ "created": 7, "updated": 2 }`

### 사용자 관심 태그 & 취득 자격증
| 기능 | 메서드 | 엔드포인트 | 요청 예시 | 비고 |
| --- | --- | --- | --- | --- |
| 내 태그 목록 | GET | `/user-tags/` | 헤더에 Bearer 토큰 | 본인 데이터만 |
| 태그 추가 | POST | `/user-tags/` | `{ "tag": 3 }` | 중복 추가 시 자동 무시 |
| 태그 삭제 | DELETE | `/user-tags/{id}/` | - | 본인 레코드만 |

| 기능 | 메서드 | 엔드포인트 | 요청 예시 | 비고 |
| --- | --- | --- | --- | --- |
| 취득 자격증 목록 | GET | `/user-certificates/` | 헤더에 Bearer 토큰 | `status_display`, `evidence_url` 포함 |
| 취득 자격증 추가 | POST | `/user-certificates/` | `multipart/form-data` → `certificate=101`, `acquired_at=2024-01-01`, `evidence=@result.pdf` | 생성 시 상태는 `pending` |
| 취득 자격증 수정 | PATCH | `/user-certificates/{id}/` | `multipart/form-data` → `acquired_at=2024-02-01` | 수정 시 상태가 다시 `pending` |
| 취득 자격증 삭제 | DELETE | `/user-certificates/{id}/` | - | 본인 레코드만 |

---

## 커뮤니티

| 기능 | 메서드 | 엔드포인트 | 요청 예시 | 비고 |
| --- | --- | --- | --- | --- |
| 게시글 목록/작성 | GET/POST | `/posts/` | POST `{ "title": "합격 후기", "body": "내용", "certificate": 101 }` | 작성은 로그인 필요 |
| 게시글 상세/수정/삭제 | GET/PATCH/DELETE | `/posts/{id}/` | PATCH `{ "body": "수정 내용" }` | 작성자 또는 관리자 |
| 좋아요 추가 | POST | `/posts/{id}/like/` | - | 로그인 필요, 중복 시 200 |
| 좋아요 취소 | DELETE | `/posts/{id}/unlike/` | - | 로그인 필요 |
| 댓글 목록/작성 | GET/POST | `/posts/{post_id}/comments/` | POST `{ "body": "좋은 정보 감사합니다" }` | 로그인 필요 |

응답에는 `comment_count`, `like_count`, `user` 정보가 포함됩니다.

---

## 평점

| 기능 | 메서드 | 엔드포인트 | 요청 예시 | 비고 |
| --- | --- | --- | --- | --- |
| 평점 목록/작성 | GET/POST | `/ratings/` | POST `{ "certificate": 101, "rating": 8, "content": "실무에 도움 됨" }` | 1인 1자격증 1개, 작성은 로그인 필요 |
| 평점 상세/수정/삭제 | GET/PATCH/DELETE | `/ratings/{id}/` | PATCH `{ "rating": 7 }` | 작성자 또는 관리자 |

---

## AI 서비스

| 기능 | 메서드 | 엔드포인트 | 요청 예시 | 비고 |
| --- | --- | --- | --- | --- |
| AI 상담 | POST | `/ai/chat/` | `{ "message": "데이터 분석 자격증 추천해줘", "history": [{ "role": "user", "content": "이전에 추천받은 내용 있어?" }] }` | 응답: `{ "reply": "...", "history": [...], "metadata": {...} }` |
| 자격증 추천 | POST | `/ai/job-certificates/` | `multipart/form-data` → `content="보안 직무 설명"`, `max_results=5` 또는 `image=@job.png` | 텍스트/이미지 중 하나 필수 |
| OCR 추출 | POST | `/ai/job-certificates/ocr/` | `multipart/form-data` → `image=@job.png`, `lang=kor+eng` | 추출 텍스트 반환 |
| 태그 제안 | POST | `/ai/job-certificates/feedback/` | `{ "tag_name": "클라우드", "certificate_ids": [101, 102], "job_excerpt": "요약" }` | 제안된 태그를 자격증에 연결 |
| 운영 문의 | POST | `/ai/support-inquiries/` | `{ "intent": "tag_request", "summary": "새 자격증 추가", "detail": "설명", "conversation": [{"role": "user","content": "..."}, ...] }` | `intent` 값: `tag_request`, `info_update`, `stats_request`, `bug_report`, `general_help` |

모든 AI 엔드포인트는 JWT 인증이 필요하며, 요청이 유효하지 않을 경우 `HTTP 400`과 상세 오류 메시지를 반환합니다.

---

## 기타

| 기능 | 메서드 | 엔드포인트 | 비고 |
| --- | --- | --- | --- |
| 헬스 체크 | GET | `/healthz` | `{ "status": "ok" }` 반환 |
| Prometheus 지표 | GET | `/metrics/` | Prometheus 포맷, 인증 없음 |

---

## 업로드 공통 규칙
- 모든 엑셀 업로드는 `multipart/form-data`로 `file` 필드를 사용합니다.
- `sheet` 쿼리 파라미터를 지정하면 해당 시트를, 지정하지 않으면 첫 번째 시트를 사용합니다.
- 업로드 응답은 성공 시 `HTTP 200`, 부분 성공 시 `HTTP 207 Multi-Status`를 돌려주며, `errors` 배열에 행 번호와 원인을 포함합니다.
- `tags` 열은 콤마, 세미콜론, 줄바꿈, 슬래시로 구분된 값들을 지원합니다.

---

## 요청 헤더 요약
- 기본: `Content-Type: application/json`
- 파일 업로드: `Content-Type: multipart/form-data`
- 인증 필요: `Authorization: Bearer <JWT access token>`

필요한 경우 `Accept: application/json` 헤더를 추가하는 것을 권장합니다.
