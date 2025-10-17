import re
from collections import defaultdict
from typing import List

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import (
    Case,
    Count,
    CharField,
    FloatField,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from certificates.models import Certificate, CertificateStatistics, Tag, UserCertificate
from community.forms import PostForm, PostCommentForm
from community.models import Post, PostLike
from ratings.forms import RatingForm
from ratings.models import Rating
from ratings.services import certificate_rating_summary

STAR_RANGE = range(2, 12, 2)
FIVE_STAR_RANGE = range(1, 6)
AVATAR_COLORS = ["#7aa2ff", "#3ddc84", "#ffb74d", "#64b5f6", "#ff8a80", "#9575cd"]

SEARCH_PAGE_SIZE = 9
TAG_SUGGESTION_LIMIT = 12

TYPE_FILTERS = [
    ("국가기술자격", "국가기술자격"),
    ("국가전문자격", "국가전문자격"),
    ("민간자격", "민간자격"),
]

SORT_OPTIONS = [
    ("pass_rate", "합격률순"),
    ("applicants", "응시자수"),
    ("name", "이름순"),
    ("difficulty", "난이도순"),
]

DEFAULT_SORT = "pass_rate"


TYPE_CATEGORY_CASE = Case(
    When(type__icontains="민간", then=Value("민간자격")),
    When(type__icontains="전문", then=Value("국가전문자격")),
    When(type__icontains="기술", then=Value("국가기술자격")),
    When(type__icontains="국가", then=Value("국가기술자격")),
    default=Value("기타"),
    output_field=CharField(),
)


def _parse_number(value: str, default: float, *, minimum: float | None = None, maximum: float | None = None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _build_page_numbers(page_obj, window: int = 2) -> List[int | None]:
    total_pages = page_obj.paginator.num_pages
    current = page_obj.number
    start = max(current - window, 1)
    end = min(current + window, total_pages)

    pages: List[int | None] = list(range(start, end + 1))

    if start > 2:
        pages = [1, None] + pages
    elif start == 2:
        pages = [1] + pages

    if end < total_pages - 1:
        pages += [None, total_pages]
    elif end == total_pages - 1:
        pages += [total_pages]

    return pages


def _get_certificate_by_slug(slug: str) -> Certificate:
    queryset = Certificate.objects.prefetch_related("tags")
    if slug.isdigit():
        cert = queryset.filter(pk=int(slug)).first()
        if cert:
            return cert
    for cert in queryset:
        if slugify(cert.name) == slug:
            return cert
    raise Http404("Certificate not found")


def _certificate_slug(cert: Certificate) -> str:
    slug_text = slugify(cert.name)
    return slug_text or str(cert.pk)


def permission_denied_view(request, exception=None):
    status_code = 403
    template_name = "users/access_denied.html"
    context = {
        "exception": exception,
        "redirect_url": reverse("login") if not request.user.is_authenticated else reverse("mypage"),
        "is_superuser": request.user.is_authenticated and request.user.is_superuser,
    }
    return render(request, template_name, context, status=status_code)


def _split_roles(raw_value: str) -> List[str]:
    if not raw_value:
        return []

    normalized = str(raw_value).replace("\r\n", "\n")
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]

    items: List[str] = []
    current: str | None = None
    for line in lines:
        if line.startswith(("-", "•", "▪")):
            if current:
                items.append(current.strip())
            current = line.lstrip("-•▪ ").strip()
        elif current:
            current += " " + line
        else:
            current = line

    if current:
        items.append(current.strip())

    if len(items) > 1:
        return items

    fallback = [part.strip() for part in re.split(r"[·,;/]", normalized) if part.strip()]
    if len(fallback) > 1:
        return fallback

    return [normalized.strip()]


def _format_duration(value):
    if value in (None, ""):
        return "정보 없음"
    try:
        numeric = float(value)
        if numeric.is_integer():
            numeric = int(numeric)
        return f"{numeric}개월"
    except (TypeError, ValueError):
        return str(value)


def _serialize_certificate(certificate_obj: Certificate, slug_value: str | None = None):
    tag_names = list(certificate_obj.tags.order_by("name").values_list("name", flat=True))
    primary_tag = tag_names[0] if tag_names else None

    latest_stat = (
        CertificateStatistics.objects.filter(certificate=certificate_obj)
        .order_by("-year", "-session")
        .first()
    )
    pass_rate = (
        float(latest_stat.pass_rate)
        if latest_stat and latest_stat.pass_rate is not None
        else None
    )

    stage_pass_rates = []
    stats_by_session = (
        CertificateStatistics.objects.filter(certificate=certificate_obj)
        .values("exam_type", "year", "pass_rate")
    )
    latest_stage: dict[str, dict[str, object]] = {}

    for stat in stats_by_session:
        exam_type = stat.get("exam_type")
        if exam_type in (None, ""):
            continue
        stage_info = _classify_exam_stage(exam_type)
        if stage_info["key"] == "total":
            continue
        year = stat.get("year")
        if not year:
            continue
        pass_rate_value = stat.get("pass_rate")
        if pass_rate_value in (None, ""):
            continue
        try:
            numeric_rate = float(pass_rate_value)
        except (TypeError, ValueError):
            continue

        existing = latest_stage.get(stage_info["key"])
        if existing:
            stored_year = existing["year"]
            if _year_sort_key(year) <= _year_sort_key(stored_year):
                continue
        latest_stage[stage_info["key"]] = {
            "key": stage_info["key"],
            "label": stage_info["label"],
            "order": stage_info["order"],
            "year": str(year),
            "pass_rate": numeric_rate,
        }

    for entry in sorted(latest_stage.values(), key=lambda item: (item["order"], item["label"])):
        stage_pass_rates.append(entry)

    category_value = primary_tag or certificate_obj.type or "자격증"
    meta_parts: List[str] = []
    for value in (category_value, certificate_obj.authority, certificate_obj.type):
        if value and value not in meta_parts:
            meta_parts.append(value)

    roles_list = _split_roles(certificate_obj.job_roles)
    roles_is_list = len(roles_list) > 1 or (
        roles_list
        and str(certificate_obj.job_roles or "").strip().startswith(("-", "•", "▪"))
    )

    return {
        "id": certificate_obj.id,
        "slug": slug_value or _certificate_slug(certificate_obj),
        "title": certificate_obj.name,
        "category": category_value,
        "issuer": certificate_obj.authority or "발급처 정보 없음",
        "type": certificate_obj.type or "자격증",
        "meta": meta_parts,
        "difficulty": certificate_obj.rating or 0,
        "difficulty_star_states": star_states_from_difficulty(certificate_obj.rating or 0),
        "tags": tag_names,
        "duration": {
            "non_major": _format_duration(certificate_obj.expected_duration),
            "major": _format_duration(certificate_obj.expected_duration_major),
        },
        "pass_rate": pass_rate,
        "pass_rates_by_stage": stage_pass_rates,
        "overview": certificate_obj.overview or "",
        "roles": roles_list,
        "roles_is_list": roles_is_list,
        "roles_text": certificate_obj.job_roles or "",
        "exam_method": certificate_obj.exam_method or "",
        "eligibility": certificate_obj.eligibility or "",
        "homepage": certificate_obj.homepage or "",
    }


def _year_sort_key(year_text: str):
    if year_text is None:
        return (-float("inf"), "")
    text = str(year_text).strip()
    match = re.search(r"\d+", text)
    if match:
        try:
            return (int(match.group()), text)
        except Exception:
            pass
    return (0, text)


def _classify_exam_stage(raw_value):
    text = str(raw_value).strip() if raw_value is not None else ""
    if not text:
        return {"key": "stage-misc", "label": "기타", "order": 900}

    digit_match = re.search(r"\d+", text)
    if digit_match:
        try:
            number = int(digit_match.group())
        except ValueError:
            number = None
        if number == 10:
            return {"key": "total", "label": "전체", "order": 100}
        if number is not None:
            return {"key": f"stage-{number}", "label": f"{number}차", "order": number}

    lowered = text.lower()
    if any(keyword in text for keyword in ("전체", "합계")):
        return {"key": "total", "label": "전체", "order": 100}
    if any(keyword in lowered for keyword in ("필기", "서류", "이론")):
        return {"key": "stage-1", "label": "1차", "order": 1}
    if any(keyword in lowered for keyword in ("실기", "실습", "작업")):
        return {"key": "stage-2", "label": "2차", "order": 2}
    if any(keyword in lowered for keyword in ("면접", "구술")):
        return {"key": "stage-3", "label": "3차", "order": 3}
    if "최종" in lowered:
        return {"key": "stage-4", "label": "최종", "order": 4}

    return {
        "key": f"label-{slugify(text) or 'misc'}",
        "label": text,
        "order": 500,
    }


def _build_statistics_payload(certificate_obj: Certificate):
    stats_qs = certificate_obj.statistics.values(
        "exam_type",
        "year",
        "registered",
        "applicants",
        "passers",
        "pass_rate",
    )

    data_by_stage: dict[str, dict] = {}
    years: set[str] = set()

    for row in stats_qs:
        year_raw = row.get("year")
        if not year_raw:
            continue
        year_text = str(year_raw).strip()
        years.add(year_text)

        stage_info = _classify_exam_stage(row.get("exam_type"))
        key = stage_info["key"]
        entry = data_by_stage.setdefault(
            key,
            {
                "key": key,
                "label": stage_info["label"],
                "order": stage_info["order"],
                "aliases": set(),
                "metrics": {},
            },
        )

        label_text = str(row.get("exam_type") or "").strip()
        if label_text:
            entry["aliases"].add(label_text)

        metrics = entry["metrics"].setdefault(
            year_text,
            {"registered": None, "applicants": None, "passers": None, "pass_rate": None},
        )

        for field in ("registered", "applicants", "passers"):
            value = row.get(field)
            if value in (None, ""):
                continue
            try:
                numeric = int(value)
            except (TypeError, ValueError):
                continue
            if metrics[field] is None:
                metrics[field] = numeric
            else:
                metrics[field] += numeric

        pass_rate_val = row.get("pass_rate")
        if pass_rate_val not in (None, ""):
            try:
                metrics["pass_rate"] = float(pass_rate_val)
            except (TypeError, ValueError):
                pass

    if not data_by_stage:
        return {"years": [], "total": None, "sessions": []}, None

    for entry in data_by_stage.values():
        for metrics in entry["metrics"].values():
            base = metrics.get("applicants")
            if base in (None, 0):
                base = metrics.get("registered")
            passers = metrics.get("passers")
            if (
                metrics.get("pass_rate") in (None, "")
                and passers not in (None, "")
                and base not in (None, 0)
            ):
                try:
                    metrics["pass_rate"] = round(passers / base * 100, 1)
                except ZeroDivisionError:
                    metrics["pass_rate"] = None

    total_entry = data_by_stage.get("total")
    if not total_entry:
        total_entry = {
            "key": "total",
            "label": "전체",
            "order": 100,
            "aliases": {"전체"},
            "metrics": {},
        }
        for entry in data_by_stage.values():
            if entry["key"] == "total":
                continue
            for year, metrics in entry["metrics"].items():
                aggregate = total_entry["metrics"].setdefault(
                    year,
                    {"registered": None, "applicants": None, "passers": None, "pass_rate": None},
                )
                for field in ("registered", "applicants", "passers"):
                    value = metrics.get(field)
                    if value is None:
                        continue
                    if aggregate[field] is None:
                        aggregate[field] = value
                    else:
                        aggregate[field] += value
        data_by_stage["total"] = total_entry

    for metrics in total_entry["metrics"].values():
        base = metrics.get("applicants")
        if base in (None, 0):
            base = metrics.get("registered")
        passers = metrics.get("passers")
        if (
            metrics.get("pass_rate") in (None, "")
            and passers not in (None, "")
            and base not in (None, 0)
        ):
            try:
                metrics["pass_rate"] = round(passers / base * 100, 1)
            except ZeroDivisionError:
                metrics["pass_rate"] = None

    for entry in data_by_stage.values():
        aliases = entry["aliases"]
        alias_list = sorted(aliases, key=len) if aliases else []
        if entry["label"] in (None, "", "기타") and alias_list:
            entry["label"] = alias_list[0]
        entry["aliases"] = alias_list

    years_sorted = sorted(years, key=_year_sort_key)
    if not years_sorted:
        return {"years": [], "total": None, "sessions": []}, None

    def normalize_metrics_map(metrics_map):
        normalized = {}
        for year_key, values in metrics_map.items():
            year_label = str(year_key)
            normalized_entry = {}
            for field in ("registered", "applicants", "passers"):
                value = values.get(field)
                if value in (None, ""):
                    normalized_entry[field] = None
                else:
                    try:
                        normalized_entry[field] = int(value)
                    except (TypeError, ValueError):
                        try:
                            normalized_entry[field] = int(float(value))
                        except Exception:
                            normalized_entry[field] = None
            rate_value = values.get("pass_rate")
            if rate_value in (None, ""):
                normalized_entry["pass_rate"] = None
            else:
                try:
                    normalized_entry["pass_rate"] = float(rate_value)
                except (TypeError, ValueError):
                    normalized_entry["pass_rate"] = None
            normalized[year_label] = normalized_entry
        return normalized

    def build_series(metrics_map):
        series = {}
        for field in ("registered", "applicants", "passers"):
            values: List[int | None] = []
            for year in years_sorted:
                metrics = metrics_map.get(year)
                if not metrics:
                    values.append(None)
                    continue
                value = metrics.get(field)
                values.append(int(value) if value is not None else None)
            series[field] = values

        pass_rate_values: List[float | None] = []
        for year in years_sorted:
            metrics = metrics_map.get(year)
            if not metrics:
                pass_rate_values.append(None)
                continue
            value = metrics.get("pass_rate")
            pass_rate_values.append(float(value) if value is not None else None)
        series["pass_rate"] = pass_rate_values
        return series

    total_payload = {
        "label": total_entry["label"],
        "series": build_series(total_entry["metrics"]),
        "metrics": normalize_metrics_map(total_entry["metrics"]),
    }

    sessions_payload = []
    for entry in sorted(
        (item for item in data_by_stage.values() if item["key"] != "total"),
        key=lambda item: (item["order"], item["label"]),
    ):
        sessions_payload.append(
            {
                "key": entry["key"],
                "label": entry["label"],
                "aliases": entry["aliases"],
                "series": build_series(entry["metrics"]),
                "metrics": normalize_metrics_map(entry["metrics"]),
            }
        )

    latest_year = years_sorted[-1]
    latest_metrics = total_entry["metrics"].get(latest_year)
    latest_snapshot = None
    if latest_metrics:
        latest_snapshot = {
            "year": latest_year,
            "registered": latest_metrics.get("registered"),
            "applicants": latest_metrics.get("applicants"),
            "passers": latest_metrics.get("passers"),
            "pass_rate": latest_metrics.get("pass_rate"),
        }

    payload = {
        "years": years_sorted,
        "total": total_payload,
        "sessions": sessions_payload,
    }
    return payload, latest_snapshot


def star_states_from_five(score: float):
    states = []
    for idx in FIVE_STAR_RANGE:
        if score >= idx:
            states.append("full")
        elif score + 0.5 >= idx:
            states.append("half")
        else:
            states.append("empty")
    return states


def star_states_from_difficulty(score10: float):
    return star_states_from_five(score10 / 2)


def avatar_color_for_user(user_id: int) -> str:
    return AVATAR_COLORS[user_id % len(AVATAR_COLORS)]


def _approved_holder_ids(certificate: Certificate) -> set[int]:
    return set(
        UserCertificate.objects.filter(
            certificate=certificate,
            status=UserCertificate.STATUS_APPROVED,
        ).values_list("user_id", flat=True)
    )


def build_rating_context(
    certificate: Certificate,
    *,
    review_limit: int | None = 4,
    page: int | None = None,
    per_page: int = 8,
):
    summary_raw = certificate_rating_summary(certificate.id)
    average_10 = summary_raw.get("average", 0) or 0
    total = summary_raw.get("total", 0) or 0
    average_10 = float(average_10) if total else 0.0

    distribution_raw = {row["score"]: row["count"] for row in summary_raw.get("distribution", [])}
    breakdown = []
    for level in range(1, 11):
        count = distribution_raw.get(level, 0)
        percent = round(count / total * 100) if total else 0
        breakdown.append({
            "level": level,
            "count": count,
            "percent": percent,
        })

    summary = {
        "average": average_10,
        "total": total,
        "breakdown": breakdown,
        "average_star_states": star_states_from_difficulty(average_10),
    }

    reviews_qs = (
        Rating.objects.select_related("user", "certificate")
        .filter(certificate=certificate)
        .order_by("-created_at")
    )

    page_obj = None
    page_numbers = None

    has_reviews = total > 0

    if page is not None and has_reviews:
        paginator = Paginator(reviews_qs, per_page)
        page_obj = paginator.get_page(page)
        page_numbers = _build_page_numbers(page_obj)
        reviews_iter = page_obj.object_list
    elif page is not None:
        reviews_iter = []
    else:
        reviews_iter = reviews_qs[:review_limit] if review_limit else reviews_qs

    holder_ids = _approved_holder_ids(certificate)

    def to_review(review: Rating):
        rating10 = review.perceived_score
        display_name = review.user.name or review.user.username
        return {
            "id": review.id,
            "difficulty_display": rating10,
            "star_states": star_states_from_difficulty(rating10),
            "title": review.certificate.name,
            "comment": review.content or "작성된 후기가 없습니다.",
            "nickname": display_name,
            "date": review.created_at.strftime("%Y-%m-%d"),
            "avatar_color": avatar_color_for_user(review.user_id),
            "avatar_url": None,
            "initial": display_name[:1].upper(),
            "is_certified": review.user_id in holder_ids,
        }

    reviews = [to_review(review) for review in reviews_iter]

    return {
        "summary": summary,
        "reviews": reviews,
        "page_obj": page_obj,
        "page_numbers": page_numbers,
    }



def _certificate_sample_data(
    slug: str,
    *,
    review_limit: int | None = 4,
    review_page: int | None = None,
    per_page: int = 8,
):
    certificate_obj = _get_certificate_by_slug(slug)
    certificate = _serialize_certificate(certificate_obj, slug)

    difficulty_scale = [
        {"level": 1, "description": "아주 쉬움. 기초 개념 위주라 단기간 준비로 누구나 합격 가능한 수준."},
        {"level": 2, "description": "쉬움. 기본 지식이 있으면 무난히 도전할 수 있는 입문 수준."},
        {"level": 3, "description": "보통. 일정한 학습이 필요하지만 꾸준히 준비하면 충분히 합격 가능한 수준."},
        {"level": 4, "description": "다소 어려움. 이론과 실무를 균형 있게 요구하며, 준비 기간이 다소 긴 수준."},
        {"level": 5, "description": "중상 난이도. 전공지식과 응용력이 필요해 체계적 학습이 요구되는 수준."},
        {"level": 6, "description": "어려움. 합격률이 낮고 심화 학습이 필요해 전공자도 부담되는 수준."},
        {"level": 7, "description": "매우 어려움. 방대한 범위와 높은 난이도로 전공자도 장기간 학습이 필수인 수준."},
        {"level": 8, "description": "극히 어려움. 전문성·응용력·실무 경험이 모두 요구되는 최상위권 자격 수준."},
        {"level": 9, "description": "최상 난이도. 전문지식과 실무를 총망라하며, 합격자가 극소수에 불과한 수준."},
        {"level": 10, "description": "극한 난이도. 수년간 전념해도 합격을 장담할 수 없는, 최고 난도의 자격 수준."},
    ]

    page_number = None
    if review_page:
        try:
            page_number = int(review_page)
        except (TypeError, ValueError):
            page_number = 1

    rating_context = build_rating_context(
        certificate_obj,
        review_limit=review_limit,
        page=page_number,
        per_page=per_page,
    )

    return {
        "certificate": certificate,
        "difficulty_scale": difficulty_scale,
        "rating_summary": rating_context["summary"],
        "reviews": rating_context["reviews"],
        "review_page_obj": rating_context["page_obj"],
        "review_page_numbers": rating_context["page_numbers"],
        "star_range": STAR_RANGE,
        "five_star_range": FIVE_STAR_RANGE,
        "certificate_object": certificate_obj,
    }

def home(request):
    """Render the public landing page."""
    recommended = []
    interest_keywords = []

    if request.user.is_authenticated:
        tag_ids = list(request.user.user_tags.values_list("tag_id", flat=True))
        if tag_ids:
            interest_keywords = list(
                Tag.objects.filter(id__in=tag_ids)
                .order_by("name")
                .values_list("name", flat=True)
            )

            tag_id_set = set(tag_ids)
            certificates = (
                Certificate.objects.filter(tags__in=tag_ids)
                .annotate(
                    match_count=Count(
                        "tags",
                        filter=Q(tags__in=tag_ids),
                        distinct=True,
                    ),
                    total_tags=Count("tags", distinct=True),
                )
                .order_by("-match_count", "-rating", "name")
                .prefetch_related("tags")
            )

            for cert in certificates[:10]:
                tag_records = list(cert.tags.all())
                matched_tags = [tag.name for tag in tag_records if tag.id in tag_id_set]
                other_tags = [tag.name for tag in tag_records if tag.id not in tag_id_set][:3]

                recommended.append(
                    {
                        "id": cert.id,
                        "slug": _certificate_slug(cert),
                        "name": cert.name,
                        "rating": cert.rating,
                        "match_count": getattr(cert, "match_count", 0),
                        "matched_tags": matched_tags,
                        "other_tags": other_tags,
                    }
                )

    context = {
        "recommended_certificates": recommended,
        "interest_keywords": interest_keywords,
    }

    return render(request, "home.html", context)


@login_required
def job_recommendation(request):
    """Render form for AI-based job certificate recommendations."""
    return render(request, "job_recommendation.html")


def search(request):
    """Search certificates with filtering, sorting, and pagination."""

    raw_query = request.GET.get("q", "").strip()
    selected_types = [
        value
        for value in request.GET.getlist("type")
        if value in {key for key, _ in TYPE_FILTERS}
    ]

    difficulty_min = _parse_number(
        request.GET.get("difficulty_min"),
        default=0,
        minimum=0,
        maximum=10,
    )
    difficulty_max = _parse_number(
        request.GET.get("difficulty_max"),
        default=10,
        minimum=0,
        maximum=10,
    )
    if difficulty_min > difficulty_max:
        difficulty_min, difficulty_max = difficulty_max, difficulty_min

    pass_rate_min = _parse_number(
        request.GET.get("pass_rate_min"),
        default=0,
        minimum=0,
        maximum=100,
    )
    pass_rate_max = _parse_number(
        request.GET.get("pass_rate_max"),
        default=100,
        minimum=0,
        maximum=100,
    )
    if pass_rate_min > pass_rate_max:
        pass_rate_min, pass_rate_max = pass_rate_max, pass_rate_min

    sort_key = request.GET.get("sort", DEFAULT_SORT)
    sort_keys = {key for key, _ in SORT_OPTIONS}
    if sort_key not in sort_keys:
        sort_key = DEFAULT_SORT

    selected_tag_ids: List[int] = []
    for tag_value in request.GET.getlist("tag"):
        try:
            tag_id = int(tag_value)
        except (TypeError, ValueError):
            continue
        if tag_id not in selected_tag_ids:
            selected_tag_ids.append(tag_id)

    tag_suggestions = (
        Tag.objects.annotate(cert_count=Count("certificates"))
        .order_by("-cert_count", "name")
        [:TAG_SUGGESTION_LIMIT]
    )

    selected_tags_map = {
        tag.id: tag for tag in Tag.objects.filter(id__in=selected_tag_ids)
    }
    selected_tags = [
        selected_tags_map[tag_id]
        for tag_id in selected_tag_ids
        if tag_id in selected_tags_map
    ]

    queryset = (
        Certificate.objects.all()
        .annotate(
            type_category=TYPE_CATEGORY_CASE,
            rating_metric=Coalesce("rating", Value(0), output_field=IntegerField()),
        )
        .prefetch_related("tags")
    )

    if raw_query:
        for term in raw_query.split():
            queryset = queryset.filter(
                Q(name__icontains=term)
                | Q(overview__icontains=term)
                | Q(job_roles__icontains=term)
                | Q(authority__icontains=term)
                | Q(tags__name__icontains=term)
            )

    if selected_tag_ids:
        queryset = queryset.filter(tags__id__in=selected_tag_ids)

    if selected_types:
        queryset = queryset.filter(type_category__in=selected_types)

    rating_filters = Q()
    if difficulty_min > 0:
        rating_filters &= Q(rating__gte=difficulty_min)
    if difficulty_max < 10:
        rating_filters &= Q(rating__lte=difficulty_max)
    if rating_filters:
        queryset = queryset.filter(rating_filters)

    queryset = queryset.distinct()

    certificates = list(queryset)

    def compute_pass_metrics(cert_ids: list[int]) -> dict[int, dict[str, float | int | None]]:
        if not cert_ids:
            return {}
        stats_qs = (
            CertificateStatistics.objects.filter(certificate_id__in=cert_ids)
            .values(
                "certificate_id",
                "exam_type",
                "year",
                "registered",
                "applicants",
                "passers",
            )
        )

        stats_by_cert: dict[int, dict[str, dict[int, dict[str, int]]]] = defaultdict(lambda: defaultdict(dict))

        for stat in stats_qs:
            cert_id = stat["certificate_id"]
            stage_info = _classify_exam_stage(stat.get("exam_type"))
            if stage_info["key"] == "total":
                continue
            year_raw = stat.get("year")
            if year_raw in (None, ""):
                continue
            year_text = str(year_raw).strip()
            stage_order = stage_info["order"]
            year_map = stats_by_cert[cert_id].setdefault(year_text, {})
            entry = year_map.setdefault(stage_order, {"registered": 0, "applicants": 0, "passers": 0})
            for field in ("registered", "applicants", "passers"):
                value = stat.get(field)
                if value is None:
                    continue
                try:
                    entry[field] += int(value)
                except (TypeError, ValueError):
                    continue

        pass_rate_metrics: dict[int, dict[str, float | int | None]] = {}
        for cert_id, year_map in stats_by_cert.items():
            stage1_years: list[str] = []
            for year, stages in year_map.items():
                stage1_entry = stages.get(1)
                if not stage1_entry:
                    continue
                stage1_total = stage1_entry.get("applicants") or stage1_entry.get("registered") or 0
                if stage1_total:
                    stage1_years.append(year)

            pass_rate_value = None
            stage1_total_value = None

            if stage1_years:
                latest_year = max(stage1_years, key=_year_sort_key)
                stages = year_map[latest_year]
                stage1_entry = stages.get(1, {})
                stage1_total_value = (
                    stage1_entry.get("applicants")
                    or stage1_entry.get("registered")
                    or 0
                )
                if stage1_total_value:
                    final_stage_order = max(stages.keys())
                    final_entry = stages.get(final_stage_order, {})
                    final_passers = final_entry.get("passers") or 0
                    if stage1_total_value > 0 and final_passers is not None:
                        pass_rate_value = round(final_passers / stage1_total_value * 100, 1)

            pass_rate_metrics[cert_id] = {
                "pass_rate": pass_rate_value,
                "applicants": stage1_total_value,
            }

        return pass_rate_metrics

    metrics_map = compute_pass_metrics([cert.id for cert in certificates])

    for cert in certificates:
        metrics = metrics_map.get(cert.id, {})
        pass_rate_value = metrics.get("pass_rate")
        applicants_value = metrics.get("applicants")
        cert.pass_rate_metric = pass_rate_value
        cert.latest_pass_rate = pass_rate_value
        cert.applicants_metric = applicants_value

    if pass_rate_min > 0:
        certificates = [
            cert
            for cert in certificates
            if cert.pass_rate_metric is not None and cert.pass_rate_metric >= pass_rate_min
        ]
    if pass_rate_max < 100:
        certificates = [
            cert
            for cert in certificates
            if cert.pass_rate_metric is not None and cert.pass_rate_metric <= pass_rate_max
        ]

    if sort_key == "pass_rate":
        certificates.sort(
            key=lambda cert: (
                cert.pass_rate_metric is not None,
                cert.pass_rate_metric or 0,
                cert.name,
            ),
            reverse=True,
        )
    elif sort_key == "applicants":
        certificates.sort(
            key=lambda cert: (
                cert.applicants_metric is not None,
                cert.applicants_metric or 0,
                cert.name,
            ),
            reverse=True,
        )
    elif sort_key == "difficulty":
        certificates.sort(
            key=lambda cert: (
                cert.rating_metric or 0,
                cert.name,
            ),
            reverse=True,
        )
    else:
        certificates.sort(key=lambda cert: cert.name)

    paginator = Paginator(certificates, SEARCH_PAGE_SIZE)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)
    page_numbers = _build_page_numbers(page_obj)

    query_without_page = request.GET.copy()
    query_without_page.pop("page", None)
    base_querystring = query_without_page.urlencode()

    query_without_sort = query_without_page.copy()
    query_without_sort.pop("sort", None)
    sort_querystring = query_without_sort.urlencode()

    quick_tag_payload = [
        {"id": tag.id, "name": tag.name}
        for tag in tag_suggestions
    ]

    context = {
        "query": raw_query,
        "results_page": page_obj,
        "page_numbers": page_numbers,
        "total_count": paginator.count,
        "quick_tags": tag_suggestions,
        "quick_tag_payload": quick_tag_payload,
        "selected_tags": selected_tags,
        "selected_tag_ids": selected_tag_ids,
        "type_filters": TYPE_FILTERS,
        "selected_types": selected_types,
        "sort_options": SORT_OPTIONS,
        "selected_sort": sort_key,
        "difficulty_min": difficulty_min,
        "difficulty_max": difficulty_max,
        "pass_rate_min": pass_rate_min,
        "pass_rate_max": pass_rate_max,
        "base_querystring": base_querystring,
        "sort_querystring": sort_querystring,
    }

    return render(request, "search.html", context)


