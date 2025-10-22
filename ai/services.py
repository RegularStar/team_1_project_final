import io
import json
import logging
import re
import textwrap
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from decouple import config
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Prefetch
from PIL import Image
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from bs4 import BeautifulSoup
from langchain_openai import ChatOpenAI

from .rag import RagHit, get_certificate_rag_retriever
try:
    import pytesseract
    from pytesseract import TesseractNotFoundError, TesseractError
except ImportError:  # pragma: no cover - optional dependency
    pytesseract = None  # type: ignore[assignment]
    TesseractNotFoundError = TesseractError = RuntimeError  # type: ignore[assignment]

JOB_TEXT_HINTS = [
    "주요업무",
    "주요 업무",
    "담당업무",
    "담당 업무",
    "직무",
    "업무",
    "업무내용",
    "역할",
    "Responsibilities",
    "Responsibility",
    "Role",
    "Description",
    "Job Description",
    "자격요건",
    "자격 요건",
    "필수요건",
    "필수 요건",
    "Qualifications",
    "Requirement",
    "우대사항",
    "우대 사항",
    "희망조건",
    "우대조건",
    "혜택",
]

JSON_NOISE_KEYWORDS = [
    "copyright",
    "모집분야",
    "마감일",
    "기업정보",
    "회사소개",
    "상세보기",
    "상담",
    "고객센터",
    "지원방법",
    "문의",
    "위치",
    "주소",
    "email",
    "tel",
    "fax",
]

from certificates.models import Certificate, Tag


ASSISTANT_SYSTEM_PROMPT = textwrap.dedent(
    """
    You are SkillBridge's AI assistant supporting Korean-speaking users with career planning, job search preparation, and certificate guidance.

    Core behaviour rules:
    1. 기본 응답 언어는 한국어이며, 사용자가 명시적으로 다른 언어를 요청할 때만 변경한다.
    2. 사용자 입력이 채용공고 주소나 본문이라면, 주요 직무·요구 기술·우대 사항을 요약한 뒤 관련 자격증이나 학습 주제를 제안한다.
    3. 직무 분석 시 공고에서 확인되는 직무명이나 포지션명을 우선적으로 추출하고, 해당 직무를 기준으로 필요한 역량·키워드를 정리한다.
    4. 추천을 제시할 때는 이유를 함께 설명하고, 사용자가 바로 확인할 수 있는 실용적인 다음 단계를 간단히 안내한다.
    5. 자격증 데이터나 통계 등 내부 시스템에서 제공되는 정보만 사실로 언급하고, 확신이 없을 때는 불확실함을 명시한다.
    6. 입력이 모호하거나 필수 정보가 부족하면, 추측하지 말고 필요한 정보를 정중히 요청한 뒤 답변을 이어간다.
    7. 질문이 자격증과 직접 관련이 없어도 커리어·학습·면접 준비 범위 안에서 최대한 도움을 준다.
    """
).strip()


DEFAULT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", ASSISTANT_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ]
)

