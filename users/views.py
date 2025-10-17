from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse_lazy
from django.views import View
from rest_framework import generics, permissions
from rest_framework.response import Response

from certificates.models import Certificate, Tag, UserCertificate, UserTag
from .forms import InterestKeywordForm, SignInForm, SignUpForm, UserCertificateRequestForm
from .serializers import UserCreateSerializer, UserSerializer

User = get_user_model()


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
        next_url = request.POST.get("next") or request.GET.get("next")
        logout(request)
        return redirect(resolve_url(next_url or "home"))


class MyPageView(View):
    template_name = "users/mypage.html"
    interest_form_class = InterestKeywordForm
    certificate_form_class = UserCertificateRequestForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        return super().dispatch(request, *args, **kwargs)

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


class UserCertificateReviewView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "users/certificate_review.html"
    raise_exception = False

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        response = render(
            self.request,
            "users/access_denied.html",
            {
                "exception": None,
                "redirect_url": reverse_lazy("login"),
            },
            status=403,
        )
        return response

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

        if action == "approve":
            record.mark_approved(request.user, note)
            messages.success(
                request,
                f"{record.user.get_username()}님의 '{record.certificate.name}' 자격증을 승인했습니다.",
            )
        elif action == "reject":
            record.mark_rejected(request.user, note)
            messages.warning(
                request,
                f"{record.user.get_username()}님의 '{record.certificate.name}' 자격증을 반려했습니다.",
            )
        else:
            messages.error(request, "지원되지 않는 작업입니다.")

        return redirect("certificate_review")
