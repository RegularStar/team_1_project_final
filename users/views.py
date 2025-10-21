<<<<<<< HEAD
from django.contrib.auth import get_user_model, login, logout
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from rest_framework import generics, permissions
from rest_framework.response import Response

from .forms import SignInForm, SignUpForm
=======
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse, reverse_lazy
from django.views import View
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from django.utils.text import slugify

from certificates.models import Certificate, Tag, UserCertificate, UserTag
from ai.models import SupportInquiry
from certificates.views import (
    CertificatePhaseViewSet,
    CertificateStatisticsViewSet,
    CertificateViewSet,
    TagViewSet,
)
from .forms import (
    AdminExcelUploadForm,
    InterestKeywordForm,
    SignInForm,
    SignUpForm,
    UserCertificateRequestForm,
)
>>>>>>> seil2
from .serializers import UserCreateSerializer, UserSerializer

User = get_user_model()


<<<<<<< HEAD
=======
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


def _public_display_name(user) -> str:
    if not user:
        return ""
    for attr in ("username", "name"):
        value = getattr(user, attr, "")
        if value:
            return value
    if hasattr(user, "get_full_name"):
        full_name = user.get_full_name()
        if full_name:
            return full_name
    email = getattr(user, "email", "")
    if email:
        return email.split("@")[0]
    return "사용자"


def _avatar_color_for_user(user_id: int | None) -> str:
    if not user_id:
        return AVATAR_COLORS[0]
    return AVATAR_COLORS[user_id % len(AVATAR_COLORS)]


def _certificate_slug(cert: Certificate) -> str:
    slug_text = slugify(cert.name)
    return slug_text or str(cert.pk)


def _is_hell_certificate(cert: Certificate) -> bool:
    rating = cert.rating
    try:
        return rating is not None and float(rating) >= HELL_BADGE_THRESHOLD
    except (TypeError, ValueError):
        return False


def _is_elite_certificate(cert: Certificate) -> bool:
    name = (cert.name or "").strip()
    return name in MAJOR_PROFESSIONALS


class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = False

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        return render(
            self.request,
            "users/access_denied.html",
            {
                "exception": None,
                "redirect_url": reverse_lazy("login"),
            },
            status=403,
        )


