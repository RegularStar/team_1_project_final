import io
import json
import logging
import re
import textwrap
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from decouple import config
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Count, Q
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


logger = logging.getLogger(__name__)


class JobContentFetchError(Exception):
    """입력 자료를 준비하는 동안 발생한 오류."""


class JobKeywordExtractionError(Exception):
    """핵심 키워드 추출 실패."""


class JobRecommendationError(Exception):
    """Raised when LLM 기반 추천 생성이 실패한 경우."""


class OcrError(Exception):
    """Raised when OCR extraction fails."""


class JobRecommendationLLMClient:
    """OpenAI 기반 자격증 추천 생성기."""

    RECOMMEND_PROMPT = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                textwrap.dedent(
                    """
                    너는 채용 공고를 분석해 자격증 추천을 제공하는 전문가야.
                    JSON 객체 한 개만 한국어로 반환하고, 다음 키를 반드시 포함해:
                    {{
                      "job_summary": "한 문장 요약",
                      "analysis": {{
                        "focus_keywords": [string, ... 최대 6개],
                        "essential_skills": [string, ... 최대 6개],
                        "preferred_skills": [string, ... 최대 6개],
                        "recommended_tags": [string, ... 최대 6개],
                        "keyword_suggestions": [string, ... 최대 6개]
                      }},
                      "recommendations": [
                        {{
                          "certificate_name": "자격증 이름",
                          "reason": "추천 이유",
                          "confidence": 0.0~1.0 사이 숫자,
                          "matched_keywords": [string, ... 최대 6개],
                          "missing_keywords": [string, ... 최대 6개]
                        }}
                      ]
                    }}
                    - confidence는 0.0과 1.0 사이 값으로만 작성해.
                    - 제공된 자격증 데이터와 어울릴 만한 정확한 명칭으로 certificate_name을 적어.
                    - matched_keywords, missing_keywords는 중복 없이 핵심 키워드만 담아.
                    - JSON 이외의 텍스트(설명, 마크다운 등)는 절대 포함하지 마.
                    """
                ).strip(),
            ),
            (
                "human",
                textwrap.dedent(
                    """
                    [채용 공고 본문]
                    {job_text}

                    최대 추천 개수: {max_results}개
                    """
                ).strip(),
            ),
        ]
    )

    def __init__(self):
        api_key = config("GPT_KEY", default=None)
        if not api_key:
            raise ImproperlyConfigured("GPT_KEY 환경 변수가 설정되지 않았습니다.")

        model_name = config("GPT_MODEL", default="gpt-4o-mini")
        self._chain = self.RECOMMEND_PROMPT | ChatOpenAI(
            api_key=api_key,
            model=model_name,
            temperature=0.2,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

    def recommend(self, job_text: str, max_results: int) -> Dict[str, object]:
        try:
            result = self._chain.invoke({"job_text": job_text, "max_results": max_results})
        except Exception as exc:  # pragma: no cover - 외부 호출
            raise JobRecommendationError(str(exc)) from exc

        if isinstance(result, AIMessage):
            content = result.content
        elif isinstance(result, str):
            content = result
        else:
            raise JobRecommendationError("LLM이 지원하지 않는 형식으로 응답했습니다.")

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise JobRecommendationError(f"LLM JSON 응답 파싱 실패: {exc}") from exc

        if not isinstance(payload, dict):
            raise JobRecommendationError("LLM 응답이 올바른 JSON 객체가 아닙니다.")

        payload.setdefault("analysis", {})
        payload.setdefault("recommendations", [])
        return payload


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


class JobCertificateRecommendationService:
    def __init__(self):
        self.ocr_service = OCRService()

    def _extract_text_from_image(self, image) -> str:
        try:
            return self.ocr_service.extract_text(image)
        except OcrError as exc:
            raise JobContentFetchError(str(exc)) from exc

    def _resolve_job_text(self, *, image, provided_content: Optional[str]) -> str:
        if not provided_content and not image:
            raise JobContentFetchError("텍스트를 입력하거나 텍스트가 담긴 이미지를 업로드해주세요.")

        parts: List[str] = []
        if provided_content:
            parts.append(provided_content.strip())
        if image is not None:
            try:
                parts.append(self._extract_text_from_image(image))
            except JobContentFetchError as exc:
                if provided_content:
                    logger.warning("이미지 OCR 실패: %s", exc)
                else:
                    raise

        job_text = "\n".join(part for part in parts if part).strip()
        if not job_text:
            raise JobContentFetchError("채용공고 본문이 비어있습니다.")
        return job_text

    def _match_certificates(
        self, entries: List[Dict[str, object]]
    ) -> tuple[List[dict], List[str], List[str], List[str]]:
        recommendations: List[dict] = []
        matched_keywords: set[str] = set()
        missing_keywords: set[str] = set()
        keyword_suggestions: set[str] = set()

        for entry in entries:
            name = (entry or {}).get("certificate_name")
            if not isinstance(name, str) or not name.strip():
                continue
            certificate = Certificate.objects.filter(name__iexact=name.strip()).first()
            if not certificate:
                continue

            reason = (entry or {}).get("reason") or ""
            confidence = entry.get("confidence")
            try:
                confidence_value = float(confidence)
            except (TypeError, ValueError):
                confidence_value = 0.0

            matched_keywords.update(entry.get("matched_keywords") or [])
            missing_keywords.update(entry.get("missing_keywords") or [])
            keyword_suggestions.update(entry.get("keyword_suggestions") or [])

            recommendations.append(
                {
                    "certificate": certificate,
                    "score": max(0, min(100, int(round(confidence_value * 100)))),
                    "reasons": [reason] if reason else [],
                }
            )

        return (
            recommendations,
            sorted({keyword for keyword in matched_keywords if isinstance(keyword, str)}),
            sorted({keyword for keyword in missing_keywords if isinstance(keyword, str)}),
            sorted({keyword for keyword in keyword_suggestions if isinstance(keyword, str)}),
        )

    @staticmethod
    def _collect_analysis_tags(analysis: Dict[str, object]) -> List[str]:
        if not isinstance(analysis, dict):
            return []

        candidates: List[str] = []
        seen: set[str] = set()
        for key in ("recommended_tags", "focus_keywords", "essential_skills", "preferred_skills"):
            values = analysis.get(key)
            if not isinstance(values, list):
                continue
            for value in values:
                if not isinstance(value, str):
                    continue
                normalized = value.strip()
                if not normalized:
                    continue
                lowered = normalized.casefold()
                if lowered in seen:
                    continue
                seen.add(lowered)
                candidates.append(normalized)
        return candidates

    def _fallback_recommendations_from_tags(
        self,
        *,
        analysis: Dict[str, object],
        max_results: int,
    ) -> tuple[List[dict], set[str]]:
        tag_labels = self._collect_analysis_tags(analysis)
        if not tag_labels:
            return ([], set())

        tag_map: dict[int, str] = {}
        tag_ids: List[int] = []
        for label in tag_labels:
            tag = Tag.objects.filter(name__iexact=label).first()
            if not tag:
                continue
            if tag.id in tag_map:
                continue
            tag_map[tag.id] = tag.name
            tag_ids.append(tag.id)

        if not tag_ids:
            return ([], set())

        queryset = (
            Certificate.objects.filter(tags__in=tag_ids)
            .annotate(match_count=Count("tags", filter=Q(tags__in=tag_ids), distinct=True))
            .order_by("-match_count", "name")
            .distinct()
            .prefetch_related("tags")
        )

        # 넉넉한 후보를 확보한 뒤 상위 max_results 개만 선택
        candidate_certificates = list(queryset[: max_results * 3 or max_results])
        if not candidate_certificates:
            return ([], set())

        recommendations: List[dict] = []
        matched_keywords: set[str] = set()

        for certificate in candidate_certificates:
            matched_tag_names = [
                tag.name for tag in certificate.tags.all() if tag.id in tag_map
            ]
            if not matched_tag_names:
                continue

            matched_keywords.update(matched_tag_names)

            total_candidates = max(len(tag_ids), 1)
            match_ratio = len(matched_tag_names) / total_candidates
            score = int(round(60 + match_ratio * 40))
            score = max(40, min(95, score))

            reason = f"채용 공고 핵심 태그와 {len(matched_tag_names)}개 일치: {', '.join(matched_tag_names)}"
            recommendations.append(
                {
                    "certificate": certificate,
                    "score": score,
                    "reasons": [reason],
                }
            )

            if len(recommendations) >= max_results:
                break

        return (recommendations, matched_keywords)

    def recommend(
        self,
        *,
        image,
        provided_content: Optional[str],
        max_results: int = 5,
    ) -> dict:
        job_text = self._resolve_job_text(image=image, provided_content=provided_content)

        try:
            llm_client = JobRecommendationLLMClient()
            llm_payload = llm_client.recommend(job_text, max_results)
        except ImproperlyConfigured as exc:
            raise JobContentFetchError(str(exc)) from exc
        except JobRecommendationError as exc:
            raise JobContentFetchError(f"AI 추천 생성에 실패했습니다: {exc}") from exc

        analysis = llm_payload.get("analysis") or {}
        if not isinstance(analysis, dict):
            analysis = {}

        raw_recommendations = llm_payload.get("recommendations") or []
        (
            recommendations,
            matched_keywords,
            missing_keywords,
            keyword_suggestions,
        ) = self._match_certificates(raw_recommendations[:max_results])

        if not recommendations:
            fallback_recommendations, fallback_matched_keywords = self._fallback_recommendations_from_tags(
                analysis=analysis,
                max_results=max_results,
            )
            if fallback_recommendations:
                recommendations = fallback_recommendations
                if fallback_matched_keywords:
                    matched_keywords = sorted(
                        {keyword for keyword in matched_keywords} | set(fallback_matched_keywords)
                    )

        if not keyword_suggestions:
            analysis_suggestions = analysis.get("keyword_suggestions")
            if isinstance(analysis_suggestions, list):
                keyword_suggestions = sorted(
                    {str(item) for item in analysis_suggestions if isinstance(item, str)}
                )

        job_summary = llm_payload.get("job_summary") or ""

        return {
            "job_excerpt": job_text[:200],
            "raw_text": job_text,
            "analysis": analysis,
            "recommendations": recommendations,
            "notice": job_summary or None,
            "missing_keywords": missing_keywords,
            "matched_keywords": matched_keywords,
            "keyword_suggestions": keyword_suggestions,
        }
