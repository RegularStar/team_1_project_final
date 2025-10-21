# SkillBridge API Guide

## 인증
| 기능 | 메서드 | 엔드포인트 | 예시 Body | 비고 |
| --- | --- | --- | --- | --- |
| JWT 발급 | POST | `/api/users/token/` | `{ "username": "admin", "password": "p@ssw0rd" }` | 응답: access/refresh |
| JWT 갱신 | POST | `/api/users/token/refresh/` | `{ "refresh": "<refresh-token>" }` | |
| 내 정보 | GET | `/api/users/me/` | 헤더: `Authorization: Bearer <token>` | |

## 사용자
| 기능 | 메서드 | 엔드포인트 | 예시 Body | 비고 |
| --- | --- | --- | --- | --- |
| 회원가입 | POST | `/api/users/register/` | `{ "username": "tester", "email": "test@example.com", "password": "p@ssw0rd!!", "name": "홍길동", "phone": "010-0000-0000" }` | |

## 자격증
| 기능 | 메서드 | 엔드포인트 | 예시 | 비고 |
| --- | --- | --- | --- | --- |
| 목록 조회 | GET | `/api/certificates/?ordering=-total_applicants&type=국가공인&tags=AI` | - | `ordering`: name/total_applicants/avg_difficulty/type |
| 상세 조회 | GET | `/api/certificates/555/` | - | |
| 생성 | POST | `/api/certificates/` | `{ "name": "정보처리기사", "overview": "설명" }` | 관리자 |
| 수정 | PATCH | `/api/certificates/555/` | `{ "overview": "업데이트" }` | 관리자 |
| 삭제 | DELETE | `/api/certificates/555/` | - | 관리자 |
| 태그 목록 | GET | `/api/tags/` | - | |
| 태그 생성 | POST | `/api/tags/` | `{ "name": "AI" }` | 관리자 |
| 단계 목록 | GET | `/api/phases/?certificate=555` | - | |
| 통계 목록 | GET | `/api/statistics/?certificate=555` | - | |

### 엑셀 업로드 (관리자 전용)
| 대상 | 엔드포인트 | 필수 헤더 | 예시 행 | 비고 |
| --- | --- | --- | --- | --- |
| 자격증 | `POST /api/certificates/upload/certificates/?sheet=Certificates` | `id`, `name` | `101, 정보처리기사, ..., tags=IT,국가` | `multipart/form-data` / `file=@certs.xlsx` / 응답: `{created, updated, errors}` (에러 시 207) |
| 단계 | `POST /api/certificates/upload/phases/` | `phase_name` + (`id` / `certificate_id`/`certificate_name`) | `901, 101, , 필기, 필기` | FK는 `certificate_id` 우선 |
| 통계 | `POST /api/statistics/upload/statistics/` | `year` + (`id` / `certificate_id`/`certificate_name`) | `1201, 101, , 실기, 2024, 1, 120, 110, 70, 0.75` | `registered` 오타 `registerd`도 허용 |

## 사용자 관심 태그 / 취득 자격증
| 기능 | 메서드 | 엔드포인트 | 예시 | 비고 |
| --- | --- | --- | --- | --- |
| 내 태그 목록 | GET | `/api/user-tags/` | 헤더: 토큰 | |
| 태그 추가 | POST | `/api/user-tags/` | `{ "tag": 3 }` | 사용자 ID 자동 주입 |
| 취득 자격증 목록 | GET | `/api/user-certificates/` | 헤더: 토큰 | |
| 취득 자격증 추가 | POST | `/api/user-certificates/` | `{ "certificate": 101, "acquired_at": "2024-01-01" }` | |

## 커뮤니티
| 기능 | 메서드 | 엔드포인트 | 예시 | 비고 |
| --- | --- | --- | --- | --- |
| 게시글 목록/생성 | GET/POST | `/api/posts/` | `POST` Body: `{ "title": "합격 후기", "body": "내용", "certificate": 101 }` | POST는 로그인 필요 |
| 게시글 상세/수정/삭제 | GET/PATCH/DELETE | `/api/posts/{id}/` | PATCH Body: `{ "body": "수정 내용" }` | 작성자 또는 관리자 |
| 댓글 목록/생성 | GET/POST | `/api/posts/{id}/comments/` | `{ "body": "좋은 정보 감사합니다" }` | POST는 로그인 필요 |
| 좋아요 추가 | POST | `/api/posts/{id}/like/` | - | |
| 좋아요 취소 | DELETE | `/api/posts/{id}/unlike/` | - | |

## 평점
| 기능 | 메서드 | 엔드포인트 | 예시 | 비고 |
| --- | --- | --- | --- | --- |
| 평점 목록/생성 | GET/POST | `/api/ratings/` | `{ "certificate": 101, "rating": 5, "content": "좋아요" }` | POST는 로그인 필요, 1인당 1개 |
| 평점 상세/수정/삭제 | GET/PATCH/DELETE | `/api/ratings/{id}/` | PATCH Body: `{ "rating": 4 }` | 작성자 or 관리자 |

## AI
| 기능 | 메서드 | 엔드포인트 | 예시 Body | 비고 |
| --- | --- | --- | --- | --- |
| GPT 상담 | POST | `/api/ai/chat/` | `{ "message": "데이터 분석 자격증 추천해줘", "history": [{"role": "user", "content": "AI 관련 자격증을 찾는 중"}] }` | 헤더: 토큰, 응답 `{ "reply": "...", "history": [...] }` |
<<<<<<< HEAD
| 채용공고 기반 추천 | POST | `/api/ai/job-certificates/` | `{ "url": "https://jobs.example.com/123", "content": "(선택) 공고 본문", "max_results": 3 }` | 공고 본문을 크롤링하거나 제공, 응답 `{ "job_excerpt": "...", "recommendations": [{"certificate": {...}, "reasons": [...]}] }` |
=======
| AI 자격증 추천 | POST | `/api/ai/job-certificates/` | `{ "content": "지원하려는 직무와 목표를 소개합니다.", "max_results": 5 }` | 텍스트 또는 이미지로 입력 정보를 제공하면 맞춤 자격증 추천과 핵심 키워드가 반환됩니다. |
>>>>>>> seil2

## 기타
| 기능 | 메서드 | 엔드포인트 | 예시 | 비고 |
| --- | --- | --- | --- | --- |
| 헬스체크 | GET | `/healthz` | - | |

### 참고
- 모든 엑셀 업로드는 관리자가 `multipart/form-data`로 `file` 필드에 `.xlsx`를 첨부해야 합니다.
- 업로드 응답 예시: `HTTP 200 { "created": 3, "updated": 1, "errors": [] }`, 에러 발생 시 `HTTP 207`과 `errors` 배열에 상세 메시지 제공.
- `pass_rate` 값은 `0~1` 또는 `0~100` 범위를 허용하며, 내부적으로 퍼센트(소수 1자리)로 저장됩니다.
