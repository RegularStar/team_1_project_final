import io
import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Prefetch
from PIL import Image

from certificates.models import Certificate, Tag

try:
    import pytesseract
    from pytesseract import TesseractError, TesseractNotFoundError
except ImportError:  # pragma: no cover - optional dependency
    pytesseract = None  # type: ignore[assignment]
    TesseractError = TesseractNotFoundError = RuntimeError  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------------------


class OcrError(Exception):
    """Raised when OCR extraction fails."""


class JobContentFetchError(Exception):
    """Raised when job content cannot be extracted."""


# ------------------------------------------------------------------------------
# OCR
# ------------------------------------------------------------------------------


class OCRService:
    """Simple OCR wrapper around pytesseract."""

    def extract_text(self, image, lang: str | None = None) -> str:
        if pytesseract is None:
            raise OcrError("pytesseract 패키지가 설치되어 있지 않습니다.")

        lang = (lang or "kor+eng").strip() or "kor+eng"

        try:
            if hasattr(image, "read"):
                raw = image.read()
                image.seek(0)
            else:  # In-memory bytes
                raw = image
            pil_image = Image.open(io.BytesIO(raw))
        except Exception as exc:  # pragma: no cover - defensive
            raise OcrError(f"이미지를 열 수 없습니다: {exc}") from exc

        try:
            text = pytesseract.image_to_string(pil_image, lang=lang)
        except TesseractNotFoundError as exc:
            raise OcrError("Tesseract 실행 파일을 찾을 수 없습니다.") from exc
        except TesseractError as exc:
            raise OcrError(str(exc)) from exc

        cleaned = (text or "").strip()
        if not cleaned:
            raise OcrError("인식된 텍스트가 없습니다.")
        return cleaned


# ------------------------------------------------------------------------------
# Chat
# ------------------------------------------------------------------------------


@dataclass
class ChatResult:
    assistant_message: str
    intent: str = "general_question"
    confidence: float = 0.0
    needs_admin: bool = False
    admin_summary: str = ""
    out_of_scope: bool = False


class LangChainChatService:
    """
    Placeholder chat service.
    In production you would connect to LangChain/OpenAI. 여기서는 테스트와 폴백을 지원한다.
    """

    def __init__(self):
        api_key = None
        try:
            from decouple import config

            api_key = config("OPENAI_API_KEY", default=None)
        except Exception:  # pragma: no cover - optional
            api_key = None

        if not api_key:
            self.available = False
        else:
            self.available = True

    def run(
        self,
        message: str,
        history: Optional[Iterable[dict]] = None,
        temperature: float = 0.3,
    ) -> dict:
        if not self.available:
            raise ImproperlyConfigured("OPENAI_API_KEY가 설정되어 있지 않습니다.")

        # 실제 연동 대신 간단한 에코를 반환한다. (프로덕션에서는 LLM 호출)
        reply = f"요청하신 메시지를 확인했습니다: {message}"
        conversation = list(history or []) + [{"role": "assistant", "content": reply}]
        result = ChatResult(
            assistant_message=reply,
            intent="general_question",
            confidence=0.2,
            needs_admin=False,
            admin_summary="",
            out_of_scope=False,
        )
        return {
            "assistant_message": result.assistant_message,
            "intent": result.intent,
            "confidence": result.confidence,
            "needs_admin": result.needs_admin,
            "admin_summary": result.admin_summary,
            "out_of_scope": result.out_of_scope,
            "conversation": conversation,
        }


# ------------------------------------------------------------------------------
# Recommendations
# ------------------------------------------------------------------------------


def _normalize_token(token: str) -> str:
    return re.sub(r"\s+", "", token.strip().lower())


def _tokenize(text: str) -> List[str]:
    cleaned = re.sub(r"[^0-9a-zA-Z가-힣\s]", " ", text)
    tokens = []
    for raw in cleaned.split():
        token = raw.strip()
        if len(token) < 2:
            continue
        tokens.append(token)
    return tokens