def certificate_statistics(request, slug="sample-cert"):
    certificate_obj = _get_certificate_by_slug(slug)
    certificate = _serialize_certificate(certificate_obj, slug)
    chart_payload, latest_snapshot = _build_statistics_payload(certificate_obj)

    years = chart_payload.get("years") or []
    year_range = None
    if years:
        year_range = years[0] if len(years) == 1 else f"{years[0]} ~ {years[-1]}"

    sessions = chart_payload.get("sessions", [])
    default_session_key = sessions[0]["key"] if sessions else None
    default_year = years[-1] if years else None

    context = {
        "certificate": certificate,
        "chart_payload": chart_payload,
        "chart_sessions": sessions,
        "has_statistics": bool(years),
        "year_range": year_range,
        "latest_snapshot": latest_snapshot,
        "total_label": (chart_payload.get("total") or {}).get("label", "전체"),
        "available_years": years,
        "default_year": default_year,
        "default_session_key": default_session_key,
    }
    return render(request, "certificate_statistics.html", context)


def certificate_detail(request, slug="sample-cert"):
    data = _certificate_sample_data(slug, review_limit=4)
    certificate_obj = data.pop("certificate_object", None)

    rating_form = RatingForm()
    existing_review = None
    if request.user.is_authenticated and certificate_obj:
        existing_review = Rating.objects.filter(
            user=request.user, certificate=certificate_obj
        ).first()
        if existing_review:
            rating_form = RatingForm(
                initial={
                    "difficulty": existing_review.perceived_score,
                    "content": existing_review.content,
                }
            )

    data.update(
        {
            "rating_form": rating_form,
            "existing_rating": existing_review,
        }
    )
    return render(request, "certificate_detail.html", data)


