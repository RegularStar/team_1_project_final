import base64
import io
import json
import logging
import re
import textwrap
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from decouple import config
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from PIL import Image
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from bs4 import BeautifulSoup
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

<<<<<<< HEAD
=======
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

                out_of_scope가 true이면 assistant_message는 반드시 \"죄송하지만, 자격증 및 커리어와 직접 관련된 질문에 대해서만 도와드릴 수 있어요.\" 라고만 답한다.
                needs_admin 이 true이면 assistant_message 마지막 문장에 \"운영자에게 전달해 드릴까요?\" 와 같이 확인을 요청한다.
                항상 JSON 한 줄만 출력하며, 문자열 내부에는 줄바꿈을 넣지 말고 이스케이프를 적절히 처리한다.
                """
            ).strip(),
        ),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ]
)

>>>>>>> seil2
JOB_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            textwrap.dedent(
                """
<<<<<<< HEAD
                사용자는 한국어 채용공고 텍스트를 제공합니다.
                다음 필드를 포함한 JSON만 반환하세요.
                {{
                  "job_title": string,
                  "focus_keywords": [string, ...],
                  "essential_skills": [string, ...],
                  "preferred_skills": [string, ...]
                }}
                각 배열은 중복 없이 핵심만 나열하고, 추가 설명이나 문장은 포함하지 마세요.
=======
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
>>>>>>> seil2
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
        api_key = config("GPT_KEY", default=None)
        if not api_key:
            raise ImproperlyConfigured("GPT_KEY 환경 변수가 설정되지 않았습니다.")

        self.model = config("GPT_MODEL", default="gpt-4o-mini")
<<<<<<< HEAD
        self.prompt = prompt or DEFAULT_PROMPT
=======
        self.prompt = prompt or CHAT_RESPONSE_PROMPT
>>>>>>> seil2
        self.api_key = api_key

    def _build_chain(self, temperature: float) -> Runnable:
        llm = ChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=temperature,
        )
        return self.prompt | llm

<<<<<<< HEAD
=======
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

>>>>>>> seil2
    def run(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.3,
<<<<<<< HEAD
    ) -> str:
        history = history or []
        chain = self._build_chain(temperature)
        result = chain.invoke({
            "history": _map_history(history),
            "input": message,
        })
        if isinstance(result, str):
            return result
        if isinstance(result, AIMessage):
            return result.content
        raise RuntimeError("지원하지 않는 응답 형식입니다.")


class JobContentFetchError(Exception):
    """채용공고 본문을 가져오는 동안 발생한 오류."""


class JobKeywordExtractionError(Exception):
    """채용공고 키워드 추출 실패."""
