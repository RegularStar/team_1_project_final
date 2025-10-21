import re
from collections import defaultdict
from typing import Iterable, List

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import (
    Case,
    Count,
    CharField,
    FloatField,
    IntegerField,
    Avg,
    F,
    ExpressionWrapper,
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

from certificates.models import Certificate, CertificateStatistics, CertificateTag, Tag, UserCertificate
from community.forms import PostForm, PostCommentForm
from community.models import Post, PostLike
from ratings.forms import RatingForm
from ratings.models import Rating
from ratings.services import certificate_rating_summary

STAR_RANGE = range(2, 12, 2)
FIVE_STAR_RANGE = range(1, 6)
AVATAR_COLORS = ["#7aa2ff", "#3ddc84", "#ffb74d", "#64b5f6", "#ff8a80", "#9575cd"]
MAJOR_PROFESSIONALS = [
    "변호사",
    "공인회계사",
    "변리사",
    "공인노무사",
    "세무사",
    "법무사",
    "감정평가사",
    "관세사",
]
HELL_BADGE_THRESHOLD = 9

SEARCH_PAGE_SIZE = 9
TAG_SUGGESTION_LIMIT = 12

TYPE_FILTERS = [
    ("국가기술자격", "국가기술자격"),
    ("국가전문자격", "국가전문자격"),
    ("민간자격", "민간자격"),
]

STAGE_FILTER_CHOICES = [
    ("", "전체"),
    ("1", "1차"),
    ("2", "2차"),
    ("3", "3차"),
    ("4", "4차"),
]

SORT_OPTIONS = [
    ("applicants", "응시자수"),
    ("name", "이름순"),
    ("difficulty", "난이도순"),
]

DEFAULT_SORT = "applicants"


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
    for value in (certificate_obj.authority, certificate_obj.type):
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

    tag_comparisons = _build_tag_comparison_payload(certificate_obj)

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
        return {"years": [], "total": None, "sessions": [], "tagComparisons": tag_comparisons}, None

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
        return {"years": [], "total": None, "sessions": [], "tagComparisons": tag_comparisons}, None

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
    payload["tagComparisons"] = tag_comparisons
    return payload, latest_snapshot


def _build_tag_comparison_payload(certificate_obj: Certificate):
    tags = list(certificate_obj.tags.all())
    if not tags:
        return []

    tag_ids = [tag.id for tag in tags if tag.id is not None]
    if not tag_ids:
        return []

    tag_certificates: dict[int, set[int]] = {tag_id: set() for tag_id in tag_ids}
    certificate_tags: dict[int, set[int]] = defaultdict(set)

    tag_links = CertificateTag.objects.filter(tag_id__in=tag_ids).values("tag_id", "certificate_id")
    for link in tag_links:
        tag_id = link.get("tag_id")
        certificate_id = link.get("certificate_id")
        if tag_id is None or certificate_id is None:
            continue
        tag_certificates.setdefault(tag_id, set()).add(certificate_id)
        certificate_tags.setdefault(certificate_id, set()).add(tag_id)

    all_certificate_ids = {certificate_obj.id}
    for cert_ids in tag_certificates.values():
        all_certificate_ids.update(cert_ids)

    if not all_certificate_ids:
        return []

    certificate_info: dict[int, dict[str, object]] = {}
    for cert in Certificate.objects.filter(id__in=all_certificate_ids):
        certificate_info[cert.id] = {
            "id": cert.id,
            "title": cert.name,
            "slug": _certificate_slug(cert),
        }

    stats_records = CertificateStatistics.objects.filter(certificate_id__in=all_certificate_ids).values(
        "certificate_id",
        "exam_type",
        "year",
        "registered",
        "applicants",
        "passers",
        "pass_rate",
    )

    tag_data: dict[int, dict[str, object]] = {
        tag_id: {"years": set(), "sessions": {}} for tag_id in tag_ids
    }

    for row in stats_records:
        certificate_id = row.get("certificate_id")
        if certificate_id is None:
            continue

        related_tags = certificate_tags.get(certificate_id)
        if not related_tags:
            continue

        year_raw = row.get("year")
        if not year_raw:
            continue
        year_text = str(year_raw).strip()
        if not year_text:
            continue

        stage_info = _classify_exam_stage(row.get("exam_type"))
        session_key = stage_info["key"]
        session_label = stage_info["label"]
        session_order = stage_info["order"]

        for tag_id in related_tags:
            if tag_id not in tag_data:
                continue

            entry = tag_data[tag_id]
            entry["years"].add(year_text)
            sessions = entry["sessions"]
            session_entry = sessions.setdefault(
                session_key,
                {"label": session_label, "order": session_order, "metrics": {}},
            )
            session_entry["label"] = session_label
            session_entry["order"] = session_order

            metrics_by_year = session_entry["metrics"].setdefault(year_text, {})
            cert_metrics = metrics_by_year.setdefault(
                certificate_id,
                {"registered": None, "applicants": None, "passers": None, "pass_rate": None},
            )

            for field in ("registered", "applicants", "passers"):
                value = row.get(field)
                if value in (None, ""):
                    continue
                try:
                    numeric = int(value)
                except (TypeError, ValueError):
                    try:
                        numeric = int(float(value))
                    except (TypeError, ValueError):
                        continue
                if cert_metrics[field] is None:
                    cert_metrics[field] = numeric
                else:
                    cert_metrics[field] += numeric

            rate_value = row.get("pass_rate")
            if rate_value not in (None, ""):
                try:
                    cert_metrics["pass_rate"] = float(rate_value)
                except (TypeError, ValueError):
                    pass

    for entry in tag_data.values():
        for session_entry in entry["sessions"].values():
            for metrics_by_year in session_entry["metrics"].values():
                for metrics in metrics_by_year.values():
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

    comparisons: list[dict[str, object]] = []

    for tag in tags:
        entry = tag_data.get(tag.id, {"years": set(), "sessions": {}})
        sessions_payload: list[dict[str, object]] = []
        for session_key, session_value in sorted(
            entry["sessions"].items(), key=lambda item: (item[1]["order"], item[0])
        ):
            metrics_by_year = session_value["metrics"]
            available_years = sorted(metrics_by_year.keys(), key=_year_sort_key)
            session_payload = {
                "key": session_key,
                "label": session_value["label"],
                "order": session_value["order"],
                "years": available_years,
                "metrics": {},
            }
            for year in available_years:
                per_certificate_metrics = []
                for cert_id in sorted(
                    metrics_by_year[year].keys(),
                    key=lambda cid: certificate_info.get(cid, {}).get("title", ""),
                ):
                    values = metrics_by_year[year][cert_id]
                    info = certificate_info.get(cert_id)
                    if not info:
                        continue
                    per_certificate_metrics.append(
                        {
                            "certificateId": cert_id,
                            "title": info["title"],
                            "slug": info["slug"],
                            "registered": values.get("registered"),
                            "applicants": values.get("applicants"),
                            "passers": values.get("passers"),
                            "pass_rate": values.get("pass_rate"),
                            "isPrimary": cert_id == certificate_obj.id,
                        }
                    )
                session_payload["metrics"][year] = per_certificate_metrics
            sessions_payload.append(session_payload)

        years_sorted = sorted(entry["years"], key=_year_sort_key)

        default_session_key = None
        default_year = None
        for session_payload in sessions_payload:
            if session_payload["metrics"] and default_session_key is None:
                default_session_key = session_payload["key"]
            year_candidates = [year for year, rows in session_payload["metrics"].items() if rows]
            if year_candidates and default_year is None:
                default_year = sorted(year_candidates, key=_year_sort_key)[-1]
        if default_year is None and years_sorted:
            default_year = years_sorted[-1]

        comparisons.append(
            {
                "id": tag.id,
                "name": tag.name,
                "sessions": sessions_payload,
                "years": years_sorted,
                "defaultSessionKey": default_session_key,
                "defaultYear": default_year,
            }
        )

    return comparisons


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


def _display_name(user) -> str:
    if not user:
        return ""
    for attr in ("username", "name"):
        value = getattr(user, attr, "")
        if value:
            return value
    full_name = user.get_full_name() if hasattr(user, "get_full_name") else ""
    if full_name:
        return full_name
    email = getattr(user, "email", "")
    if email:
        return email
    return "사용자"


def _is_hell_certificate(certificate: Certificate) -> bool:
    rating = certificate.rating
    try:
        return rating is not None and float(rating) >= HELL_BADGE_THRESHOLD
    except (TypeError, ValueError):
        return False


def _is_elite_certificate(certificate: Certificate) -> bool:
    name = (certificate.name or "").strip()
    return name in MAJOR_PROFESSIONALS


def _build_user_badge_counts(user_ids: Iterable[int]) -> dict[int, dict[str, int]]:
    user_ids = {user_id for user_id in user_ids if user_id is not None}
    if not user_ids:
        return {}

    badges: dict[int, dict[str, int]] = {}
    records = (
        UserCertificate.objects.select_related("certificate")
        .filter(user_id__in=user_ids, status=UserCertificate.STATUS_APPROVED)
    )
    for record in records:
        certificate = record.certificate
        if certificate is None:
            continue
        summary = badges.setdefault(record.user_id, {"hell": 0, "elite": 0})
        if _is_hell_certificate(certificate):
            summary["hell"] += 1
        if _is_elite_certificate(certificate):
            summary["elite"] += 1
    # ensure all requested ids exist in map
    for user_id in user_ids:
        badges.setdefault(user_id, {"hell": 0, "elite": 0})
    return badges


def build_rating_context(
    certificate: Certificate,
    *,
    review_limit: int | None = 4,
    page: int | None = None,
    per_page: int = 8,
    user=None,
    user_can_review: bool = False,
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

    review_records = list(reviews_iter)
    badge_counts = _build_user_badge_counts(review.user_id for review in review_records)

    holder_ids = _approved_holder_ids(certificate)

    def to_review(review: Rating):
        rating10 = review.perceived_score
        display_name = _display_name(review.user)
        can_edit = bool(
            user_can_review and user and user.is_authenticated and review.user_id == user.id
        )
        badge_summary = badge_counts.get(review.user_id, {"hell": 0, "elite": 0})
        return {
            "id": review.id,
            "difficulty_display": rating10,
            "title": review.certificate.name,
            "comment": review.content or "작성된 후기가 없습니다.",
            "comment_raw": review.content or "",
            "nickname": display_name,
            "date": review.created_at.strftime("%Y-%m-%d"),
            "avatar_color": avatar_color_for_user(review.user_id),
            "avatar_url": None,
            "initial": display_name[:1].upper(),
            "is_certified": review.user_id in holder_ids,
            "can_edit": can_edit,
            "hell_count": badge_summary.get("hell", 0),
            "elite_count": badge_summary.get("elite", 0),
        }

    reviews = [to_review(review) for review in review_records]

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
    user=None,
):
    certificate_obj = _get_certificate_by_slug(slug)
    certificate = _serialize_certificate(certificate_obj, slug)

    user_can_review = False
    if user is not None and getattr(user, "is_authenticated", False) and certificate_obj:
        user_can_review = UserCertificate.objects.filter(
            user=user,
            certificate=certificate_obj,
            status=UserCertificate.STATUS_APPROVED,
        ).exists()

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
        user=user,
        user_can_review=user_can_review,
    )

    summary = rating_context["summary"]
    official_difficulty = float(certificate.get("difficulty") or 0)
    user_average = float(summary.get("average") or 0)
    user_count = summary.get("total") or 0

    badges = []
    if official_difficulty >= 9 and user_average >= 9 and user_count > 0:
        badges.append({"label": "지옥의 자격증", "variant": "hell"})
    if (certificate.get("title") or "").strip() in MAJOR_PROFESSIONALS:
        badges.append({"label": "8대 전문직", "variant": "elite"})
    certificate["badges"] = badges

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
        "user_can_review": user_can_review,
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

    difficulty_official_min = _parse_number(
        request.GET.get("difficulty_official_min") or request.GET.get("difficulty_min"),
        default=0,
        minimum=0,
        maximum=10,
    )
    difficulty_official_max = _parse_number(
        request.GET.get("difficulty_official_max") or request.GET.get("difficulty_max"),
        default=10,
        minimum=0,
        maximum=10,
    )
    if difficulty_official_min > difficulty_official_max:
        difficulty_official_min, difficulty_official_max = difficulty_official_max, difficulty_official_min

    difficulty_user_min = _parse_number(
        request.GET.get("difficulty_user_min"),
        default=0,
        minimum=0,
        maximum=10,
    )
    difficulty_user_max = _parse_number(
        request.GET.get("difficulty_user_max"),
        default=10,
        minimum=0,
        maximum=10,
    )
    if difficulty_user_min > difficulty_user_max:
        difficulty_user_min, difficulty_user_max = difficulty_user_max, difficulty_user_min

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

    pass_rate_stage_param = (request.GET.get("pass_rate_stage") or "").strip()
    try:
        pass_rate_stage = int(pass_rate_stage_param) if pass_rate_stage_param else None
    except (TypeError, ValueError):
        pass_rate_stage = None

    applicants_min_value = request.GET.get("applicants_min")
    applicants_max_value = request.GET.get("applicants_max")

    applicants_min = None
    if applicants_min_value not in (None, ""):
        applicants_min = _parse_number(
            applicants_min_value,
            default=0,
            minimum=0,
        )

    applicants_max = None
    if applicants_max_value not in (None, ""):
        applicants_max = _parse_number(
            applicants_max_value,
            default=0,
            minimum=0,
        )

    if (
        applicants_min is not None
        and applicants_max is not None
        and applicants_min > applicants_max
    ):
        applicants_min, applicants_max = applicants_max, applicants_min

    applicants_stage_param = (request.GET.get("applicants_stage") or "").strip()
    try:
        applicants_stage = int(applicants_stage_param) if applicants_stage_param else None
    except (TypeError, ValueError):
        applicants_stage = None

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
    if difficulty_official_min > 0:
        rating_filters &= Q(rating__gte=difficulty_official_min)
    if difficulty_official_max < 10:
        rating_filters &= Q(rating__lte=difficulty_official_max)
    if rating_filters:
        queryset = queryset.filter(rating_filters)

    queryset = queryset.distinct()

    certificates = list(queryset)

    def compute_pass_metrics(cert_ids: list[int]) -> dict[int, dict[str, object]]:
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

        stats_by_cert: dict[int, dict[str, dict[int, dict[str, int | str]]]] = defaultdict(lambda: defaultdict(dict))

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
            entry = year_map.setdefault(
                stage_order,
                {
                    "label": stage_info["label"],
                    "order": stage_order,
                    "registered": 0,
                    "applicants": 0,
                    "passers": 0,
                },
            )
            for field in ("registered", "applicants", "passers"):
                value = stat.get(field)
                if value is None:
                    continue
                try:
                    entry[field] += int(value)
                except (TypeError, ValueError):
                    continue

        metrics_by_cert: dict[int, dict[str, object]] = {}
        for cert_id, year_map in stats_by_cert.items():
            if not year_map:
                metrics_by_cert[cert_id] = {
                    "pass_rate": None,
                    "applicants": None,
                    "baseline_year": None,
                    "stages": [],
                    "stage_lookup": {},
                }
                continue

            latest_year = max(year_map.keys(), key=_year_sort_key)
            stages_for_year = year_map.get(latest_year, {})

            stage_orders = sorted(stages_for_year.keys())
            stage_metrics_list: list[dict[str, object]] = []
            stage_lookup: dict[int, dict[str, object]] = {}
            stage1_total_value = None
            pass_rate_value = None

            if stage_orders:
                stage1_order = 1 if 1 in stages_for_year else stage_orders[0]
                stage1_entry = stages_for_year.get(stage1_order, {})
                stage1_total_value = stage1_entry.get("applicants")
                if stage1_total_value is None:
                    stage1_total_value = stage1_entry.get("registered")

                final_stage_order = stage_orders[-1]
                final_entry = stages_for_year.get(final_stage_order, {})
                final_passers = final_entry.get("passers")

                for order in stage_orders:
                    entry = stages_for_year[order]
                    applicants_total = entry.get("applicants")
                    if applicants_total is None:
                        applicants_total = entry.get("registered")
                    passers_total = entry.get("passers")
                    pass_rate_stage = None
                    if applicants_total not in (None, 0) and passers_total is not None:
                        try:
                            pass_rate_stage = round(passers_total / applicants_total * 100, 1)
                        except ZeroDivisionError:
                            pass_rate_stage = None

                    stage_data = {
                        "order": order,
                        "label": entry.get("label") or f"{order}차",
                        "applicants": applicants_total,
                        "pass_rate": pass_rate_stage,
                    }
                    stage_metrics_list.append(stage_data)
                    stage_lookup[order] = stage_data

                if (
                    stage1_total_value not in (None, 0)
                    and final_passers is not None
                    and stage1_total_value
                ):
                    try:
                        pass_rate_value = round(final_passers / stage1_total_value * 100, 1)
                    except ZeroDivisionError:
                        pass_rate_value = None

            metrics_by_cert[cert_id] = {
                "pass_rate": pass_rate_value,
                "applicants": stage1_total_value,
                "baseline_year": latest_year,
                "stages": stage_metrics_list,
                "stage_lookup": stage_lookup,
            }

        return metrics_by_cert

    cert_ids = [cert.id for cert in certificates]
    metrics_map = compute_pass_metrics(cert_ids)

    ratings_map: dict[int, dict[str, float | int | None]] = {}
    if cert_ids:
        rating_rows = (
            Rating.objects.filter(certificate_id__in=cert_ids)
            .values("certificate_id")
            .annotate(
                average=Avg(
                    Case(
                        When(rating__gt=5, then=F("rating")),
                        default=ExpressionWrapper(F("rating") * 2, output_field=FloatField()),
                        output_field=FloatField(),
                    )
                ),
                count=Count("id"),
            )
        )
        ratings_map = {
            row["certificate_id"]: {
                "average": row["average"],
                "count": row["count"],
            }
            for row in rating_rows
        }

    for cert in certificates:
        metrics = metrics_map.get(cert.id, {})
        pass_rate_value = metrics.get("pass_rate")
        applicants_value = metrics.get("applicants")
        cert.pass_rate_metric = pass_rate_value
        cert.latest_pass_rate = pass_rate_value
        cert.applicants_metric = applicants_value
        cert.stage_statistics = metrics.get("stages") or []
        cert.stage_metrics_lookup = metrics.get("stage_lookup") or {}
        cert.stats_baseline_year = metrics.get("baseline_year")

        rating_stats = ratings_map.get(cert.id, {})
        user_average = rating_stats.get("average")
        if user_average is not None:
            try:
                user_average = round(float(user_average), 1)
            except (TypeError, ValueError):
                user_average = None
        cert.user_difficulty_average = user_average
        cert.user_difficulty_count = rating_stats.get("count") or 0
        if cert.user_difficulty_count == 0:
            cert.user_difficulty_average = None

    if difficulty_user_min > 0 or difficulty_user_max < 10:
        filtered_by_user_difficulty: list[Certificate] = []
        for cert in certificates:
            avg = getattr(cert, "user_difficulty_average", None)
            if avg is None:
                continue
            if avg < difficulty_user_min:
                continue
            if avg > difficulty_user_max:
                continue
            filtered_by_user_difficulty.append(cert)
        certificates = filtered_by_user_difficulty

    def resolve_pass_rate(cert):
        if pass_rate_stage:
            stage_entry = cert.stage_metrics_lookup.get(pass_rate_stage)
            if stage_entry:
                return stage_entry.get("pass_rate")
            return None
        return cert.pass_rate_metric

    def resolve_applicants(cert):
        if applicants_stage:
            stage_entry = cert.stage_metrics_lookup.get(applicants_stage)
            if stage_entry:
                return stage_entry.get("applicants")
            return None
        return cert.applicants_metric

    if pass_rate_min > 0:
        filtered = []
        for cert in certificates:
            value = resolve_pass_rate(cert)
            if value is None:
                continue
            if value >= pass_rate_min:
                filtered.append(cert)
        certificates = filtered

    if pass_rate_max < 100:
        filtered = []
        for cert in certificates:
            value = resolve_pass_rate(cert)
            if value is None:
                continue
            if value <= pass_rate_max:
                filtered.append(cert)
        certificates = filtered

    if applicants_min is not None:
        filtered = []
        for cert in certificates:
            value = resolve_applicants(cert)
            if value is None:
                continue
            if value >= applicants_min:
                filtered.append(cert)
        certificates = filtered

    if applicants_max is not None:
        filtered = []
        for cert in certificates:
            value = resolve_applicants(cert)
            if value is None:
                continue
            if value <= applicants_max:
                filtered.append(cert)
        certificates = filtered

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

    CHUNK_SIZE = 5
    current_chunk_index = (page_obj.number - 1) // CHUNK_SIZE
    chunk_start = current_chunk_index * CHUNK_SIZE + 1
    chunk_end = min(chunk_start + CHUNK_SIZE - 1, paginator.num_pages)
    page_chunk = list(range(chunk_start, chunk_end + 1))

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

    applicants_min_display = "" if applicants_min is None else int(applicants_min)
    applicants_max_display = "" if applicants_max is None else int(applicants_max)

    context = {
        "query": raw_query,
        "results_page": page_obj,
        "page_numbers": page_numbers,
        "page_chunk": page_chunk,
        "total_count": paginator.count,
        "quick_tags": tag_suggestions,
        "quick_tag_payload": quick_tag_payload,
        "selected_tags": selected_tags,
        "selected_tag_ids": selected_tag_ids,
        "type_filters": TYPE_FILTERS,
        "selected_types": selected_types,
        "sort_options": SORT_OPTIONS,
        "selected_sort": sort_key,
        "difficulty_official_min": difficulty_official_min,
        "difficulty_official_max": difficulty_official_max,
        "difficulty_user_min": difficulty_user_min,
        "difficulty_user_max": difficulty_user_max,
        "pass_rate_min": pass_rate_min,
        "pass_rate_max": pass_rate_max,
        "pass_rate_stage": pass_rate_stage_param,
        "applicants_min": applicants_min_display,
        "applicants_max": applicants_max_display,
        "applicants_stage": applicants_stage_param,
        "stage_filter_choices": STAGE_FILTER_CHOICES,
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
        "tag_comparisons": chart_payload.get("tagComparisons") or [],
    }
    return render(request, "certificate_statistics.html", context)


