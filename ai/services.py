import re
import textwrap
from typing import Dict, List, Optional

from decouple import config
from django.core.exceptions import ImproperlyConfigured
import requests
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from bs4 import BeautifulSoup

from certificates.models import Certificate


DEFAULT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "You are SkillBridge's AI assistant. Help users with career planning and certificates."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ]
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


class JobCertificateRecommendationService:
    def __init__(self, max_job_chars: int = 6000):
        self.max_job_chars = max_job_chars

    def recommend(
        self,
        url: str,
        max_results: int = 5,
        provided_content: Optional[str] = None,
    ) -> Dict[str, object]:
        job_text = self._resolve_job_text(url, provided_content)
        scored = self._score_certificates(job_text)
        top = scored[:max_results]
        summary = textwrap.shorten(job_text, width=400, placeholder="...")

        return {
            "job_excerpt": summary,
            "recommendations": top,
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

        return text[: self.max_job_chars]

    def _fetch_job_content(self, url: str) -> str:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise JobContentFetchError(f"채용공고를 가져오지 못했습니다: {exc}") from exc

        content_type = response.headers.get("Content-Type", "").lower()
        text = response.text
        if "html" in content_type:
            return self._strip_html(text)
        return text

    def _strip_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return " ".join(soup.stripped_strings)

    def _score_certificates(self, job_text: str) -> List[Dict[str, object]]:
        lowered = job_text.lower()
        tokens = self._tokenize(job_text)

        candidates: List[Dict[str, object]] = []

        queryset = Certificate.objects.prefetch_related("tags").all()
        for certificate in queryset:
            score = 0
            reasons: List[str] = []
            tag_matches: List[str] = []
            keyword_matches: List[str] = []

            if certificate.name and certificate.name.lower() in lowered:
                score += 5
                reasons.append(f"채용공고에 '{certificate.name}' 언급")

            for tag in certificate.tags.all():
                tag_lower = tag.name.lower()
                if tag_lower in lowered or any(tok in tokens for tok in self._tokenize(tag.name)):
                    if tag.name not in tag_matches:
                        tag_matches.append(tag.name)

            if tag_matches:
                score += 3 * len(tag_matches)
                reasons.append(f"관련 태그 일치: {', '.join(tag_matches)}")

            for field in ["overview", "job_roles", "exam_method", "eligibility", "type"]:
                value = getattr(certificate, field, "") or ""
                if not value:
                    continue
                field_tokens = self._tokenize(value)
                matched = sorted(field_tokens & tokens)
                if matched:
                    increment = min(len(matched), 3)
                    score += increment
                    keyword_matches.extend(matched[:3])

            keyword_matches = sorted(set(keyword_matches))
            if keyword_matches:
                reasons.append(f"핵심 키워드 일치: {', '.join(keyword_matches)}")

            if not score:
                continue

            candidates.append(
                {
                    "certificate": certificate,
                    "score": score,
                    "reasons": reasons,
                }
            )

        candidates.sort(key=lambda item: (-item["score"], item["certificate"].name))
        return candidates

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        tokens = set(
            token.lower()
            for token in re.findall(r"[\w+#]+", text)
            if len(token.strip()) >= 2
        )
        return tokens