=======
    ) -> Dict[str, object]:
        history = history or []
        chain = self._build_chain(temperature)
        result = chain.invoke({"history": _map_history(history), "input": message})

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

        return {
            "assistant_message": assistant_message.strip(),
            "intent": intent,
            "needs_admin": needs_admin,
            "admin_summary": admin_summary,
            "out_of_scope": out_of_scope,
            "confidence": confidence,
        }

    def _parse_assistant_json(self, raw: str) -> Dict[str, object]:
        cleaned = self._clean_json_text(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("AI JSON 파싱 실패: %s", cleaned)
            return {}
        if not isinstance(data, dict):
            return {}
        return data


class JobContentFetchError(Exception):
    """입력 자료를 준비하는 동안 발생한 오류."""


class JobKeywordExtractionError(Exception):
    """핵심 키워드 추출 실패."""
>>>>>>> seil2


logger = logging.getLogger(__name__)


class OcrError(Exception):
    """이미지에서 텍스트 추출 중 발생한 오류."""


class OCRService:
    def __init__(self, *, default_lang: str = "kor+eng"):
        self.default_lang = default_lang

    def extract_text(self, image_file, *, lang: str | None = None) -> str:
        if pytesseract is None:
            raise OcrError("pytesseract 라이브러리가 설치되어 있지 않습니다. requirements.txt를 확인하세요.")

        selected_lang = (lang or self.default_lang or "").strip() or "kor+eng"

        try:
            if hasattr(image_file, "seek"):
                image_file.seek(0)
            image = Image.open(image_file)
        except Exception as exc:
            raise OcrError(f"이미지를 열 수 없습니다: {exc}") from exc

        try:
            if image.mode not in ("L", "RGB"):
                image = image.convert("RGB")

            text = pytesseract.image_to_string(image, lang=selected_lang)
        except TesseractNotFoundError as exc:  # pragma: no cover
            raise OcrError("Tesseract OCR 실행 파일을 찾을 수 없습니다. 서버에 tesseract-ocr을 설치하세요.") from exc
        except TesseractError as exc:  # pragma: no cover
            raise OcrError(f"OCR 처리 중 오류가 발생했습니다: {exc}") from exc
        finally:
            image.close()

        return text.strip()


class JobKeywordExtractor:
    def __init__(self):
        api_key = config("GPT_KEY", default=None)
        if not api_key:
            raise ImproperlyConfigured("GPT_KEY 환경 변수가 설정되지 않았습니다.")
        model = config("GPT_MODEL", default="gpt-4o-mini")
        self.llm = ChatOpenAI(api_key=api_key, model=model, temperature=0.2)
        self.prompt = JOB_ANALYSIS_PROMPT

<<<<<<< HEAD
    def extract(self, job_text: str) -> Dict[str, object]:
        chain = self.prompt | self.llm
        result = chain.invoke({"job_text": job_text})
=======
    def extract(self, job_text: str, tag_catalog: List[str]) -> Dict[str, object]:
        chain = self.prompt | self.llm
        payload = {
            "job_text": job_text,
            "tag_catalog": self._format_tag_catalog(tag_catalog),
        }
        result = chain.invoke(payload)
>>>>>>> seil2
        if isinstance(result, str):
            content = result
        elif isinstance(result, AIMessage):
            content = result.content
        else:
            raise JobKeywordExtractionError("LLM 응답 형식을 해석할 수 없습니다.")

        try:
            data = self._decode_json(content)
        except json.JSONDecodeError as exc:
            raise JobKeywordExtractionError(f"LLM JSON 파싱 실패: {exc}") from exc

        return {
            "job_title": self._normalize_string(data.get("job_title")),
            "focus_keywords": self._normalize_list(data.get("focus_keywords")),
            "essential_skills": self._normalize_list(data.get("essential_skills")),
            "preferred_skills": self._normalize_list(data.get("preferred_skills")),
<<<<<<< HEAD
=======
            "recommended_tags": self._normalize_list(data.get("recommended_tags")),
            "expanded_keywords": self._normalize_list(data.get("expanded_keywords")),
            "new_keywords": self._normalize_list(data.get("new_keywords")),
>>>>>>> seil2
        }

    @staticmethod
    def _decode_json(raw: str) -> Dict[str, object]:
        stripped = raw.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        match = re.search(r"\{.*\}", stripped, re.S)
        if match:
            return json.loads(match.group())
        return json.loads(stripped)

    @staticmethod
    def _normalize_string(value) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip()

    @staticmethod
    def _normalize_list(value) -> List[str]:
        if not isinstance(value, list):
            return []
        cleaned: List[str] = []
        seen = set()
        for item in value:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            cleaned.append(text)
        return cleaned

<<<<<<< HEAD
=======
    @staticmethod
    def _format_tag_catalog(tags: List[str]) -> str:
        filtered = [
            tag.strip()
            for tag in tags
            if isinstance(tag, str) and tag and tag.strip()
        ]
        limited = filtered[:200]
        formatted = "\n".join(f"- {tag}" for tag in limited)
        if len(filtered) > len(limited):
            formatted += "\n- ..."
        return formatted

>>>>>>> seil2

class JobCertificateRecommendationService:
    def __init__(self, max_job_chars: int = 6000):
        self.max_job_chars = max_job_chars
        self._keyword_extractor: Optional[JobKeywordExtractor] = None
        self._tag_lookup: Optional[Dict[str, str]] = None

    def recommend(
        self,
<<<<<<< HEAD
        image,
=======
        image=None,
>>>>>>> seil2
        max_results: int = 5,
        provided_content: Optional[str] = None,
    ) -> Dict[str, object]:
        job_text = self._resolve_job_text(image, provided_content)
        summary = textwrap.shorten(job_text, width=400, placeholder="...")

        if not self._has_meaningful_content(job_text):
            return {
                "job_excerpt": summary,
                "raw_text": job_text,
                "analysis": {},
                "recommendations": [],
<<<<<<< HEAD
                "notice": "채용공고에서 직무 정보를 찾지 못했습니다. 공고 본문을 직접 입력해 주세요.",
            }

        analysis = self._extract_job_analysis(job_text)
        scored = self._score_certificates(job_text, analysis)
=======
                "notice": "입력 내용에서 핵심 정보를 찾지 못했습니다. 더 구체적인 목표나 활동을 입력해 주세요.",
                "missing_keywords": [],
            }

        analysis, keyword_suggestions = self._extract_job_analysis(job_text)
        scored, missing_keywords, matched_keywords = self._score_certificates(job_text, analysis)
