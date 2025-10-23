# team_1_project_final



📌 GitHub 협업 가이드

1. 레포지토리 클론

팀 프로젝트 저장소를 내 컴퓨터로 가져오기:
```bash
git clone https://github.com/RegularStar/team_1_project_final.git
cd team_1_project_final
```

⸻

## 로컬 Kubernetes 배포 가이드

1. **로컬 클러스터 준비**
   - Minikube 혹은 Kind 등 Kubernetes 환경을 구동합니다.
   - Minikube를 사용할 경우 Docker daemon 사용을 위해 `eval $(minikube docker-env)` 실행을 권장합니다.

2. **Docker 이미지 빌드/적재**
   ```bash
   docker build -t skillbridge:local .
   # Minikube 사용 시
   minikube image load skillbridge:local
   ```
   Kubernetes 매니페스트(`k8s/deployment.yaml`)의 이미지 태그를 `skillbridge:local`로 바꾸거나 `kubectl set image`로 덮어쓸 수 있습니다.

3. **환경 변수 시크릿 생성**
   `.env` 파일 내용을 클러스터 시크릿으로 등록합니다.
   ```bash
   kubectl create secret generic skillbridge-env --from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -
   ```

4. **리소스 배포**
   ```bash
   kubectl apply -f k8s/service.yaml
   kubectl apply -f k8s/deployment.yaml
   kubectl get pods,svc
   ```

5. **접속 확인**
   ```bash
   kubectl port-forward svc/skillbridge 8000:8000
   curl http://localhost:8000/healthz
   ```

## k6 부하 테스트 실행