CHAT_RESPONSE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            textwrap.dedent(
                """
                너는 SkillBridge의 AI 상담원으로, 자격증·커리어·통계 문의를 돕습니다.

                항상 아래 JSON 형식만 한국어로 반환하세요. 코드 블록, 주석, 불필요한 설명을 포함하지 마세요.
                {{
                  "assistant_message": "사용자에게 보여줄 답변 (한국어)",
                  "intent": "tag_request|info_update|stats_request|bug_report|general_question|out_of_scope|other",
                  "confidence": 0.0-1.0 숫자,
                  "needs_admin": true|false,
                  "admin_summary": "운영자에게 전달할 경우 한 줄 요약 (없으면 빈 문자열)",
                  "out_of_scope": true|false
                }}

                분류 규칙:
                - 자격증 추가나 신규 등록 요청은 intent \"tag_request\".
                - 자격증 정보, 상세, 일정 등의 수정 요청은 \"info_update\".
                - 통계, 데이터, 리포트 요청은 \"stats_request\".
                - 오류, 버그, 불편 신고는 \"bug_report\".
                - 자격증/커리어/학습 관련 일반 상담은 \"general_question\".
                - 위 범위를 벗어난 주제(예: 음악 추천, 가벼운 잡담)는 \"out_of_scope\".
                - 분류 불가하면 \"other\".

                needs_admin 규칙:
                - intent가 tag_request, info_update, stats_request, bug_report라면 true 로 설정하고 admin_summary에 짧은 문장을 작성해 운영자 전달 필요성을 알린다.
                - 그 외에는 false 로 설정한다.

                대화 맥락을 적극 활용해 사용자가 짧게 후속 질문을 하더라도 동일한 자격증·커리어 주제라면 그대로 답하거나 필요한 정보를 정중히 요청한다.
                정보가 부족하거나 명확하지 않으면 out_of_scope로 분류하지 말고 필요한 정보를 물어본다.
                제공된 컨텍스트나 내부 지식에서 답을 찾지 못하면 general_question 으로 분류하고 assistant_message에 데이터 부족 안내와 함께 추천 후속 조치를 제공한다.
                out_of_scope가 true이면 assistant_message 값에는 반드시 \"죄송하지만, 자격증 및 커리어와 직접 관련된 질문에 대해서만 도와드릴 수 있어요.\" 문자열만 넣는다.
                needs_admin 이 true이면 assistant_message 마지막 문장에 \"운영자에게 전달해 드릴까요?\" 와 같이 확인을 요청한다.
                항상 JSON 한 줄만 출력하며, 문자열 내부에는 줄바꿈을 넣지 말고 이스케이프를 적절히 처리한다.

                제공된 컨텍스트 자료가 있을 수 있습니다. 아래 [컨텍스트] 블록을 우선 참고하고, \"컨텍스트 없음\"이면 내부 지식만 활용하세요.

                [컨텍스트]
                {context}
                """
            ).strip(),
        ),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ]
)

JOB_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            textwrap.dedent(
                """
                너는 SkillBridge의 커리어 코파일럿이야. 사용자가 제공하는 텍스트는 채용공고일 수도 있고, 특정 회사/직무에 대한 관심사나 자기소개일 수도 있어.

                아래는 서비스에서 관리 중인 태그 목록이야. 이 목록에 있는 태그만 활용해 핵심 역량을 선별해야 해.
                {tag_catalog}

                반드시 JSON만 반환하고, 형식은 다음을 지켜.
                {{
                  "job_title": string,  // 텍스트에서 드러나는 핵심 목표·직무 요약 (없으면 빈 문자열)
                  "focus_keywords": [string, ...],  // 태그 목록에서 고른 대표 핵심 키워드 (최대 6개)
                  "essential_skills": [string, ...],  // 반드시 필요한 역량 태그 (최대 6개)
                  "preferred_skills": [string, ...],  // 있으면 좋은 보조 역량 태그 (최대 6개)
                  "recommended_tags": [string, ...],  // 태그 목록에서 고른 BEST 자격증 매칭용 태그 정확히 3개 (모자라면 가능한 만큼)
                  "expanded_keywords": [string, ...],  // 텍스트와 연관된 기술·역량 핵심 명사 정확히 20개 (태그 목록의 단어를 우선 사용하되, 부족하면 새 단어도 허용)
                  "new_keywords": [string, ...]  // 태그 목록에 없지만 꼭 추가되면 좋을 핵심 키워드 (기능어·일반명사는 넣지 말 것, 최대 5개)
                }}

                focus_keywords, essential_skills, preferred_skills, recommended_tags에는 반드시 태그 목록에 존재하는 용어만 넣어.
                expanded_keywords에는 태그 목록에 있는 용어를 우선 사용하되, 정말 필요하면 목록에 없는 연관 키워드도 포함할 수 있어. 단, 동사·형용사·기능어는 제외하고 핵심 명사만 중복 없이 정확히 20개를 제공해.
                new_keywords에는 목록에 없는 핵심 기술만 넣고, 이미 태그 목록에 있는 단어나 일반적인 표현(예: 분석, 및, 업무, 비즈니스 등)은 포함하지 마.
                불필요한 설명이나 다른 텍스트는 절대 출력하지 마.
                """
            ).strip(),
        ),
        ("human", "{job_text}"),
    ]
)


DEFAULT_JOB_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