>>>>>>> seil2
        top = scored[:max_results]

        notice: Optional[str] = None
        if not top:
            notice = "추천 가능한 자격증을 찾지 못했습니다. 데이터베이스에 관련 자격증이 부족할 수 있어요."

        return {
            "job_excerpt": summary,
            "raw_text": job_text,
            "analysis": analysis or {},
            "recommendations": top,
            "notice": notice,
<<<<<<< HEAD
=======
            "missing_keywords": missing_keywords,
            "matched_keywords": matched_keywords,
            "keyword_suggestions": keyword_suggestions,
>>>>>>> seil2
        }

    def _resolve_job_text(self, image_file, provided_content: Optional[str]) -> str:
        content = (provided_content or "").strip()
        if content:
            text = content
        else:
            text = self._extract_text_from_image(image_file)

        text = text.strip()
        if not text:
<<<<<<< HEAD
            raise JobContentFetchError("채용공고 본문이 비어있습니다.")
=======
            raise JobContentFetchError("입력 내용이 비어있습니다.")
>>>>>>> seil2

        focused = self._extract_relevant_sections(text)
        return focused[: self.max_job_chars]

    def _extract_text_from_image(self, image_file) -> str:
        if image_file is None:
<<<<<<< HEAD
            raise JobContentFetchError("채용공고 이미지를 제공해주세요.")
=======
            raise JobContentFetchError("텍스트가 담긴 이미지를 제공해주세요.")
>>>>>>> seil2

        ocr_service = OCRService()
        try:
            text = ocr_service.extract_text(image_file, lang=None)
        except OcrError as exc:
<<<<<<< HEAD
            raise JobContentFetchError(f"채용공고 이미지에서 텍스트를 추출하지 못했습니다: {exc}") from exc
=======
            raise JobContentFetchError(f"이미지에서 텍스트를 추출하지 못했습니다: {exc}") from exc