def certificate_reviews(request, slug="sample-cert"):
    page = request.GET.get("page") or 1
    data = _certificate_sample_data(slug, review_limit=None, review_page=page, per_page=8)
    certificate_obj = data.pop("certificate_object", None)

    rating_form = RatingForm()
    existing_review = None
    if request.user.is_authenticated and certificate_obj:
        existing_review = Rating.objects.filter(
            user=request.user, certificate=certificate_obj
        ).first()
        if existing_review:
            rating_form = RatingForm(
                initial={
                    "difficulty": existing_review.perceived_score,
                    "content": existing_review.content,
                }
            )

    data.update(
        {
            "reviews": data.get("reviews", []),
            "review_page_obj": data.get("review_page_obj"),
            "review_page_numbers": data.get("review_page_numbers"),
            "rating_form": rating_form,
            "existing_rating": existing_review,
        }
    )
    return render(request, "certificate_reviews.html", data)


def board_list(request, slug):
    certificate = _get_certificate_by_slug(slug)
    canonical_slug = _certificate_slug(certificate)
    if slug != canonical_slug:
        return redirect("board_list", slug=canonical_slug)

    queryset = (
        Post.objects.filter(certificate=certificate)
        .select_related("user")
        .annotate(
            comment_count=Count("comments", distinct=True),
            like_count=Count("likes", distinct=True),
        )
        .order_by("-created_at")
    )

    search_query = request.GET.get("q")
    if search_query:
        queryset = queryset.filter(Q(title__icontains=search_query) | Q(body__icontains=search_query))

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    query_without_page = request.GET.copy()
    query_without_page.pop("page", None)
    base_querystring = query_without_page.urlencode()

    holder_ids = _approved_holder_ids(certificate)
    for post in page_obj:
        post.user_is_certified = post.user_id in holder_ids
        post.board_slug = canonical_slug
        post.certificate_name = certificate.name
        post.detail_url = reverse("board_detail", args=[canonical_slug, post.id])

    context = {
        "board": {
            "title": certificate.name,
            "slug": canonical_slug,
            "certificate": certificate,
            "is_global": False,
        },
        "posts": page_obj,
        "page_obj": page_obj,
        "page_numbers": _build_page_numbers(page_obj),
        "search_query": search_query or "",
        "base_querystring": base_querystring,
    }
    return render(request, "board_list.html", context)