1. **전제 조건**
   - [k6](https://k6.io/) CLI 설치
   - Docker Compose로 실행 중이면 `http://localhost:8080`, Kubernetes 포트포워딩을 쓴다면 `http://localhost:8000` 등 테스트 대상 URL에 접근 가능해야 합니다.

2. **테스트 실행**
   ```bash
   k6 run k6/script.js --env BASE_URL=http://localhost:8080
   ```
   `BASE_URL`을 변경하면 Kubernetes 포트포워딩(예: `http://localhost:8000`)이나 배포 환경 등 다른 URL로도 테스트할 수 있습니다.

3. **지표 해석**
   - `http_req_duration`과 `home_duration` 등 커스텀 메트릭으로 응답 시간을 확인합니다.
   - `http_errors`가 5% 이상이면 실패율이 높은 것으로 간주하고 원인을 점검합니다.

필요에 따라 k6 옵션(`stages`, `thresholds`, 시나리오 등)을 수정해 다양한 트래픽 패턴을 실험할 수 있습니다.

### k6 메트릭 시각화 (Prometheus + Grafana)

1. **환경 변수 준비**  
   `.env`에 아래 항목을 추가하거나 `.env.example` 값을 참고해 원하는 계정 정보를 채워 넣습니다.
   ```
   GRAFANA_ADMIN_USER=admin
   GRAFANA_ADMIN_PASSWORD=changeme
   ```

2. **지원 서비스 기동**  
   웹/DB 컨테이너와 함께 Prometheus, Grafana가 올라옵니다.
   ```bash
   docker compose up -d db web prometheus grafana
   # 또는 docker-compose up -d db web prometheus grafana
   ```

3. **k6에서 Prometheus remote write로 메트릭 전송**  
   ```
   k6 run --out prometheus-remote-write=http://localhost:9090/api/v1/write \
     k6/script.js --env BASE_URL=http://localhost:8080
   ```
   k6가 Prometheus에 직접 메트릭을 푸시하며, `docker-compose.yml`에서 `--web.enable-remote-write-receiver` 옵션을 켜 두었기 때문에 별도 설정 없이 수신됩니다.

4. **Grafana 대시보드 확인**  
   - `http://localhost:3000` 접속 후 `.env`에 지정한 관리자 계정으로 로그인합니다.  
   - `Dashboards -> Browse -> k6` 폴더 아래에 자동으로 생성된 **k6 HTTP Overview** 대시보드에서 p95 응답 시간, 요청 수, 실패 건수, 가상 사용자 수를 실시간으로 볼 수 있습니다.  
   - 필요시 `dashboards/` 안에 JSON을 추가해 커스텀 패널을 손쉽게 늘릴 수 있습니다.

5. **정리**  
   테스트가 끝나면 `docker compose down`으로 컨테이너를 중지하고, 영구 데이터를 지우고 싶다면 `docker compose down -v`를 사용합니다.

> 참고: 호스트에서 MySQL은 `localhost:13306`으로 노출됩니다. 컨테이너 간 통신은 기존과 동일하게 `db:3306`을 사용하고, Docker Compose로 띄운 애플리케이션은 `http://localhost:8080`, Kubernetes 포트포워딩이나 서비스는 `http://localhost:8000`, Grafana는 `http://localhost:3000`으로 접근합니다.

2. 가상환경 & 패키지 설치
```bash
# 가상환경 생성 (Mac/Linux)

python3 -m venv venv
source venv/bin/activate


# Windows

python -m venv venv
venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt

```
⸻

3. 브랜치 전략
	•	기본(main) 브랜치는 배포용으로 사용
	•	각자 기능 작업 시에는 개인 브랜치를 따서 작업 후 PR(Pull Request)
```bash
# 새 브랜치 생성
git checkout -b feature/my-feature
```

⸻

4. 변경사항 반영
```bash
# 변경 확인
git status

# 변경 스테이징
git add .

# 커밋 (메시지는 간단+의미 있게)
git commit -m "로그인 기능 추가"

# 원격 푸시 (최초 1회 -u 옵션 필수)
git push -u origin feature/my-feature
```

⸻

5. Pull & Merge
	•	작업 시작 전 항상 최신 코드 받아오기:

git pull origin main

	•	작업 완료 후 GitHub에서 PR(Pull Request) 생성 → 코드 리뷰 → main 브랜치로 머지

⸻

6. 협업 시 주의사항
	•	main 브랜치에 직접 푸시 금지 (오직 PR을 통해 반영)
	•	커밋 메시지 규칙: 작업 단위 명확하게 ("feat: 회원가입 API 추가", "fix: DB 연결 오류 수정")
	•	자주 pull 해서 충돌 최소화

⸻

## RAG 문서 생성 파이프라인

`data/data.xlsx`에 있는 자격증 데이터를 챗봇 RAG 인덱스로 변환하려면 아래 절차를 따르세요.

1. 의존성 설치 (최초 1회)
   ```bash
   pip install openpyxl
   ```
   `requirements.txt`에 포함돼 있으므로 전체 패키지를 설치해도 됩니다.
2. 문서 생성 스크립트 실행
   ```bash
   python scripts/build_rag_documents.py \
     --input data/data.xlsx \
     --output data/rag/documents.jsonl
   ```
3. 임베딩 인덱스 생성 (OpenAI API 키 필요, `GPT_KEY` 또는 `OPENAI_API_KEY` 환경 변수 사용)
   ```bash
   python scripts/build_rag_index.py \
     --input data/rag/documents.jsonl \
     --output data/rag/index.json \
     --model text-embedding-3-small
   ```
   기본 경로는 `RAG_INDEX_PATH` 환경 변수로 변경할 수 있습니다.
4. 생성된 인덱스(`data/rag/index.json`)가 존재하면 챗봇이 자동으로 컨텍스트 검색을 수행합니다. 추가 벡터 DB가 필요하면 인덱스를 다른 스토어에 적재해 통계 질의에 활용하세요.

엑셀 파일을 업데이트하면 두 스크립트(`build_rag_documents.py`, `build_rag_index.py`)를 순서대로 재실행해 최신 정보를 인덱스에 반영하세요.

## Redis 캐시 (AI 서비스)

챗봇과 자격증 추천에서 OpenAI 호출 결과를 재사용하기 위해 Redis 캐시를 사용할 수 있어요.

1. Redis 실행 후 `.env`에 `REDIS_URL=redis://localhost:6379/1` 형태로 등록합니다.
2. (선택) 캐시 만료 시간은 `AI_CHAT_CACHE_TTL`(기본 300초), `AI_JOB_ANALYSIS_CACHE_TTL`(기본 900초) 환경변수로 조정할 수 있습니다.
3. Redis가 없으면 자동으로 메모리 캐시(LocMem)를 사용하므로 개발 환경에서도 바로 동작합니다.

캐시를 켜면 동일한 질문/직무 텍스트에 대해 OpenAI 호출 없이 빠르게 응답해 부하 테스트(k6)에서 전후 성능 비교가 가능합니다.