>>>>>>> seil2

        text = text.strip()
        if not text:
            raise JobContentFetchError("이미지에서 텍스트를 추출하지 못했습니다.")
        return text

    def _fetch_job_content(self, url: str) -> str:
        try:
            response = requests.get(url, headers=DEFAULT_JOB_FETCH_HEADERS, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
<<<<<<< HEAD
            raise JobContentFetchError(f"채용공고를 가져오지 못했습니다: {exc}") from exc
=======
            raise JobContentFetchError(f"자료를 가져오지 못했습니다: {exc}") from exc
>>>>>>> seil2

        content_type = response.headers.get("Content-Type", "").lower()
        is_image = "image" in content_type or url.lower().endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff")
        )

        if is_image:
            image_bytes = io.BytesIO(response.content)
            ocr_service = OCRService()
            try:
                text = ocr_service.extract_text(image_bytes, lang=None)
            except OcrError as exc:
                raise JobContentFetchError(f"이미지에서 텍스트를 추출하지 못했습니다: {exc}") from exc
            if not text:
                raise JobContentFetchError("이미지에서 텍스트를 추출하지 못했습니다.")
            return text

        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"

        text = response.text
        if "html" in content_type:
            parts: List[str] = []

            image_text = self._extract_text_from_images(text, response.url or url)
            if image_text:
                parts.append(image_text)

            extracted = self._extract_from_embedded_json(text)
            if extracted:
                parts.append(extracted)

            stripped = self._strip_html(text)
            if stripped:
                parts.append(stripped)

            combined = "\n".join(part for part in parts if part).strip()
            if combined:
                return combined
        return text

    def _extract_from_embedded_json(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return ""

        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            return ""

        collected: List[str] = []
        fallback: List[str] = []
        seen = set()

        def add_text(raw: str):
            if not isinstance(raw, str):
                return
            text_value = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
            if len(text_value) < 6:
                return
            normalized = text_value.casefold()
            if normalized in seen:
                return
            seen.add(normalized)
            if any(hint.casefold() in normalized for hint in JOB_TEXT_HINTS):
                collected.append(text_value)
            else:
                if not any(keyword in normalized for keyword in JSON_NOISE_KEYWORDS):
                    fallback.append(text_value)

        def walk(value):
            if isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
            elif isinstance(value, str):
                add_text(value)

        walk(data)

        if collected:
            return "\n".join(collected[:80]).strip()
        if fallback:
            return "\n".join(fallback[:80]).strip()
        return ""

    def _extract_text_from_images(self, html: str, base_url: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        image_urls: List[str] = []
        seen = set()

        ocr_service = OCRService()

        for img in soup.find_all("img"):
            src = img.get("data-src") or img.get("src")
            if not src:
                continue
            src = src.strip()
            if not src or src in seen:
                continue
            seen.add(src)

            if src.startswith("data:image"):
                try:
                    header, data = src.split(",", 1)
                    image_bytes = base64.b64decode(data)
                except Exception:
                    continue
                try:
                    text = ocr_service.extract_text(io.BytesIO(image_bytes), lang=None)
                except OcrError:
                    continue
                if text:
                    image_urls.append(text)
                continue

            full_url = urljoin(base_url, src)
            image_urls.append(full_url)

        ocr_texts: List[str] = []

        for entry in image_urls:
            if entry.startswith("http"):
                try:
                    image_response = requests.get(entry, headers=DEFAULT_JOB_FETCH_HEADERS, timeout=10)
                    image_response.raise_for_status()
                except requests.RequestException:
                    continue
                content_type = image_response.headers.get("Content-Type", "")
                if "image" not in content_type:
                    continue
                try:
                    text = ocr_service.extract_text(io.BytesIO(image_response.content), lang=None)
                except OcrError:
                    continue
            else:
                text = entry

            if text and len(text.strip()) >= 6:
                ocr_texts.append(text.strip())

        return "\n".join(ocr_texts)


    def _strip_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return "\n".join(soup.stripped_strings)

    def _extract_relevant_sections(self, text: str) -> str:
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and "http" not in line.casefold() and "www." not in line.casefold()
        ]
        if not lines:
            return text

        headline_patterns = [
            "주요 업무",
            "담당업무",
            "담당 업무",
            "업무 내용",
            "직무 내용",
            "직무 소개",
            "직무 요약",
            "Job Description",
            "Responsibilities",
            "What you will do",
        ]

        collected: List[str] = []
        capture = False
        buffer: List[str] = []

        def flush_buffer():
            nonlocal buffer
            if buffer:
                collected.extend(buffer)
                buffer = []

        for line in lines:
            normalized = line.casefold()
            if any(keyword in normalized for keyword in NON_JOB_LINE_KEYWORDS):
                continue
            is_headline = any(pattern.casefold() in normalized for pattern in headline_patterns) or normalized.endswith(":")

            if is_headline:
                flush_buffer()
                capture = True
                buffer.append(line)
                continue

            if capture:
                if len(line) <= 2 and not re.search(r"[가-힣a-zA-Z]", line):
                    flush_buffer()
                    capture = False
                    continue
                if any(keyword in normalized for keyword in NON_JOB_LINE_KEYWORDS):
                    flush_buffer()
                    capture = False
                    continue
                buffer.append(line)

        flush_buffer()

        if not collected:
            trimmed = "\n".join(lines[:80])
            return trimmed

        snippet = "\n".join(collected[:120])
        return snippet

<<<<<<< HEAD
    def _extract_job_analysis(self, job_text: str) -> Optional[Dict[str, object]]:
=======
    def _extract_job_analysis(self, job_text: str) -> tuple[Optional[Dict[str, object]], List[str]]:
>>>>>>> seil2
        gpt_analysis: Optional[Dict[str, object]] = None

        try:
            extractor = self._get_keyword_extractor()
        except ImproperlyConfigured:
            logger.debug("GPT_KEY 미설정으로 키워드 추출을 건너뜁니다.")
        else:
            try:
<<<<<<< HEAD
                gpt_analysis = extractor.extract(job_text)
            except JobKeywordExtractionError as exc:
                logger.warning("채용공고 키워드 추출 실패: %s", exc)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("채용공고 키워드 추출 중 예기치 못한 오류: %s", exc)

        fallback = self._fallback_job_analysis(job_text)
        merged = self._merge_analysis(gpt_analysis, fallback)
        return self._filter_analysis_to_tags(merged)
=======
                tag_catalog = sorted(set(self._get_tag_lookup().values()))
                gpt_analysis = extractor.extract(job_text, tag_catalog)
            except JobKeywordExtractionError as exc:
                logger.warning("핵심 키워드 추출 실패: %s", exc)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("핵심 키워드 추출 중 예기치 못한 오류: %s", exc)

        fallback = self._fallback_job_analysis(job_text)
        merged = self._merge_analysis(gpt_analysis, fallback)
        filtered = self._filter_analysis_to_tags(merged)
        suggestions: List[str] = []

        def add_suggestions(items: List[str]) -> None:
            for item in items:
                if not isinstance(item, str):
                    continue
                text = item.strip()
                if not text:
                    continue
                lowered = text.casefold()
                if lowered in seen_suggestions:
                    continue
                seen_suggestions.add(lowered)
                suggestions.append(text)

        seen_suggestions: set[str] = set()
        add_suggestions(filtered.get("recommended_tags", []))
        add_suggestions(filtered.get("expanded_keywords", []))
        add_suggestions(filtered.get("focus_keywords", []))
        add_suggestions(filtered.get("essential_skills", []))
        add_suggestions(filtered.get("preferred_skills", []))
        add_suggestions(filtered.get("new_keywords", []))

        return filtered, suggestions
>>>>>>> seil2

    def _get_keyword_extractor(self) -> JobKeywordExtractor:
        if self._keyword_extractor is None:
            self._keyword_extractor = JobKeywordExtractor()
        return self._keyword_extractor

    def _fallback_job_analysis(self, job_text: str) -> Dict[str, object]:
        lines = [line.strip() for line in job_text.splitlines() if line.strip()]
        job_title = self._guess_job_title(lines)

        focus_lines = self._collect_section_lines(lines, FOCUS_SECTION_HEADINGS, limit=60)
        essential_lines = self._collect_section_lines(lines, ESSENTIAL_SECTION_HEADINGS, limit=60)
        preferred_lines = self._collect_section_lines(lines, PREFERRED_SECTION_HEADINGS, limit=60)

        if not focus_lines:
            focus_lines = lines[:40]

        focus_keywords = self._keywords_from_lines(focus_lines, limit=10)
        essential_keywords = self._keywords_from_lines(essential_lines, limit=10)
        preferred_keywords = self._keywords_from_lines(preferred_lines, limit=10)

        if not essential_keywords:
            essential_keywords = focus_keywords[:6]

        if not preferred_keywords:
            preferred_keywords = [
                kw for kw in focus_keywords if kw not in essential_keywords
            ][:6]

<<<<<<< HEAD
=======
        recommended_tags = []
        seen = set()
        for item in focus_keywords + essential_keywords:
            lowered = item.casefold()
            if lowered in seen:
                continue
            seen.add(lowered)
            recommended_tags.append(item)
            if len(recommended_tags) >= 3:
                break

        expanded_keywords: List[str] = []
        seen_expanded = set(recommended_tags)
        for group in (focus_keywords, essential_keywords, preferred_keywords):
            for item in group:
                lowered = item.casefold()
                if lowered in seen_expanded:
                    continue
                seen_expanded.add(lowered)
                expanded_keywords.append(item)
                if len(expanded_keywords) >= 20:
                    break
            if len(expanded_keywords) >= 20:
                break

>>>>>>> seil2
        return {
            "job_title": job_title,
            "focus_keywords": focus_keywords,
            "essential_skills": essential_keywords,
            "preferred_skills": preferred_keywords,
<<<<<<< HEAD
=======
            "recommended_tags": recommended_tags,
            "expanded_keywords": expanded_keywords,
            "new_keywords": [],
>>>>>>> seil2
        }

    @staticmethod
    def _merge_analysis(primary: Optional[Dict[str, object]], fallback: Dict[str, object]) -> Dict[str, object]:
        if not primary:
            return fallback

        result = dict(primary)

        if not result.get("job_title") and fallback.get("job_title"):
            result["job_title"] = fallback["job_title"]

<<<<<<< HEAD
        for key in ("focus_keywords", "essential_skills", "preferred_skills"):
=======
        for key in ("focus_keywords", "essential_skills", "preferred_skills", "recommended_tags", "expanded_keywords"):
>>>>>>> seil2
            primary_values = primary.get(key) or []
            fallback_values = fallback.get(key) or []
            merged: List[str] = []
            seen = set()
            for item in primary_values + fallback_values:
                if not isinstance(item, str):
                    continue
                text = item.strip()
                if not text:
                    continue
                lowered = text.casefold()
                if lowered in seen:
                    continue
                seen.add(lowered)
                merged.append(text)
            result[key] = merged

<<<<<<< HEAD
=======
        primary_new = primary.get("new_keywords") or []
        fallback_new = fallback.get("new_keywords") or []
        combined_new: List[str] = []
        seen_new = set()
        for item in primary_new + fallback_new:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if not text:
                continue
            lowered = text.casefold()
            if lowered in seen_new:
                continue
            seen_new.add(lowered)
            combined_new.append(text)
        result["new_keywords"] = combined_new

>>>>>>> seil2
        return result

    def _collect_section_lines(self, lines: List[str], headings: List[str], *, limit: int) -> List[str]:
        collected: List[str] = []
        capture = False
        heading_tokens = [h.casefold() for h in headings]
        other_heading_tokens = [
            h.casefold() for h in ALL_SECTION_HEADINGS if h not in headings
        ]
        break_tokens = [b.casefold() for b in SECTION_BREAK_KEYWORDS]

        for line in lines:
            normalized = line.casefold()
            if any(token in normalized for token in heading_tokens):
                if capture and collected:
                    break
                capture = True
                remainder = line
                for heading in headings:
                    if heading in remainder:
                        remainder = remainder.split(heading, 1)[-1]
                remainder = remainder.lstrip(":-•□[]() ").strip()
                if remainder:
                    collected.append(remainder)
                continue

            if capture:
                if any(token in normalized for token in other_heading_tokens):
                    break
                if any(token in normalized for token in break_tokens):
                    break
                if any(keyword in normalized for keyword in NON_JOB_LINE_KEYWORDS):
                    continue
                collected.append(line)
                if len(collected) >= limit:
                    break

        return collected

    def _guess_job_title(self, lines: List[str]) -> str:
        search_space = " ".join(lines[:80])
        match = JOB_TITLE_PATTERN.search(search_space)
        if match:
            return match.group(0).strip()

        for line in lines[:10]:
            if len(line) > 40:
                continue
            if "디자이너" in line or "designer" in line.lower():
                return line.strip()
        return ""

    def _keywords_from_lines(self, lines: List[str], *, limit: int) -> List[str]:
        if not lines:
            return []

        tokens: List[str] = []
        seen = set()
        for raw in re.findall(r"[A-Za-z0-9가-힣+#/\\-]{2,}", " ".join(lines)):
            cleaned = self._clean_keyword(raw)
            if not cleaned:
                continue
            matched = self._match_tag(cleaned)
            if not matched:
                continue
            lower = matched.casefold()
            if lower in seen:
                continue
            seen.add(lower)
            tokens.append(matched)
            if len(tokens) >= limit:
                break
        return tokens

    def _clean_keyword(self, keyword: str) -> Optional[str]:
        if not keyword:
            return None
        text = keyword.strip()
        if len(text) < 2:
            return None
        if text.isdigit():
            return None
        if all(ch in "-_/\\." for ch in text):
            return None
        lowered = text.casefold()
        if lowered.startswith("http") or lowered.startswith("www"):
            return None
        if "http" in lowered or "www" in lowered:
            return None
        if any(ch.isdigit() for ch in text):
            if len(text) <= 3:
                return None
            if not any("가" <= ch <= "힣" or ch.isalpha() for ch in text if not ch.isdigit()):
                return None
        if not any("가" <= ch <= "힣" or ch.isalpha() for ch in text):
            return None
        if lowered in GENERIC_STOPWORDS:
            return None
        return text

    def _get_tag_lookup(self) -> Dict[str, str]:
        if self._tag_lookup is None:
            self._tag_lookup = {
                name.casefold(): name
                for name in Tag.objects.values_list("name", flat=True)
                if isinstance(name, str) and name.strip()
            }
        return self._tag_lookup

    def _match_tag(self, keyword: str) -> Optional[str]:
        lookup = self._get_tag_lookup()
        key = keyword.strip().casefold()
        return lookup.get(key)

    def _filter_keywords_to_tags(self, keywords: List[str], *, limit: Optional[int] = None) -> List[str]:
        filtered: List[str] = []
        seen = set()
        for raw in keywords:
            if not isinstance(raw, str):
                continue
            matched = self._match_tag(raw)
            if not matched:
                continue
            lowered = matched.casefold()
            if lowered in seen:
                continue
            seen.add(lowered)
            filtered.append(matched)
            if limit is not None and len(filtered) >= limit:
                break
        return filtered

    def _filter_analysis_to_tags(self, analysis: Dict[str, object]) -> Dict[str, object]:
        result = dict(analysis)
<<<<<<< HEAD
        for key in ("focus_keywords", "essential_skills", "preferred_skills"):
=======
        tag_keys = ("focus_keywords", "essential_skills", "preferred_skills", "recommended_tags")
        for key in tag_keys:
>>>>>>> seil2
            raw = result.get(key)
            if not raw:
                result[key] = []
                continue
            if isinstance(raw, list):
<<<<<<< HEAD
                result[key] = self._filter_keywords_to_tags(raw)
            else:
                result[key] = []
=======
                limit = 3 if key == "recommended_tags" else None
                result[key] = self._filter_keywords_to_tags(raw, limit=limit)
            else:
                result[key] = []

        expanded_raw = analysis.get("expanded_keywords")
        if isinstance(expanded_raw, list):
            seen_expanded: set[str] = set()
            expanded_clean: List[str] = []
            for item in expanded_raw:
                if not isinstance(item, str):
                    continue
                text = item.strip()
                if not text:
                    continue
                lowered = text.casefold()
                if lowered in seen_expanded:
                    continue
                seen_expanded.add(lowered)
                expanded_clean.append(text)
                if len(expanded_clean) >= 20:
                    break
            result["expanded_keywords"] = expanded_clean
        else:
            result["expanded_keywords"] = []

        raw_new = analysis.get("new_keywords")
        filtered_new: List[str] = []
        if isinstance(raw_new, list):
            seen = set()
            for item in raw_new:
                if not isinstance(item, str):
                    continue
                text = item.strip()
                if not text:
                    continue
                if self._match_tag(text):
                    continue
                lowered = text.casefold()
                if lowered in seen:
                    continue
                seen.add(lowered)
                filtered_new.append(text)
                if len(filtered_new) >= 5:
                    break
        result["new_keywords"] = filtered_new

>>>>>>> seil2
        return result

    def _generate_keywords_from_text(self, text: str, *, limit: int = 30) -> List[str]:
        tokens: List[str] = []
        seen = set()
        for raw in re.findall(r"[A-Za-z0-9가-힣+#/\\-]+", text):
            cleaned = self._clean_keyword(raw)
            if not cleaned:
                continue
            lower = cleaned.casefold()
            if lower in seen:
                continue
            seen.add(lower)
            tokens.append(cleaned)
            if len(tokens) >= limit:
                break
        return tokens

    def _has_meaningful_content(self, text: str) -> bool:
        tokens = self._generate_keywords_from_text(text, limit=40)
        return len(tokens) >= 4

    def _score_certificates(
        self,
        job_text: str,
        analysis: Optional[Dict[str, object]],
<<<<<<< HEAD
    ) -> List[Dict[str, object]]:
        normalized_keywords: Dict[str, str] = {}

        def add_keyword(raw_keyword: str) -> None:
=======
    ) -> tuple[List[Dict[str, object]], List[str], List[str]]:
        normalized_keywords: Dict[str, str] = {}
        loose_keywords: Dict[str, str] = {}
        missing_keywords: set[str] = set()

        def register_keyword(raw_keyword: str, *, record_missing: bool) -> None:
>>>>>>> seil2
            cleaned = self._clean_keyword(raw_keyword)
            if not cleaned:
                return
            matched = self._match_tag(cleaned)
<<<<<<< HEAD
            if not matched:
                return
            normalized_keywords.setdefault(matched.casefold(), matched)
=======
            if matched:
                normalized_keywords.setdefault(matched.casefold(), matched)
                return
            lowered = cleaned.casefold()
            if lowered not in loose_keywords:
                loose_keywords[lowered] = cleaned
            if record_missing:
                missing_keywords.add(cleaned)
>>>>>>> seil2

        job_title = None
        if analysis:
            job_title = analysis.get("job_title") or None
<<<<<<< HEAD
            for bucket in ("focus_keywords", "essential_skills", "preferred_skills"):
                for keyword in analysis.get(bucket, []) or []:
                    add_keyword(keyword)

        if job_title and isinstance(job_title, str):
            add_keyword(job_title)

        if not normalized_keywords:
            for keyword in self._keywords_from_lines(job_text.splitlines(), limit=30):
                add_keyword(keyword)

        if not normalized_keywords:
            for keyword in self._generate_keywords_from_text(job_text, limit=30):
                add_keyword(keyword)

        if not normalized_keywords:
            return []
=======

            for keyword in analysis.get("new_keywords") or []:
                register_keyword(keyword, record_missing=True)

            for bucket in ("recommended_tags", "expanded_keywords", "focus_keywords", "essential_skills", "preferred_skills"):
                for keyword in analysis.get(bucket, []) or []:
                    register_keyword(keyword, record_missing=False)

        if job_title and isinstance(job_title, str):
            register_keyword(job_title, record_missing=False)

        if not normalized_keywords and not loose_keywords:
            return [], sorted(missing_keywords, key=str.casefold), []
