import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
from decouple import config
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)


class RagRetrieverError(Exception):
    """Raised when the RAG retriever cannot be initialized or queried."""


@dataclass
class RagHit:
    text: str
    metadata: Dict[str, Any]
    score: float


def _resolve_index_path(path: Optional[str] = None) -> Path:
    configured = path or config("RAG_INDEX_PATH", default="data/rag/index.json")
    return Path(configured).expanduser().resolve()


def _resolve_api_key() -> Optional[str]:
    return config("GPT_KEY", default=None) or config("OPENAI_API_KEY", default=None)


class CertificateRagRetriever:
    """Lightweight vector-based retriever for certificate knowledge."""

    def __init__(
        self,
        *,
        documents: List[Dict[str, Any]],
        embeddings: np.ndarray,
        embedding_client: OpenAIEmbeddings,
        model_name: str,
    ):
        if not len(documents):
            raise ValueError("documents must not be empty.")
        if embeddings.shape[0] != len(documents):
            raise ValueError("embedding count must match document count.")

        self._documents = documents
        self._matrix = embeddings.astype(np.float32)
        self._norms = np.linalg.norm(self._matrix, axis=1)
        self._norms[self._norms == 0] = 1e-12
        self._embedder = embedding_client
        self._model_name = model_name

    @classmethod
    def from_index(cls, *, path: Optional[str] = None) -> "CertificateRagRetriever":
        index_path = _resolve_index_path(path)
        if not index_path.exists():
            raise RagRetrieverError(f"RAG 인덱스 파일을 찾을 수 없습니다: {index_path}")

        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RagRetrieverError(f"RAG 인덱스 파일을 파싱하지 못했습니다: {exc}") from exc

        model_name = payload.get("model") or config("RAG_EMBEDDING_MODEL", default="text-embedding-3-small")
        raw_documents: Iterable[Dict[str, Any]] = payload.get("documents") or []
        if not raw_documents:
            raise RagRetrieverError("RAG 인덱스에 문서가 없습니다.")

        documents: List[Dict[str, Any]] = []
        vectors: List[np.ndarray] = []
        for item in raw_documents:
            text = item.get("text")
            vector = item.get("embedding")
            if not text or not vector:
                continue
            try:
                vector_arr = np.asarray(vector, dtype=np.float32)
            except ValueError:
                continue
            doc = dict(item)
            doc.pop("embedding", None)
            documents.append(doc)
            vectors.append(vector_arr)

        if not documents or not vectors:
            raise RagRetrieverError("유효한 문서를 RAG 인덱스에서 찾지 못했습니다.")

        try:
            matrix = np.vstack(vectors)
        except ValueError as exc:
            raise RagRetrieverError("RAG 임베딩 행렬을 구성하지 못했습니다.") from exc

        api_key = _resolve_api_key()
        if not api_key:
            raise RagRetrieverError("GPT_KEY 환경 변수가 없어 RAG 검색을 비활성화합니다.")

        embedder = OpenAIEmbeddings(model=model_name, api_key=api_key)

        return cls(documents=documents, embeddings=matrix, embedding_client=embedder, model_name=model_name)

    @property
    def model_name(self) -> str:
        return self._model_name

    def search(self, query: str, *, top_k: int = 4, min_score: float = 0.35) -> List[RagHit]:
        if not query or not query.strip():
            return []

        try:
            query_vector = np.asarray(self._embedder.embed_query(query), dtype=np.float32)
        except Exception as exc:  # pragma: no cover - relies on external service
            logger.warning("RAG 임베딩 생성 실패: %s", exc)
            return []

        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return []

        similarities = (self._matrix @ query_vector) / (self._norms * query_norm)
        if np.isnan(similarities).all():
            return []

        ranked_indices = np.argsort(similarities)[::-1]
        hits: List[RagHit] = []
        for idx in ranked_indices[:top_k]:
            score = float(similarities[idx])
            if np.isnan(score) or score < min_score:
                continue
            document = self._documents[idx]
            text = document.get("text", "").strip()
            if not text:
                continue
            metadata = {k: v for k, v in document.items() if k != "text"}
            hits.append(RagHit(text=text, metadata=metadata, score=score))

        return hits


_cached_retriever: Optional[CertificateRagRetriever] = None
_retriever_failed: bool = False


def get_certificate_rag_retriever() -> Optional[CertificateRagRetriever]:
    global _cached_retriever, _retriever_failed  # noqa: PLW0603
    if _cached_retriever is not None:
        return _cached_retriever
    if _retriever_failed:
        return None

    try:
        _cached_retriever = CertificateRagRetriever.from_index()
    except RagRetrieverError as exc:
        _retriever_failed = True
        logger.info("RAG 검색 비활성화: %s", exc)
        return None
    except Exception as exc:  # pragma: no cover - safety catch
        _retriever_failed = True
        logger.exception("RAG 검색 초기화 실패: %s", exc)
        return None

    return _cached_retriever