class JobCertificateRecommendationService:
    def __init__(self):
        self.ocr_service = OCRService()

    # --- helpers -----------------------------------------------------------------
    def _extract_text_from_image(self, image) -> str:
        try:
            return self.ocr_service.extract_text(image)
        except OcrError as exc:
            raise JobContentFetchError(str(exc)) from exc

    def _build_analysis(self, tokens: List[str], matched_tags: List[str], suggested_tags: List[str]) -> dict:
        focus = matched_tags[:6]
        essential = matched_tags[:6]
        preferred = matched_tags[6:12] if len(matched_tags) > 6 else []
        recommended = matched_tags[:3] or suggested_tags[:3]
        expanded = list(dict.fromkeys(tokens))  # preserve order and uniqueness
        if len(expanded) < 20:
            expanded += ["직무"] * (20 - len(expanded))
        expanded = expanded[:20]
        new_keywords = [token for token in suggested_tags if token not in matched_tags][:5]
        return {
            "job_title": matched_tags[0] if matched_tags else "",
            "focus_keywords": focus,
            "essential_skills": essential,
            "preferred_skills": preferred,
            "recommended_tags": recommended,
            "expanded_keywords": expanded,
            "new_keywords": new_keywords,
        }

    # --- public API ---------------------------------------------------------------
    def recommend(
        self,
        *,
        image,
        provided_content: Optional[str],
        max_results: int = 5,
    ) -> dict:
        if not provided_content and not image:
            raise JobContentFetchError("텍스트를 입력하거나 텍스트가 담긴 이미지를 업로드해주세요.")

        job_text_parts: List[str] = []
        if provided_content:
            job_text_parts.append(provided_content.strip())
        if image is not None:
            try:
                job_text_parts.append(self._extract_text_from_image(image))
            except JobContentFetchError as exc:
                if provided_content:
                    logger.warning("이미지 OCR 실패: %s", exc)
                else:
                    raise

        combined_text = "\n".join(part for part in job_text_parts if part)
        if not combined_text:
            raise JobContentFetchError("채용공고 본문이 비어있습니다.")

        tokens = _tokenize(combined_text)
        normalized_tokens = {_normalize_token(token) for token in tokens}

        tag_qs = Tag.objects.all()
        tag_map = {tag.id: tag.name for tag in tag_qs}
        normalized_tag_map = {tag_id: _normalize_token(name) for tag_id, name in tag_map.items()}

        certificates = (
            Certificate.objects.prefetch_related(
                Prefetch("tags", queryset=Tag.objects.only("id", "name"))
            )
            .exclude(tags=None)
            .all()
        )

        scored: List[tuple[Certificate, int, List[str]]] = []
        for certificate in certificates:
            matched = []
            for tag in certificate.tags.all():
                normalized = normalized_tag_map.get(tag.id, "")
                if normalized and normalized in normalized_tokens:
                    matched.append(tag_map[tag.id])
            if matched:
                score = min(100, len(matched) * 20)
                scored.append((certificate, score, matched))

        # sort by score desc then name
        scored.sort(key=lambda item: (-item[1], item[0].name))
        recommendations = [
            {
                "certificate": certificate,
                "score": score,
                "reasons": matched,
            }
            for certificate, score, matched in scored[:max_results]
        ]

        matched_keywords = sorted({reason for _, _, reasons in scored for reason in reasons})
        missing_keywords: List[str] = []

        # naive suggestions: tokens not matched that look like uppercase English words
        keyword_suggestions = [
            token for token in tokens if token not in matched_keywords and len(token) > 2
        ][:10]

        analysis = self._build_analysis(tokens, matched_keywords, keyword_suggestions)

        return {
            "job_excerpt": combined_text[:200],
            "raw_text": combined_text,
            "analysis": analysis,
            "recommendations": recommendations,
            "notice": None,
            "missing_keywords": missing_keywords,
            "matched_keywords": matched_keywords,
            "keyword_suggestions": keyword_suggestions,
        }