>>>>>>> seil2

        keyword_filter = Q()
        for original in normalized_keywords.values():
            term = original.strip()
            if not term:
                continue
            keyword_filter |= (
                Q(name__icontains=term)
                | Q(tags__name__icontains=term)
                | Q(overview__icontains=term)
                | Q(job_roles__icontains=term)
                | Q(exam_method__icontains=term)
                | Q(eligibility__icontains=term)
                | Q(type__icontains=term)
            )
<<<<<<< HEAD
=======
        for original in loose_keywords.values():
            term = original.strip()
            if not term:
                continue
            keyword_filter |= (
                Q(name__icontains=term)
                | Q(overview__icontains=term)
                | Q(job_roles__icontains=term)
                | Q(exam_method__icontains=term)
                | Q(eligibility__icontains=term)
                | Q(type__icontains=term)
            )
>>>>>>> seil2

        queryset = Certificate.objects.all().prefetch_related("tags")
        if keyword_filter.children:
            queryset = queryset.filter(keyword_filter).distinct()

        candidates: List[Dict[str, object]] = []

        job_title_lower = job_title.casefold() if isinstance(job_title, str) else ""

        for certificate in queryset:
            name_lower = (certificate.name or "").lower()
            field_blob = " ".join(
                [
                    certificate.overview or "",
                    certificate.job_roles or "",
                    certificate.exam_method or "",
                    certificate.eligibility or "",
                    certificate.type or "",
                ]
            ).lower()

            tag_names = [tag.name for tag in certificate.tags.all() if tag.name]
            tag_lowers = [tag.lower() for tag in tag_names]

            matched_name_keywords: set[str] = set()
            matched_field_keywords: set[str] = set()
            matched_tags: set[str] = set()