def board_all(request):
    search_query = request.GET.get("q")
    board_slug = request.GET.get("board")

    if board_slug and board_slug not in {"", "all"}:
        try:
            target_certificate = _get_certificate_by_slug(board_slug)
        except Http404:
            pass
        else:
            return redirect("board_list", slug=_certificate_slug(target_certificate))

    queryset = (
        Post.objects.select_related("certificate", "user")
        .annotate(
            comment_count=Count("comments", distinct=True),
            like_count=Count("likes", distinct=True),
        )
        .order_by("-created_at")
    )

    if search_query:
        queryset = queryset.filter(
            Q(title__icontains=search_query) | Q(body__icontains=search_query)
        )

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    certificate_ids = {post.certificate_id for post in page_obj if post.certificate_id}
    holder_map: dict[int, set[int]] = defaultdict(set)
    if certificate_ids:
        for cert_id, user_id in UserCertificate.objects.filter(
            certificate_id__in=certificate_ids,
            status=UserCertificate.STATUS_APPROVED,
        ).values_list("certificate_id", "user_id"):
            holder_map[cert_id].add(user_id)

    for post in page_obj:
        certificate_obj = post.certificate
        post.board_slug = _certificate_slug(certificate_obj) if certificate_obj else ""
        post.certificate_name = certificate_obj.name if certificate_obj else "게시판 미지정"
        if certificate_obj:
            post.user_is_certified = post.user_id in holder_map.get(certificate_obj.id, set())
            post.detail_url = reverse("board_detail", args=[post.board_slug, post.id])
        else:
            post.user_is_certified = False
            post.detail_url = ""

    query_without_page = request.GET.copy()
    query_without_page.pop("page", None)
    if query_without_page.get("board") in {None, "", "all"}:
        query_without_page.pop("board", None)
    base_querystring = query_without_page.urlencode()

    context = {
        "board": {"title": "전체", "slug": "all", "certificate": None, "is_global": True},
        "posts": page_obj,
        "page_obj": page_obj,
        "page_numbers": _build_page_numbers(page_obj),
        "search_query": search_query or "",
        "base_querystring": base_querystring,
    }
    return render(request, "board_list.html", context)