GENERIC_STOPWORDS = {
    "및",
    "또는",
    "그리고",
    "대한",
    "관련",
    "관련된",
    "위한",
    "있는",
    "없는",
    "가능",
    "경력",
    "담당",
    "업무",
    "내용",
    "정보",
    "제품",
    "서비스",
    "사업",
    "지원",
    "제공",
    "필수",
    "우대",
    "자격",
    "요건",
    "조건",
    "요구",
    "기업",
    "기업의",
    "사정",
    "사정으로",
    "공지",
    "안내",
    "기간",
    "조기",
    "마감",
    "마감일은",
    "변경",
    "변경될",
    "가능성",
    "있습니다",
    "있어요",
    "남은기간",
    "접수",
    "시작일",
    "종료일",
    "근무지",
    "위치",
    "지도보기",
    "서울",
    "송파구",
    "송파대로",
    "송파대로34길",
    "송파동",
    "씨엠빌딩",
    "구내식당업",
    "기관",
    "000명",
    "이하",
    "팀",
    "회사",
    "조직",
    "프로젝트",
    "전략",
    "프로세스",
    "계획",
    "실행",
    "등",
    "및",
    "같은",
    "통한",
    "각종",
    "주요",
    "전반",
    "전체",
    "email",
    "helpdesk",
    "jobkorea",
    "co",
    "kr",
    "rights",
    "reserved",
    "llc",
    "copyright",
    "contact",
    "tel",
    "fax",
    "homepage",
    "접수기간",
    "방법",
    "남은기간",
    "시작일",
    "마감일",
    "기업정보",
    "문의",
    "고객센터",
    "support",
    "상세",
    "상세보기",
    "더보기",
    "사원수",
    "산업",
    "업종",
    "중견기업",
    "비상장",
    "기업구분",
    "위치정보",
}

FOCUS_SECTION_HEADINGS = [
    "주요 업무",
    "주요업무",
    "담당업무",
    "담당 업무",
    "업무 내용",
    "직무 내용",
    "직무 소개",
    "Job Description",
    "Responsibilities",
    "What you will do",
]

ESSENTIAL_SECTION_HEADINGS = [
    "자격 요건",
    "자격요건",
    "필수 자격",
    "필수 요건",
    "필수 사항",
    "필수 조건",
    "Required Qualifications",
    "Requirements",
    "Must have",
]

PREFERRED_SECTION_HEADINGS = [
    "우대사항",
    "우대 조건",
    "우대 요건",
    "우대 사항",
    "우대",
    "Preferred Qualifications",
    "Nice to have",
    "Plus",
]

SECTION_BREAK_KEYWORDS = [
    "근무 조건",
    "복리후생",
    "혜택",
    "전형 절차",
    "채용 절차",
    "지원 방법",
    "회사 소개",
    "Culture",
    "조직 문화",
    "Values",
    "Benefits",
]

ALL_SECTION_HEADINGS = (
    FOCUS_SECTION_HEADINGS
    + ESSENTIAL_SECTION_HEADINGS
    + PREFERRED_SECTION_HEADINGS
)

NON_JOB_LINE_KEYWORDS = [
    "접수기간",
    "남은기간",
    "기업 정보",
    "기업정보",
    "사원수",
    "산업",
    "업종",
    "위치",
    "지도보기",
    "문의",
    "고객센터",
    "contact",
    "지원 방법",
    "지원방법",
    "채용 절차",
    "채용절차",
    "전형 절차",
    "전형절차",
]

JOB_TITLE_PATTERN = re.compile(
    r"([가-힣A-Za-z0-9/&\-\s]{2,40}?(디자이너|디자인|개발자|엔지니어|매니저|마케터|기획자|에디터|컨설턴트|스페셜리스트|리더|담당자|전문가|연구원|디렉터|프로듀서|플래너))"
)


def _map_history(history: List[Dict[str, str]]) -> List[BaseMessage]:
    mapped: List[BaseMessage] = []
    for item in history:
        role = item["role"]
        content = item["content"]
        if role == "user":
            mapped.append(HumanMessage(content=content))
        else:
            mapped.append(AIMessage(content=content))
    return mapped