<<<<<<< HEAD
=======
            matched_loose_keywords: set[str] = set()
>>>>>>> seil2

            for lower_kw, original_kw in normalized_keywords.items():
                if lower_kw in name_lower:
                    matched_name_keywords.add(original_kw)
                elif lower_kw in field_blob:
                    matched_field_keywords.add(original_kw)

                for idx, tag_lower in enumerate(tag_lowers):
                    if not tag_lower:
                        continue
                    if lower_kw == tag_lower or lower_kw in tag_lower:
                        matched_tags.add(tag_names[idx])
                        break

<<<<<<< HEAD
=======
            for lower_kw, original_kw in loose_keywords.items():
                if lower_kw in name_lower or lower_kw in field_blob:
                    matched_loose_keywords.add(original_kw)

>>>>>>> seil2
            score = 0
            job_title_match = bool(job_title_lower and job_title_lower in name_lower)
            if job_title_match:
                score += 6
            if matched_name_keywords:
                score += 3 * len(matched_name_keywords)
            if matched_field_keywords:
                score += 2 * len(matched_field_keywords)
            if matched_tags:
                score += 4 * len(matched_tags)
<<<<<<< HEAD

            keyword_hits = len(matched_name_keywords | matched_field_keywords)
=======
            if matched_loose_keywords:
                score += 2 * len(matched_loose_keywords)

            keyword_hits = len(matched_name_keywords | matched_field_keywords | matched_loose_keywords)