def board_detail(request, slug, post_id):
    certificate = _get_certificate_by_slug(slug)
    post = get_object_or_404(
        Post.objects.select_related("user", "certificate").prefetch_related("comments__user"),
        pk=post_id,
    )
    if post.certificate_id != certificate.id:
        raise Http404

    canonical_slug = _certificate_slug(certificate)
    if slug != canonical_slug:
        return redirect("board_detail", slug=canonical_slug, post_id=post.id)

    comments = post.comments.select_related("user").order_by("created_at")
    like_count = post.likes.count()
    is_liked = request.user.is_authenticated and post.likes.filter(user=request.user).exists()
    can_manage_post = request.user.is_authenticated and (
        request.user == post.user or request.user.is_staff
    )

    holder_ids = _approved_holder_ids(certificate)
    post.user_is_certified = post.user_id in holder_ids
    for comment in comments:
        comment.user_is_certified = comment.user_id in holder_ids

    if request.method == "POST":
        if not request.user.is_authenticated:
            login_url = reverse("login")
            return redirect(f"{login_url}?next={request.path}")

        comment_form = PostCommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.post = post
            comment.user = request.user
            comment.save()
            return redirect("board_detail", slug=canonical_slug, post_id=post.id)
    else:
        comment_form = PostCommentForm()

    context = {
        "board": {"title": certificate.name, "slug": canonical_slug, "certificate": certificate},
        "post": post,
        "comments": comments,
        "comment_form": comment_form,
        "like_count": like_count,
        "is_liked": is_liked,
        "can_manage_post": can_manage_post,
    }
    return render(request, "board_detail.html", context)


