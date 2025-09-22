#!/usr/bin/env sh
set -e

# DB 대기 (간단 폴링)
echo "Waiting for MySQL at $DB_HOST:$DB_PORT ..."
until python - <<'PY'
import sys, socket, os
s = socket.socket()
host = os.environ.get("DB_HOST", "db")
port = int(os.environ.get("DB_PORT", "3306"))
try:
    s.settimeout(1.0)
    s.connect((host, port))
    print("DB is up")
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
do
  sleep 1
done

# 마이그레이션
python manage.py migrate --noinput

# 개발 서버 실행
python manage.py runserver 0.0.0.0:8000