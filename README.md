# team_1_project_final



📌 GitHub 협업 가이드

1. 레포지토리 클론

팀 프로젝트 저장소를 내 컴퓨터로 가져오기:

git clone https://github.com/RegularStar/team_1_project_final.git
cd team_1_project_final


⸻

2. 가상환경 & 패키지 설치

# 가상환경 생성 (Mac/Linux)
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt


⸻

3. 브랜치 전략
	•	기본(main) 브랜치는 배포용으로 사용
	•	각자 기능 작업 시에는 개인 브랜치를 따서 작업 후 PR(Pull Request)

# 새 브랜치 생성
git checkout -b feature/my-feature


⸻

4. 변경사항 반영

# 변경 확인
git status

# 변경 스테이징
git add .

# 커밋 (메시지는 간단+의미 있게)
git commit -m "로그인 기능 추가"

# 원격 푸시 (최초 1회 -u 옵션 필수)
git push -u origin feature/my-feature


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