@login_required
def board_create(request):
    board_slug = request.GET.get("board")
    selected_certificate = None
    if board_slug:
        try:
            selected_certificate = _get_certificate_by_slug(board_slug)
        except Http404:
            selected_certificate = None

    selected_board_slug = _certificate_slug(selected_certificate) if selected_certificate else (board_slug or "")

    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            post.save()
            redirect_slug = _certificate_slug(post.certificate) if post.certificate else selected_board_slug
            return redirect("board_detail", slug=redirect_slug, post_id=post.id)

        posted_certificate_id = request.POST.get("certificate")
        if posted_certificate_id:
            try:
                selected_board_slug = _certificate_slug(Certificate.objects.get(pk=posted_certificate_id))
            except (ValueError, Certificate.DoesNotExist):
                pass
    else:
        initial = {}
        if selected_certificate:
            initial["certificate"] = selected_certificate
        form = PostForm(initial=initial)

    boards = [
        {"slug": _certificate_slug(cert), "name": cert.name, "id": cert.id}
        for cert in Certificate.objects.order_by("name")
    ]

    if not selected_board_slug and boards:
        selected_board_slug = boards[0]["slug"]

    context = {
        "form": form,
        "boards": boards,
        "selected_board": selected_board_slug,
        "form_title": "게시글 작성하기",
        "submit_label": "글쓰기",
        "cancel_url": None,
    }
    return render(request, "board_form.html", context)