>>>>>>> seil2
class RegisterView(generics.CreateAPIView):
    """POST /api/users/register/"""

    serializer_class = UserCreateSerializer
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveAPIView):
    """GET /api/users/me/ (JWT 필요)"""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class SignInView(View):
    template_name = "users/login.html"
    form_class = SignInForm
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = self.form_class(request=request)
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = self.form_class(request=request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect(request.GET.get("next") or self.success_url)
        return render(request, self.template_name, {"form": form})


class SignUpView(View):
    template_name = "users/register.html"
    form_class = SignUpForm
    success_url = reverse_lazy("mypage")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect(self.success_url)
        return render(request, self.template_name, {"form": form})


class LogoutView(View):
    def post(self, request):
<<<<<<< HEAD
        logout(request)
        return redirect("home")
=======
        next_url = request.POST.get("next") or request.GET.get("next")
        logout(request)
        return redirect(resolve_url(next_url or "home"))


class UserPublicProfileView(View):
    template_name = "users/public_profile.html"

    def get(self, request, user_id):
        profile_user = get_object_or_404(
            User.objects.prefetch_related("user_tags__tag", "user_certificates__certificate"),
            pk=user_id,
        )

        tag_entries = [
            {
                "id": user_tag.tag_id,
                "name": user_tag.tag.name,
            }
            for user_tag in profile_user.user_tags.select_related("tag").order_by("tag__name")
            if user_tag.tag is not None
        ]

        certificate_records = (
            profile_user.user_certificates.select_related("certificate")
            .filter(status=UserCertificate.STATUS_APPROVED)
            .order_by("-acquired_at", "-created_at")
        )

        certificates = []
        hell_count = 0
        elite_count = 0

        for record in certificate_records:
            certificate = record.certificate
            if certificate is None:
                continue
            is_hell = _is_hell_certificate(certificate)
            is_elite = _is_elite_certificate(certificate)
            if is_hell:
                hell_count += 1
            if is_elite:
                elite_count += 1

            certificates.append(
                {
                    "id": certificate.id,
                    "name": certificate.name,
                    "slug": _certificate_slug(certificate),
                    "type": certificate.type,
                    "rating": certificate.rating,
                    "acquired_at": record.acquired_at,
                    "created_at": record.created_at,
                    "is_hell": is_hell,
                    "is_elite": is_elite,
                }
            )

        special_summary = []
        if hell_count:
            special_summary.append(f"지옥의 자격증 {hell_count}개")
        if elite_count:
            special_summary.append(f"8대 전문직 {elite_count}개")

        context = {
            "profile_user": profile_user,
            "display_name": _public_display_name(profile_user),
            "avatar_color": _avatar_color_for_user(profile_user.id),
            "tag_entries": tag_entries,
            "tag_count": len(tag_entries),
            "certificates": certificates,
            "certificate_count": len(certificates),
            "hell_count": hell_count,
            "elite_count": elite_count,
            "special_summary": special_summary,
            "is_self": request.user.is_authenticated and request.user.id == profile_user.id,
        }
        return render(request, self.template_name, context)
>>>>>>> seil2


class MyPageView(View):
    template_name = "users/mypage.html"
<<<<<<< HEAD
=======
    interest_form_class = InterestKeywordForm
    certificate_form_class = UserCertificateRequestForm
>>>>>>> seil2

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        return super().dispatch(request, *args, **kwargs)

<<<<<<< HEAD
    def get(self, request):
        user = request.user
        context = {
            "user": user,
        }
        return render(request, self.template_name, context)
=======
    def _build_context(self, request, interest_form=None, certificate_form=None):
        interest_form = interest_form or self.interest_form_class()
        certificate_form = certificate_form or self.certificate_form_class()

        user_tags = request.user.user_tags.select_related("tag").order_by("tag__name")
        tag_ids = [item.tag_id for item in user_tags]

        related_tags = Tag.objects.none()
        if tag_ids:
            related_certificate_ids = list(
                Certificate.objects.filter(tags__in=tag_ids)
                .values_list("id", flat=True)
                .distinct()
            )

            if related_certificate_ids:
                related_tags = (
                    Tag.objects.filter(certificates__id__in=related_certificate_ids)
                    .exclude(id__in=tag_ids)
                    .annotate(
                        certificate_count=Count(
                            "certificates",
                            filter=Q(certificates__id__in=related_certificate_ids),
                            distinct=True,
                        )
                    )
                    .distinct()
                    .order_by("-certificate_count", "name")[:12]
                )

        if not tag_ids:
            related_tags = (
                Tag.objects.annotate(certificate_count=Count("certificates", distinct=True))
                .order_by("-certificate_count", "name")[:12]
            )

        user_certificates = (
            request.user.user_certificates.select_related("certificate", "reviewed_by")
            .order_by("-created_at")
        )

        selected_certificate = None
        certificate_value = certificate_form["certificate"].value()
        if certificate_value:
            try:
                selected_certificate = Certificate.objects.get(pk=certificate_value)
            except Certificate.DoesNotExist:
                selected_certificate = None

        return {
            "user": request.user,
            "interest_form": interest_form,
            "certificate_form": certificate_form,
            "interest_tags": user_tags,
            "tag_suggestions": related_tags,
            "user_certificates": user_certificates,
            "selected_certificate": selected_certificate,
        }

    def get(self, request):
        context = self._build_context(request)
        return render(request, self.template_name, context)

    def post(self, request):
        form_type = request.POST.get("form")

        if form_type == "remove_tag":
            tag_id = request.POST.get("remove_tag")
            user_tag = request.user.user_tags.filter(tag_id=tag_id).first()
            if user_tag:
                user_tag.delete()
                messages.success(request, "관심 태그를 삭제했어요.")
            else:
                messages.warning(request, "이미 삭제된 태그예요.")
            return redirect("mypage")

        if form_type == "add_tag":
            interest_form = self.interest_form_class(request.POST)
            if interest_form.is_valid():
                keyword = interest_form.cleaned_data["keyword"]
                tag, _ = Tag.objects.get_or_create(name=keyword)
                try:
                    UserTag.objects.get_or_create(user=request.user, tag=tag)
                except IntegrityError:
                    messages.info(request, "이미 등록된 태그예요.")
                else:
                    messages.success(request, "관심 태그를 추가했어요.")
                return redirect("mypage")

            context = self._build_context(request, interest_form=interest_form)
            messages.error(request, "관심 태그를 다시 확인해주세요.")
            return render(request, self.template_name, context)

        if form_type == "remove_certificate":
            certificate_id = request.POST.get("certificate_id")
            record = request.user.user_certificates.filter(id=certificate_id).first()
            if record:
                record.delete()
                messages.success(request, "자격증 정보를 삭제했어요.")
            else:
                messages.warning(request, "이미 삭제된 자격증이에요.")
            return redirect("mypage")

        if form_type == "add_certificate":
            certificate_form = self.certificate_form_class(request.POST, request.FILES)
            if certificate_form.is_valid():
                certificate = certificate_form.cleaned_data["certificate"]
                acquired_at = certificate_form.cleaned_data.get("acquired_at")
                evidence = certificate_form.cleaned_data.get("evidence")

                record, created = UserCertificate.objects.get_or_create(
                    user=request.user,
                    certificate=certificate,
                    defaults={
                        "acquired_at": acquired_at,
                        "evidence": evidence,
                        "status": UserCertificate.STATUS_PENDING,
                    },
                )

                if not created:
                    if acquired_at:
                        record.acquired_at = acquired_at
                    else:
                        record.acquired_at = None
                    if evidence:
                        record.evidence = evidence
                    record.status = UserCertificate.STATUS_PENDING
                    record.review_note = ""
                    record.reviewed_by = None
                    record.reviewed_at = None
                    record.save(
                        update_fields=[
                            "acquired_at",
                            "evidence",
                            "status",
                            "review_note",
                            "reviewed_by",
                            "reviewed_at",
                        ]
                    )

                    messages.success(request, "자격증 정보를 다시 심사 요청했어요.")
                else:
                    messages.success(request, "자격증 인증을 신청했어요. 관리자 확인 후 등록됩니다.")
                return redirect("mypage")

            context = self._build_context(
                request,
                interest_form=self.interest_form_class(),
                certificate_form=certificate_form,
            )
            messages.error(request, "자격증 인증 신청 정보를 다시 확인해주세요.")
            return render(request, self.template_name, context)

        # 기본적으로는 태그 추가 실패와 동일하게 처리
        interest_form = self.interest_form_class(request.POST or None)
        context = self._build_context(request, interest_form=interest_form)
        messages.error(request, "요청을 처리하지 못했어요. 다시 시도해주세요.")
        return render(request, self.template_name, context)


class ManageHomeView(SuperuserRequiredMixin, View):
    template_name = "manage/home.html"

    quick_links = [
        {
            "title": "관리자 업로드 허브",
            "description": "자격증과 태그, 통계 데이터를 엑셀로 일괄 업데이트하세요.",
            "url_name": "manage_uploads",
        },
        {
            "title": "사용자 자격증 등록요청",
            "description": "사용자가 제출한 자격증 인증 요청을 검토하고 승인합니다.",
            "url_name": "certificate_review",
        },
        {
            "title": "사용자 문의 검토",
            "description": "챗봇에서 접수된 문의와 요청을 확인하고 처리합니다.",
            "url_name": "manage_support_inquiries",
        },
        {
            "title": "유저 관리",
            "description": "회원 정보와 권한을 Django Admin에서 관리합니다.",
            "url_name": "admin:users_user_changelist",
        },
    ]

    def get(self, request):
        links = []
        for item in self.quick_links:
            try:
                target = reverse(item["url_name"])
            except Exception:
                target = "#"
            links.append({**item, "url": target})
        context = {
            "quick_links": links,
        }
        return render(request, self.template_name, context)


class ManageSupportInquiryView(SuperuserRequiredMixin, View):
    template_name = "manage/support_inquiries.html"

    def get(self, request):
        intent = request.GET.get("intent", "all").strip()
        status_param = request.GET.get("status", "all").strip()

        queryset = SupportInquiry.objects.select_related("user").order_by("-created_at")
        if intent and intent != "all":
            queryset = queryset.filter(intent=intent)
        if status_param and status_param != "all":
            queryset = queryset.filter(status=status_param)

        context = {
            "inquiries": queryset,
            "selected_intent": intent,
            "selected_status": status_param,
            "intent_choices": SupportInquiry.Intent.choices,
            "status_choices": SupportInquiry.Status.choices,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        inquiry_id = request.POST.get("inquiry_id")
        new_status = request.POST.get("status")

        if not inquiry_id or not new_status:
            messages.error(request, "요청 정보를 확인할 수 없습니다.")
            return redirect("manage_support_inquiries")

        inquiry = SupportInquiry.objects.filter(id=inquiry_id).first()
        if not inquiry:
            messages.error(request, "해당 문의를 찾을 수 없습니다.")
            return redirect("manage_support_inquiries")

        valid_status = dict(SupportInquiry.Status.choices)
        if new_status not in valid_status:
            messages.error(request, "지원하지 않는 상태 값입니다.")
            return redirect("manage_support_inquiries")

        inquiry.status = new_status
        inquiry.save(update_fields=["status", "updated_at"])
        messages.success(request, "문의 상태를 업데이트했습니다.")
        return redirect("manage_support_inquiries")


class ManageUploadHubView(SuperuserRequiredMixin, View):
    template_name = "manage/dashboard.html"
    form_class = AdminExcelUploadForm
    upload_targets = [
        {
            "key": "certificates",
            "title": "자격증 마스터",
            "description": "id와 name은 필수이며, tags 열은 콤마로 구분합니다.",
            "notes": [
                "필수 열: id, name",
                "선택 열: overview, job_roles, exam_method, eligibility, authority, type, homepage, rating, expected_duration, expected_duration_major, tags",
            ],
            "viewset": CertificateViewSet,
            "action": "upload_certificates",
            "api_path": "certificates/upload/certificates",
            "summary_keys": [("created", "신규"), ("updated", "갱신")],
        },
        {
            "key": "certificate_tags",
            "title": "자격증-태그 매핑",
            "description": "자격증에 태그 세트를 한 번에 연결하거나 초기화합니다.",
            "notes": [
                "필수 열: certificate_id 또는 certificate_name",
                "선택 열: tags (콤마 구분), tag_ids",
                "tags 미입력 시 기존 태그가 모두 초기화됩니다.",
            ],
            "viewset": CertificateViewSet,
            "action": "upload_certificate_tags",
            "api_path": "certificates/upload/certificate-tags",
            "summary_keys": [
                ("updated_certificates", "태그 갱신"),
                ("cleared_certificates", "초기화"),
                ("created_tags", "신규 태그"),
            ],
        },
        {
            "key": "phases",
            "title": "자격증 단계",
            "description": "필기/실기 등 단계 정보를 일괄 등록합니다.",
            "notes": [
                "필수 열: certificate_id 또는 certificate_name, phase_name",
                "선택 열: id, phase_type",
            ],
            "viewset": CertificatePhaseViewSet,
            "action": "upload_phases",
            "api_path": "certificates/upload/phases",
            "summary_keys": [("created", "신규"), ("updated", "갱신")],
        },
        {
            "key": "statistics",
            "title": "자격증 통계",
            "description": "연도/회차별 응시자 수, 합격률 데이터를 업로드합니다.",
            "notes": [
                "필수 열: certificate_id 또는 certificate_name, year",
                "선택 열: id, exam_type, session, registered, applicants, passers, pass_rate",
            ],
            "viewset": CertificateStatisticsViewSet,
            "action": "upload_statistics",
            "api_path": "certificates/upload/statistics",
            "summary_keys": [("created", "신규"), ("updated", "갱신")],
        },
        {
            "key": "tags",
            "title": "태그 마스터",
            "description": "태그 이름과 ID를 관리합니다.",
            "notes": [
                "필수 열: name",
                "선택 열: id",
            ],
            "viewset": TagViewSet,
            "action": "upload_tags",
            "api_path": "tags/upload/tags",
            "summary_keys": [("created", "신규"), ("updated", "갱신")],
        },
    ]

    def _build_form_map(self, overrides=None):
        overrides = overrides or {}
        forms = {}
        for target in self.upload_targets:
            key = target["key"]
            forms[key] = overrides.get(key) or self.form_class(prefix=key)
        return forms

    def _build_context(self, overrides=None):
        form_map = self._build_form_map(overrides)
        sections = []
        for target in self.upload_targets:
            sections.append(
                {
                    "key": target["key"],
                    "title": target["title"],
                    "description": target.get("description", ""),
                    "notes": target.get("notes", []),
                    "form": form_map[target["key"]],
                }
            )
        return {"upload_sections": sections}

    def get(self, request):
        context = self._build_context()
        return render(request, self.template_name, context)

    def post(self, request):
        upload_key = request.POST.get("upload_type")
        config = next((item for item in self.upload_targets if item["key"] == upload_key), None)
        if not config:
            messages.error(request, "지원하지 않는 업로드 요청입니다.")
            return redirect("manage_uploads")

        form = self.form_class(request.POST, request.FILES, prefix=upload_key)
        if not form.is_valid():
            context = self._build_context({upload_key: form})
            return render(request, self.template_name, context, status=400)

        response = self._perform_upload(request, config, form.cleaned_data)
        self._add_messages(request, config, response)
        return redirect("manage_uploads")

    def _perform_upload(self, request, config, cleaned_data):
        upload_file = cleaned_data["file"]
        sheet_name = (cleaned_data.get("sheet_name") or "").strip()
        upload_file.seek(0)

        query = {"sheet": sheet_name} if sheet_name else {}
        query_string = urlencode(query)
        url = f"/api/{config['api_path']}/"
        if query_string:
            url = f"{url}?{query_string}"

        factory = APIRequestFactory()
        django_request = factory.post(url, {"file": upload_file}, format="multipart")
        force_authenticate(
            django_request,
            user=request.user,
            token=getattr(request, "auth", None),
        )

        view = config["viewset"].as_view({"post": config["action"]})
        response = view(django_request)
        if hasattr(response, "render"):
            response.render()
        return response

    def _format_summary(self, config, data):
        if not isinstance(data, dict):
            return ""
        parts = []
        for key, label in config.get("summary_keys", []):
            if key in data and data[key] is not None:
                parts.append(f"{label} {data[key]}")
        return ", ".join(parts)

    def _extract_errors(self, data):
        if isinstance(data, dict):
            errors = data.get("errors")
            if isinstance(errors, list) and errors:
                preview = errors[:3]
                extra = len(errors) - len(preview)
                message = "; ".join(str(item) for item in preview)
                if extra > 0:
                    message += f" 외 {extra}건"
                return message
        return ""

    def _error_detail(self, data):
        if isinstance(data, dict):
            detail = data.get("detail")
            if detail:
                return str(detail)
            message = self._extract_errors(data)
            if message:
                return message
        return "자세한 오류는 서버 로그를 확인해주세요."

    def _add_messages(self, request, config, response):
        data = getattr(response, "data", {})
        summary = self._format_summary(config, data)

        if response.status_code == 200:
            base = f"{config['title']} 업로드가 완료됐어요."
            if summary:
                base += f" ({summary})"
            messages.success(request, base)
            return

        if response.status_code == 207:
            base = f"{config['title']} 업로드가 일부만 처리됐어요."
            if summary:
                base += f" ({summary})"
            error_preview = self._extract_errors(data)
            if error_preview:
                base += f" - {error_preview}"
            messages.warning(request, base)
            return

        detail = self._error_detail(data)
        messages.error(request, f"{config['title']} 업로드에 실패했습니다: {detail}")


class UserCertificateReviewView(SuperuserRequiredMixin, View):
    template_name = "users/certificate_review.html"

    def get(self, request):
        pending_requests = (
            UserCertificate.objects.select_related("user", "certificate")
            .filter(status=UserCertificate.STATUS_PENDING)
            .order_by("created_at")
        )
        recent_decisions = (
            UserCertificate.objects.select_related("user", "certificate", "reviewed_by")
            .filter(status__in=[UserCertificate.STATUS_APPROVED, UserCertificate.STATUS_REJECTED])
            .order_by("-reviewed_at")[:10]
        )

        context = {
            "pending_requests": pending_requests,
            "recent_decisions": recent_decisions,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        record_id = request.POST.get("record_id")
        action = request.POST.get("action")
        note = (request.POST.get("note") or "").strip()

        record = get_object_or_404(
            UserCertificate.objects.select_related("user", "certificate"), pk=record_id
        )

        if record.status != UserCertificate.STATUS_PENDING and action in {"approve", "reject"}:
            messages.info(request, "이미 처리된 신청입니다.")
            return redirect("certificate_review")

        display_name = record.user.name or record.user.get_username()

        if action == "approve":
            record.mark_approved(request.user, note)
            messages.success(
                request,
                f"{display_name}님의 '{record.certificate.name}' 자격증을 승인했습니다.",
            )
        elif action == "reject":
            record.mark_rejected(request.user, note)
            messages.warning(
                request,
                f"{display_name}님의 '{record.certificate.name}' 자격증을 반려했습니다.",
            )
        else:
            messages.error(request, "지원되지 않는 작업입니다.")

        return redirect("certificate_review")
>>>>>>> seil2
