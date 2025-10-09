import re
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

from certificates.models import Certificate, CertificateStatistics, Tag
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

    def _split_roles(raw_value: str):
        if not raw_value:
            return []

        normalized = str(raw_value).replace("\r\n", "\n")
        lines = [line.strip() for line in normalized.split("\n") if line.strip()]

        items = []
        current = None
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

    tag_names = list(certificate_obj.tags.order_by("name").values_list("name", flat=True))
    primary_tag = tag_names[0] if tag_names else None

    latest_stat = (
        CertificateStatistics.objects.filter(certificate=certificate_obj)
        .order_by("-year", "-session")
        .first()
    )
    pass_rate = float(latest_stat.pass_rate) if latest_stat and latest_stat.pass_rate is not None else None

    category_value = primary_tag or certificate_obj.type or "자격증"
    meta_parts = []
    for value in (category_value, certificate_obj.authority, certificate_obj.type):
        if value and value not in meta_parts:
            meta_parts.append(value)

    roles_list = _split_roles(certificate_obj.job_roles)
    roles_is_list = len(roles_list) > 1 or (
        roles_list
        and str(certificate_obj.job_roles or "").strip().startswith(("-", "•", "▪"))
    )

    certificate = {
        "id": certificate_obj.id,
        "slug": slug,
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
        "overview": certificate_obj.overview or "",
        "roles": roles_list,
        "roles_is_list": roles_is_list,
        "roles_text": certificate_obj.job_roles or "",
        "exam_method": certificate_obj.exam_method or "",
        "eligibility": certificate_obj.eligibility or "",
        "homepage": certificate_obj.homepage or "",
    }

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
    return render(request, "home.html")


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

    latest_stats = CertificateStatistics.objects.filter(certificate_id=OuterRef("pk")).order_by(
        "-year", "-session", "-id"
    )

    latest_pass_rate = Subquery(
        latest_stats.values("pass_rate")[:1],
        output_field=FloatField(),
    )
    latest_applicants = Subquery(
        latest_stats.values("applicants")[:1],
        output_field=IntegerField(),
    )
    latest_registered = Subquery(
        latest_stats.values("registered")[:1],
        output_field=IntegerField(),
    )

    queryset = (
        Certificate.objects.all()
        .annotate(
            type_category=TYPE_CATEGORY_CASE,
            latest_pass_rate=latest_pass_rate,
            latest_applicants=latest_applicants,
            latest_registered=latest_registered,
            pass_rate_metric=Coalesce(
                latest_pass_rate, Value(0.0), output_field=FloatField()
            ),
            applicants_metric=Coalesce(
                latest_applicants,
                latest_registered,
                Value(0),
                output_field=IntegerField(),
            ),
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

    pass_rate_filters = Q()
    if pass_rate_min > 0:
        pass_rate_filters &= Q(pass_rate_metric__gte=pass_rate_min)
    if pass_rate_max < 100:
        pass_rate_filters &= Q(pass_rate_metric__lte=pass_rate_max)
    if pass_rate_filters:
        queryset = queryset.filter(pass_rate_filters)

    queryset = queryset.distinct()

    sort_map = {
        "pass_rate": ("-pass_rate_metric", "-applicants_metric", "name"),
        "applicants": ("-applicants_metric", "-pass_rate_metric", "name"),
        "name": ("name",),
        "difficulty": ("-rating_metric", "name"),
    }
    order_by = sort_map.get(sort_key, sort_map[DEFAULT_SORT]) + ("id",)
    queryset = queryset.order_by(*order_by)

    paginator = Paginator(queryset, SEARCH_PAGE_SIZE)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)
    page_numbers = _build_page_numbers(page_obj)

    query_without_page = request.GET.copy()
    query_without_page.pop("page", None)
    base_querystring = query_without_page.urlencode()

    query_without_sort = query_without_page.copy()
    query_without_sort.pop("sort", None)
    sort_querystring = query_without_sort.urlencode()

    context = {
        "query": raw_query,
        "results_page": page_obj,
        "page_numbers": page_numbers,
        "total_count": paginator.count,
        "quick_tags": tag_suggestions,
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

    context = {
        "board": {"title": certificate.name, "slug": canonical_slug, "certificate": certificate},
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