>>>>>>> seil2

            if (
                not job_title_match
                and not matched_tags
<<<<<<< HEAD
                and keyword_hits < 2
=======
                and keyword_hits < 1
>>>>>>> seil2
            ):
                continue

            if not score:
                continue

            if score < 8:
                continue

            reasons: List[str] = []
            if job_title_match:
                reasons.append(f"직무명과 연관: {job_title}")
            if matched_tags:
                reasons.append(f"관련 태그 일치: {', '.join(sorted(matched_tags))}")
            combined_keywords = sorted(matched_name_keywords | matched_field_keywords)
            if combined_keywords:
                reasons.append(f"핵심 키워드 일치: {', '.join(combined_keywords)}")
<<<<<<< HEAD
=======
            if matched_loose_keywords:
                reasons.append(f"연관 키워드 일치: {', '.join(sorted(matched_loose_keywords))}")
>>>>>>> seil2
            candidates.append(
                {
                    "certificate": certificate,
                    "score": score,
                    "reasons": reasons,
                }
            )

        candidates.sort(key=lambda item: (-item["score"], item["certificate"].name))
<<<<<<< HEAD
        return candidates
=======
        matched_keywords = sorted(
            {value for value in normalized_keywords.values()} | set(loose_keywords.values()),
            key=str.casefold,
        )
        return candidates, sorted(missing_keywords, key=str.casefold), matched_keywords
>>>>>>> seil2