def certificate_detail(request, slug="sample-cert"):
    data = _certificate_sample_data(slug, review_limit=4, user=request.user)
    certificate_obj = data.pop("certificate_object", None)
    can_submit_review = data.get("user_can_review", False)

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
            "can_submit_review": can_submit_review,
        }
    )
    return render(request, "certificate_detail.html", data)


def certificate_reviews(request, slug="sample-cert"):
    page = request.GET.get("page") or 1
    data = _certificate_sample_data(
        slug,
        review_limit=None,
        review_page=page,
        per_page=8,
        user=request.user,
    )
    certificate_obj = data.pop("certificate_object", None)
    can_submit_review = data.get("user_can_review", False)

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
            "can_submit_review": can_submit_review,
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
    user_badges = _build_user_badge_counts(post.user_id for post in page_obj)
    for post in page_obj:
        post.user_is_certified = post.user_id in holder_ids
        post.board_slug = canonical_slug
        post.certificate_name = certificate.name
        post.detail_url = reverse("board_detail", args=[canonical_slug, post.id])
        badge_summary = user_badges.get(post.user_id, {"hell": 0, "elite": 0})
        post.user_hell_count = badge_summary.get("hell", 0)
        post.user_elite_count = badge_summary.get("elite", 0)
        post.user_display_name = _display_name(post.user)

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

    user_badges = _build_user_badge_counts(post.user_id for post in page_obj)

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
        badge_summary = user_badges.get(post.user_id, {"hell": 0, "elite": 0})
        post.user_hell_count = badge_summary.get("hell", 0)
        post.user_elite_count = badge_summary.get("elite", 0)
        post.user_display_name = _display_name(post.user)

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
    badge_counts = _build_user_badge_counts(
        [post.user_id, *[comment.user_id for comment in comments]]
    )
    post.user_is_certified = post.user_id in holder_ids
    post_badges = badge_counts.get(post.user_id, {"hell": 0, "elite": 0})
    post.user_hell_count = post_badges.get("hell", 0)
    post.user_elite_count = post_badges.get("elite", 0)
    post.user_display_name = _display_name(post.user)
    for comment in comments:
        comment.user_is_certified = comment.user_id in holder_ids
        comment_badges = badge_counts.get(comment.user_id, {"hell": 0, "elite": 0})
        comment.user_hell_count = comment_badges.get("hell", 0)
        comment.user_elite_count = comment_badges.get("elite", 0)
        comment.user_display_name = _display_name(comment.user)

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
