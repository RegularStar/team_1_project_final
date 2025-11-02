# SkillBridge
AI 기반 자격증 추천 & 커리어 커뮤니티 플랫폼

> SkillBridge는 Django REST Framework와 LangChain을 기반으로 한 자격증 추천·커뮤니티 서비스입니다. 텍스트 또는 이미지로 전달된 직무 정보를 분석해 맞춤형 자격증을 제안하고, 커뮤니티·리뷰 데이터를 통합해 커리어 의사결정을 돕습니다.

## 목차
- [프로젝트 개요](#프로젝트-개요)
- [주요 기능](#주요-기능)
- [빠른 시작](#빠른-시작)
- [아키텍처](#아키텍처)
- [AI 처리 흐름](#ai-처리-흐름)
- [캐싱 & 성능 메모](#캐싱--성능-메모)
- [데이터 & RAG 파이프라인](#데이터--rag-파이프라인)
- [운영 & DevOps](#운영--devops)
- [테스트 & 품질](#테스트--품질)
- [배포 정보](#배포-정보)
- [추가 문서](#추가-문서)
- [License](#license)

## 프로젝트 개요
- **프로젝트명**: SkillBridge  
- **프로젝트 설명**: 텍스트·이미지 기반 직무 분석과 LangChain RAG 검색을 결합해 맞춤형 자격증 추천과 커뮤니티 기능을 제공하는 AI 커리어 플랫폼입니다.
- **예시 시나리오**: 채용 공고를 업로드하면 LangChain이 핵심 역량을 추출하고, Django API가 자격증 DB와 매칭해 추천 목록을 반환합니다.
- **핵심 기술 요약**: Django 5, DRF, LangChain, OpenAI GPT-4o-mini, MySQL, 선택적 Redis 캐시, Docker.
- **팀 구성**:

  | 이름 | 역할 | 담당 |
  | --- | --- | --- |
  | 한세일 | PM & Frontend & Backend | 프로젝트 기획, DB 설계(ERD), API 설계, 비즈니스 로직 구현, 성능 개선(Redis), 프론트엔드 전담 |
  | 정규성 | Backend | API 설계, 비즈니스 로직 구현, 모니터링 및 배포 전담, 인증 및 권한 관리 |
  | 김선우 | Data | 자격증 데이터 수집 및 관리 |

## 주요 기능
- **AI 자격증 추천**: LangChain + OpenAI로 추출한 키워드를 기반으로 자격증 모델을 매칭하여 추천합니다.
- **AI 챗봇 질의응답**: `/api/ai/chat/`에서 JWT 인증 후 사용할 수 있는 대화형 상담 API를 제공합니다.
- **OCR 기반 직무 분석**: 이미지나 PDF 스크린샷에서 텍스트를 추출해 직무 정보를 파악합니다.
- **자격증·커뮤니티 허브**: 자격증 상세, 후기, 평점, 커뮤니티 게시판, 댓글, 좋아요, 유저 랭킹 등을 제공합니다.
- **운영자 기능**: 업로드 허브, 문의 처리, 자격증 심사 등 운영 워크플로우를 위한 관리자 뷰가 포함되어 있습니다.

## 빠른 시작
```bash
# 1. 저장소 클론
git clone https://github.com/RegularStar/team_1_project_final.git
cd team_1_project_final

# 2. 환경 변수 설정 (.env 예시 제공)
cp .env.example .env
# DB, OpenAI 키, (선택) REDIS_URL 등을 채워주세요.

# 3. Docker 기반 실행
docker-compose up --build

# 4. 브라우저 접속
http://localhost:8080
```
- `web` 컨테이너는 내부 8000 포트를 호스트 8080으로 노출합니다.
- entrypoint 스크립트는 DB 연결을 확인하고 `python manage.py migrate` 후 개발 서버(`runserver`)를 실행합니다. 정적 파일 수집과 관리자 계정 생성은 수동으로 수행해야 합니다.
- Redis는 필수 구성요소가 아니며, `REDIS_URL`을 지정하지 않으면 Django 기본 메모리 캐시가 사용됩니다.

## 아키텍처
![Architecture Diagram](docs/architecture.png)

- **요청 경로**: 클라이언트 → Django REST API → LangChain 서비스 → OpenAI GPT-4o-mini → 단일 응답 반환.
- **RAG**: `data/rag/index.json`에 저장된 벡터 인덱스를 로드해 LangChain 검색에 활용합니다.
- **데이터 저장소**: MySQL 8을 기본 DB로 사용하며, 캐시는 Django Cache 프레임워크를 통해 Redis 또는 로컬 메모리를 사용할 수 있습니다.
- **운영 환경**: Docker Compose로 로컬 개발 환경을 제공하며, GitHub Actions + EC2 + Docker Compose로 프로덕션 배포를 자동화합니다.
- **옵저버빌리티**: Prometheus와 Grafana 컨테이너 구성을 포함해 `/metrics/` 엔드포인트를 모니터링할 수 있습니다.

## AI 처리 흐름
![AI Flow](docs/architecture.png)

1. 클라이언트가 `/api/ai/chat/` 또는 `/api/ai/job-certificates/`로 JWT 인증 후 요청을 전송합니다.
2. Django 뷰가 입력을 검증하고 LangChain 서비스 레이어를 호출합니다.
3. LangChain이 RAG 인덱스에서 문서를 검색한 뒤 OpenAI GPT-4o-mini에 질의해 JSON 응답을 생성합니다.
4. Django Cache를 통해 동일 요청을 일정 시간 저장합니다(기본은 로컬 메모리, `REDIS_URL` 설정 시 Redis 사용).
5. 최종 결과는 단일 HTTP 응답 형태로 반환되며 스트리밍은 사용하지 않습니다.

## 캐싱 & 성능 메모
- `AI_CHAT_CACHE_TTL`, `AI_JOB_ANALYSIS_CACHE_TTL` 환경 변수로 캐시 TTL을 조정할 수 있습니다.
- Redis를 사용할 경우 `docker-compose`에 별도 서비스를 추가하고 `.env`에 `REDIS_URL=redis://...`을 입력해주세요. 기본 템플릿에는 포함돼 있지 않습니다.
- 저장소의 `redis_stat.log`는 내부 테스트에서 수집한 Redis 통계 예시입니다. 실서비스 환경에서는 추가 로그 수집/모니터링 구성이 필요합니다.
- 공식적인 성능 수치는 아직 확정되지 않았으며, k6 스크립트로 부하 테스트를 반복하며 데이터를 축적 중입니다.

### Redis 도입 전후 모니터링(In-flight 50 VU, 15분 관찰)

![Redis 확장 전](docs/assets/redis-before.png)

- **API p95 응답시간**: 캐시 미적용 상태에서 최대 45~50초까지 상승, DB 커넥션 경합으로 Race Condition 발생.
- **요청 수(상태 코드별)**: 초반에는 상승하나 중간 이후 처리량 급감, 일부 요청이 대기 상태로 누적.
- **비정상 응답수**: 5분 평균 1.57건 수준의 오류 발생, 레이턴시 급등 구간에서 집중.
- **View별 평균 응답시간**: `ai-chat` 5.61초, `home` 17.1ms로 편차 심화.
- **누적 HTTP 요청 수**: 약 1.6K 처리, DB 접근 병목으로 인해 처리 한계 도달.

![Redis 적용 후](docs/assets/redis-after.png)

- **API p95 응답시간**: 초반 워밍업 이후 1초 미만으로 안정화, Redis 캐시 활성화로 DB 접근 횟수 대폭 감소.
- **요청 수(상태 코드별)**: 초당 25 req/s 수준 유지, 전구간 `200 OK` 비율 100% 달성.
- **비정상 응답수**: 0건, Race Condition 제거로 안정적인 응답 확보.
- **View별 평균 응답시간**: `ai-chat` 635ms, `home` 3.56ms로 전 구간 균일한 속도 유지.
- **누적 HTTP 요청 수**: 약 8K 처리(5배 증가), 캐시 히트율 상승으로 처리 효율 극대화.
- **총평**: Redis 캐싱으로 DB 부하 감소, Race Condition 해소, 확장 가능 구조 확보.

## 데이터 & RAG 파이프라인
1. **데이터 정리**: `data/data.xlsx`에 자격증 기본 정보와 통계 데이터를 워크시트별로 관리합니다.
2. **RAG 문서 생성**:
   ```bash
   python scripts/build_rag_documents.py \
     --input data/data.xlsx \
     --output data/rag/documents.jsonl
   ```
3. **임베딩 인덱스 빌드**:
   ```bash
   export OPENAI_API_KEY=sk-...
   python scripts/build_rag_index.py \
     --input data/rag/documents.jsonl \
     --output data/rag/index.json \
     --model text-embedding-3-small
   ```
4. **배포 연동**: `RAG_INDEX_PATH` 환경 변수로 인덱스 파일 경로를 지정합니다.
5. **검증**: 빌드 결과는 수동으로 스팟 체크하며, 추가 유효성 검사 스크립트는 현재 진행 중입니다.

## 운영 & DevOps
- **Docker**: `docker/entrypoint.sh`가 DB 준비 확인과 마이그레이션을 수행한 뒤 개발 서버를 기동합니다.
- **CI/CD**: `.github/workflows/deploy.yml`은 GitHub Actions에서 Django 테스트를 실행한 후, EC2 서버로 코드를 동기화하고 Docker Compose로 재배포합니다.
- **Kubernetes 템플릿**: `k8s/deployment.yaml`, `k8s/service.yaml`은 기본 Deployment/Service 예시이며 HPA나 Kustomize 오버레이는 포함되어 있지 않습니다.
- **모니터링**: `docker-compose`로 Prometheus/Grafana를 기동할 수 있으며, Alertmanager나 외부 알림 채널은 별도 구성해야 합니다.

## 테스트 & 품질
- `python manage.py test`로 Django TestCase 기반 단위/통합 테스트를 실행합니다.
- `k6/script.js`는 AI 챗봇 API에 대한 부하 테스트 시나리오를 제공합니다.
- 코드 스타일 도구(ruff, black 등)는 아직 레포지토리에 포함되어 있지 않습니다.

## 배포 정보
- 운영 URL: http://3.39.25.91:8080/
- 테스트 계정: `test` / `test1234`
- 헬스 체크: `https://skillbridge.app/healthz` (JSON `{ "status": "ok" }` 응답)

## 추가 문서
- `API.md` — REST API 명세
- `docs/architecture.png` — 시스템 구성 다이어그램
- `docs/ERD.png` — DB ERD (Mermaid 코드 대신 이미지 제공)
- `k6/` — 부하 테스트 스크립트
- `scripts/` — RAG 문서/인덱스 생성 스크립트

## License
MIT © 2025 Team SkillBridge *(별도 LICENSE 파일은 추후 추가 예정)*
