#!/usr/bin/env python3
"""
Generate a vector index for RAG from the pre-built documents JSONL.

Example:
    python scripts/build_rag_index.py \
        --input data/rag/documents.jsonl \
        --output data/rag/index.json \
        --model text-embedding-3-small
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from langchain_openai import OpenAIEmbeddings


def _load_documents(path: Path) -> List[Dict[str, Any]]:
    documents: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            text = (data.get("text") or "").strip()
            if not text:
                continue
            documents.append(data)
    return documents


def _resolve_api_key(provided: str | None = None) -> str:
    api_key = provided or os.getenv("GPT_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OpenAI API 키를 찾을 수 없습니다. GPT_KEY 또는 OPENAI_API_KEY를 설정해주세요.")
    return api_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SkillBridge RAG index.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/rag/documents.jsonl"),
        help="원본 문서 JSONL 경로",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/rag/index.json"),
        help="생성할 인덱스 파일 경로",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small"),
        help="사용할 OpenAI 임베딩 모델 이름",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=None,
        help="OpenAI API 키 (미지정 시 GPT_KEY/OPENAI_API_KEY 환경 변수 사용)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="임베딩 요청 배치 크기",
    )

    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"문서 파일을 찾을 수 없습니다: {args.input}")

    docs = _load_documents(args.input)
    if not docs:
        raise SystemExit("임베딩할 문서를 찾지 못했습니다.")

    api_key = _resolve_api_key(args.api_key)
    embeddings = OpenAIEmbeddings(api_key=api_key, model=args.model)

    texts = [doc["text"] for doc in docs]
    vectors: List[List[float]] = []
    batch = max(1, args.batch_size)
    for start in range(0, len(texts), batch):
        chunk = texts[start : start + batch]
        vectors.extend(embeddings.embed_documents(chunk))

    if len(vectors) != len(docs):
        raise SystemExit("임베딩 결과 수가 문서 수와 일치하지 않습니다.")

    index_payload = {
        "model": args.model,
        "document_count": len(docs),
        "documents": [],
    }

    for doc, vector in zip(docs, vectors):
        record = dict(doc)
        record["embedding"] = vector
        index_payload["documents"].append(record)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(index_payload, handle, ensure_ascii=False)

    print(f"Saved RAG index with {len(docs)} documents to {args.output}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\n중단되었습니다.")
