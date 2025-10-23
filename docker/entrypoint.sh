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

# RAG 인덱스 자동 생성 (옵션)
if [ "${RAG_AUTO_BUILD:-false}" = "true" ]; then
  RAG_SOURCE_PATH=${RAG_SOURCE_PATH:-data/data.xlsx}
  RAG_DOCUMENTS_PATH=${RAG_DOCUMENTS_PATH:-data/rag/documents.jsonl}
  RAG_INDEX_PATH=${RAG_INDEX_PATH:-data/rag/index.json}

  if [ -f "$RAG_SOURCE_PATH" ]; then
    echo "Building RAG documents from ${RAG_SOURCE_PATH} ..."
    python scripts/build_rag_documents.py --input "$RAG_SOURCE_PATH" --output "$RAG_DOCUMENTS_PATH"

    if [ -n "${GPT_KEY:-}" ] || [ -n "${OPENAI_API_KEY:-}" ]; then
      echo "Building RAG index at ${RAG_INDEX_PATH} ..."
      python scripts/build_rag_index.py --input "$RAG_DOCUMENTS_PATH" --output "$RAG_INDEX_PATH"
    else
      echo "Skipping RAG index build: GPT_KEY/OPENAI_API_KEY is not set."
    fi
  else
    echo "Skipping RAG build: source file ${RAG_SOURCE_PATH} not found."
  fi
fi

# 마이그레이션
python manage.py migrate --noinput

# 개발 서버 실행
python manage.py runserver 0.0.0.0:8000