class LangChainChatService:
    def __init__(self, prompt: Optional[ChatPromptTemplate] = None):
        api_key = config("GPT_KEY")
        if not api_key:
            raise ImproperlyConfigured("GPT_KEY 환경 변수가 설정되지 않았습니다.")

        self.model = config("GPT_MODEL", default="gpt-4o-mini")
        self.prompt = prompt or CHAT_RESPONSE_PROMPT
        self.api_key = api_key
        self.retriever = get_certificate_rag_retriever()

    def _build_chain(self, temperature: float) -> Runnable:
        llm = ChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=temperature,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        return self.prompt | llm

    @staticmethod
    def _clean_json_text(raw: str) -> str:
        stripped = raw.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        return stripped.strip()

    @staticmethod
    def _parse_float(value) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, number))

    def run(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.3,
    ) -> Dict[str, object]:
        history = history or []
        context_text, context_hits = self._build_context(message)
        chain = self._build_chain(temperature)
        result = chain.invoke(
            {
                "history": _map_history(history),
                "input": message,
                "context": context_text,
            }
        )

        if isinstance(result, AIMessage):
            content = result.content
        elif isinstance(result, str):
            content = result
        else:
            raise RuntimeError("지원하지 않는 응답 형식입니다.")

        parsed = self._parse_assistant_json(content)
        assistant_message = parsed.get("assistant_message") or "죄송하지만 답변을 생성하지 못했습니다."
        intent = parsed.get("intent") or "general_question"
        needs_admin = bool(parsed.get("needs_admin"))
        admin_summary = (parsed.get("admin_summary") or "").strip()
        out_of_scope = bool(parsed.get("out_of_scope"))
        confidence = self._parse_float(parsed.get("confidence"))

        response = {
            "assistant_message": assistant_message.strip(),
            "intent": intent,
            "needs_admin": needs_admin,
            "admin_summary": admin_summary,
            "out_of_scope": out_of_scope,
            "confidence": confidence,
        }
        if context_hits:
            response["context_hits"] = [
                {
                    "id": hit.metadata.get("id"),
                    "certificate_id": hit.metadata.get("certificate_id"),
                    "type": hit.metadata.get("type"),
                    "name": hit.metadata.get("name"),
                    "year": hit.metadata.get("year"),
                    "score": round(hit.score, 4),
                }
                for hit in context_hits
            ]

        return response

    def _parse_assistant_json(self, raw: str) -> Dict[str, object]:
        cleaned = self._clean_json_text(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("AI JSON 파싱 실패: %s", cleaned)
            return {
                "assistant_message": cleaned,
                "intent": "general_question",
                "needs_admin": False,
                "admin_summary": "",
                "out_of_scope": False,
                "confidence": 0.0,
            }
        if not isinstance(data, dict):
            return {
                "assistant_message": cleaned if isinstance(cleaned, str) else "",
                "intent": "general_question",
                "needs_admin": False,
                "admin_summary": "",
                "out_of_scope": False,
                "confidence": 0.0,
            }
        return data

    def _build_context(self, message: str) -> Tuple[str, List[RagHit]]:
        if not self.retriever:
            return ("컨텍스트 없음", [])
        try:
            hits = self.retriever.search(message, top_k=4)
        except Exception as exc:  # pragma: no cover - safeguards
            logger.warning("RAG 검색 실패: %s", exc)
            return ("컨텍스트 없음", [])

        if not hits:
            return ("컨텍스트 없음", [])

        separator = "\n\n-----\n\n"
        context_parts: List[str] = []

        for hit in hits:
            text = hit.text.strip()
            if not text:
                continue

            metadata = hit.metadata
            prefix: List[str] = []
            name = metadata.get("name")
            if name:
                prefix.append(str(name))

            doc_type = metadata.get("type")
            if doc_type == "certificate_statistics" and metadata.get("year"):
                prefix.append(f"{metadata['year']}년 통계")
            elif doc_type == "certificate_profile":
                prefix.append("자격증 개요")

            if prefix:
                header = " - ".join(prefix)
                context_parts.append(f"[{header}]\n{text}")
            else:
                context_parts.append(text)

        if not context_parts:
            return ("컨텍스트 없음", [])

        return (separator.join(context_parts), hits)


class JobContentFetchError(Exception):
    """입력 자료를 준비하는 동안 발생한 오류."""


class JobKeywordExtractionError(Exception):
    """핵심 키워드 추출 실패."""


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