@login_required
@require_POST
def board_toggle_like(request, slug, post_id):
    certificate = _get_certificate_by_slug(slug)
    post = get_object_or_404(Post.objects.select_related("certificate"), pk=post_id)
    if post.certificate_id != certificate.id:
        raise Http404

    like, created = PostLike.objects.get_or_create(post=post, user=request.user)
    if not created:
        like.delete()

    return redirect("board_detail", slug=_certificate_slug(certificate), post_id=post.id)


@login_required
def board_edit(request, slug, post_id):
    certificate = _get_certificate_by_slug(slug)
    post = get_object_or_404(Post.objects.select_related("certificate", "user"), pk=post_id)
    if post.certificate_id != certificate.id:
        raise Http404
    if request.user != post.user and not request.user.is_staff:
        return HttpResponseForbidden("수정 권한이 없습니다.")

    canonical_slug = _certificate_slug(certificate)
    if slug != canonical_slug:
        return redirect("board_edit", slug=canonical_slug, post_id=post.id)

    if request.method == "POST":
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            updated_post = form.save(commit=False)
            updated_post.user = post.user
            updated_post.save()
            form.save_m2m()
            target_slug = _certificate_slug(updated_post.certificate) if updated_post.certificate else canonical_slug
            return redirect("board_detail", slug=target_slug, post_id=post.id)
    else:
        form = PostForm(instance=post)

    boards = [
        {"slug": _certificate_slug(cert), "name": cert.name, "id": cert.id}
        for cert in Certificate.objects.order_by("name")
    ]

    context = {
        "form": form,
        "boards": boards,
        "selected_board": _certificate_slug(post.certificate) if post.certificate else canonical_slug,
        "form_title": "게시글 수정하기",
        "submit_label": "수정하기",
        "post_object": post,
        "cancel_url": reverse("board_detail", args=[canonical_slug, post.id]),
    }
    return render(request, "board_form.html", context)


@login_required
def board_delete(request, slug, post_id):
    certificate = _get_certificate_by_slug(slug)
    post = get_object_or_404(Post.objects.select_related("certificate", "user"), pk=post_id)
    if post.certificate_id != certificate.id:
        raise Http404
    if request.user != post.user and not request.user.is_staff:
        return HttpResponseForbidden("삭제 권한이 없습니다.")

    canonical_slug = _certificate_slug(certificate)
    if slug != canonical_slug:
        return redirect("board_delete", slug=canonical_slug, post_id=post.id)

    if request.method == "POST":
        redirect_slug = _certificate_slug(post.certificate) if post.certificate else canonical_slug
        post.delete()
        return redirect("board_list", slug=redirect_slug)

    context = {
        "board": {"title": certificate.name, "slug": canonical_slug},
        "post": post,
    }
    return render(request, "board_confirm_delete.html", context)
