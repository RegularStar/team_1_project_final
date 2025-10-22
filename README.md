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

## GitHub Actions 기반 EC2 Docker 배포

### 1. 사전 준비 (EC2)
- Docker 와 Docker Compose 플러그인을 설치합니다. (Ubuntu 기준 `sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin`)  
  Amazon Linux에서 `docker compose` 플러그인 패키지를 찾지 못한다면 아래처럼 직접 설치할 수 있습니다.
  ```
  sudo mkdir -p /usr/local/lib/docker/cli-plugins
  sudo curl -SL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  docker compose version
  ```
- 배포에 사용할 디렉터리를 만듭니다. 기본 경로는 `${HOME}/skillbridge` (`/home/<EC2_USER>/skillbridge`)이며, 다른 경로를 쓰고 싶다면 워크플로 파일(`.github/workflows/deploy.yml`)의 `TARGET_DIR` 값을 수정하세요.
- 애플리케이션 컨테이너가 MySQL, Prometheus 등을 함께 구동하므로 EC2 보안 그룹의 관련 포트를 열어두거나, 필요 시 프록시 뒤에 배치합니다.

### 2. GitHub Secrets 설정
`.github/workflows/deploy.yml`은 아래 네 가지 시크릿을 요구합니다.
- `EC2_HOST` : 배포 대상 EC2 퍼블릭 IP 또는 도메인
- `EC2_USER` : SSH 접속 사용자 (예: `ubuntu`)
- `EC2_SSH_KEY` : EC2 접속용 개인키 (PEM 내용을 그대로 붙여 넣기)
- `ENV_FILE` : 다줄 환경변수 (.env 양식)  
  ```
  SECRET_KEY=...
  DEBUG=False
  DB_NAME=...
  DB_USER=...
  DB_PASSWORD=...
  DB_HOST=db
  DB_PORT=3306
  TZ=Asia/Seoul
  GRAFANA_ADMIN_USER=admin
  GRAFANA_ADMIN_PASSWORD=changeme
  ```
  `ENV_FILE`은 실제 운영 값으로 채워 넣습니다. GitHub 로그에서 자동 마스킹되지만, 필요하다면 민감 값을 세분화해 개별 시크릿으로 만든 뒤 워크플로를 수정해도 됩니다.

### 3. 동작 방식
- main 브랜치에 push 하거나, Actions 탭에서 `Deploy to EC2` 워크플로를 수동 실행하면 배포가 시작됩니다.
- 배포 잡은 GitHub Actions 상단에서 자동으로 Django 단위 테스트(`python manage.py test`)를 실행하며, 테스트가 실패하면 배포 단계는 건너뜁니다.
- GH Actions 러너 → EC2 로 코드를 `rsync`로 동기화한 뒤, `.env`를 재작성하고 `docker compose up -d --build`로 컨테이너를 재기동합니다. 이전 컨테이너는 `docker compose down --remove-orphans`로 정리합니다.
- 데이터베이스는 Docker 볼륨(`db_data`)을 사용하므로 컨테이너 재시작 시 데이터가 유지됩니다. 필요시 백업/복원 정책을 별도로 수립하세요.

### 4. 점검
- 워크플로 실행 로그에서 `Deploy application` 단계가 성공했는지 확인합니다.
- EC2에서 직접 상태를 보고 싶다면 `docker compose ps` 또는 `docker logs sb_web` 등을 확인할 수 있습니다.
- 문제 발생 시 EC2로 SSH 접속 후 수동으로 `cd ~/skillbridge && docker compose up -d --build` 를 실행해 재배포할 수 있습니다.

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
