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

from certificates.models import Certificate


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

JOB_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            textwrap.dedent(
                """
                사용자는 한국어 채용공고 텍스트를 제공합니다.
                다음 필드를 포함한 JSON만 반환하세요.
                {{
                  "job_title": string,
                  "focus_keywords": [string, ...],
                  "essential_skills": [string, ...],
                  "preferred_skills": [string, ...]
                }}
                각 배열은 중복 없이 핵심만 나열하고, 추가 설명이나 문장은 포함하지 마세요.
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
        self.prompt = prompt or DEFAULT_PROMPT
        self.api_key = api_key

    def _build_chain(self, temperature: float) -> Runnable:
        llm = ChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=temperature,
        )
        return self.prompt | llm

    def run(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.3,
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

    def extract(self, job_text: str) -> Dict[str, object]:
        chain = self.prompt | self.llm
        result = chain.invoke({"job_text": job_text})
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


class JobCertificateRecommendationService:
    def __init__(self, max_job_chars: int = 6000):
        self.max_job_chars = max_job_chars
        self._keyword_extractor: Optional[JobKeywordExtractor] = None

    def recommend(
        self,
        url: str,
        max_results: int = 5,
        provided_content: Optional[str] = None,
    ) -> Dict[str, object]:
        job_text = self._resolve_job_text(url, provided_content)
        summary = textwrap.shorten(job_text, width=400, placeholder="...")

        if not self._has_meaningful_content(job_text):
            return {
                "job_excerpt": summary,
                "raw_text": job_text,
                "analysis": {},
                "recommendations": [],
                "notice": "채용공고에서 직무 정보를 찾지 못했습니다. 공고 본문을 직접 입력해 주세요.",
            }

        analysis = self._extract_job_analysis(job_text)
        scored = self._score_certificates(job_text, analysis)
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
        }

    def _resolve_job_text(self, url: str, provided_content: Optional[str]) -> str:
        content = (provided_content or "").strip()
        if content:
            text = content
        else:
            text = self._fetch_job_content(url)

        text = text.strip()
        if not text:
            raise JobContentFetchError("채용공고 본문이 비어있습니다.")

        focused = self._extract_relevant_sections(text)
        return focused[: self.max_job_chars]

    def _fetch_job_content(self, url: str) -> str:
        try:
            response = requests.get(url, headers=DEFAULT_JOB_FETCH_HEADERS, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise JobContentFetchError(f"채용공고를 가져오지 못했습니다: {exc}") from exc

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

    def _extract_job_analysis(self, job_text: str) -> Optional[Dict[str, object]]:
        gpt_analysis: Optional[Dict[str, object]] = None

        try:
            extractor = self._get_keyword_extractor()
        except ImproperlyConfigured:
            logger.debug("GPT_KEY 미설정으로 키워드 추출을 건너뜁니다.")
        else:
            try:
                gpt_analysis = extractor.extract(job_text)
            except JobKeywordExtractionError as exc:
                logger.warning("채용공고 키워드 추출 실패: %s", exc)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("채용공고 키워드 추출 중 예기치 못한 오류: %s", exc)

        fallback = self._fallback_job_analysis(job_text)
        return self._merge_analysis(gpt_analysis, fallback)

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

        return {
            "job_title": job_title,
            "focus_keywords": focus_keywords,
            "essential_skills": essential_keywords,
            "preferred_skills": preferred_keywords,
        }

    @staticmethod
    def _merge_analysis(primary: Optional[Dict[str, object]], fallback: Dict[str, object]) -> Dict[str, object]:
        if not primary:
            return fallback

        result = dict(primary)

        if not result.get("job_title") and fallback.get("job_title"):
            result["job_title"] = fallback["job_title"]

        for key in ("focus_keywords", "essential_skills", "preferred_skills"):
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
            lower = cleaned.casefold()
            if lower in seen:
                continue
            seen.add(lower)
            tokens.append(cleaned)
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
    ) -> List[Dict[str, object]]:
        normalized_keywords: Dict[str, str] = {}

        def add_keyword(raw_keyword: str) -> None:
            cleaned = self._clean_keyword(raw_keyword)
            if not cleaned:
                return
            normalized_keywords.setdefault(cleaned.casefold(), cleaned)

        job_title = None
        if analysis:
            job_title = analysis.get("job_title") or None
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

            keyword_hits = len(matched_name_keywords | matched_field_keywords)

            if (
                not job_title_match
                and not matched_tags
                and keyword_hits < 2
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
            candidates.append(
                {
                    "certificate": certificate,
                    "score": score,
                    "reasons": reasons,
                }
            )

        candidates.sort(key=lambda item: (-item["score"], item["certificate"].name))
        return candidates
