FROM python:3.12-slim

# 시스템 패키지 (mysqlclient 빌드에 필요)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 소스 복사
COPY . .

# 로컬 타임존(옵션)
ARG TZ=Asia/Seoul
ENV TZ=${TZ}

EXPOSE 8000

# entrypoint 스크립트로 DB 준비 후 마이그레이션/실행
ENTRYPOINT ["sh", "docker/entrypoint.sh"]