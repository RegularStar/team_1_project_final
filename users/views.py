from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from rest_framework import generics, permissions
from rest_framework.response import Response

from certificates.models import Certificate, Tag, UserTag
from .forms import InterestKeywordForm, SignInForm, SignUpForm
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
        logout(request)
        return redirect("home")


class MyPageView(View):
    template_name = "users/mypage.html"
    form_class = InterestKeywordForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        return super().dispatch(request, *args, **kwargs)

    def _build_context(self, request, form):
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

        return {
            "user": request.user,
            "interest_form": form,
            "interest_tags": user_tags,
            "tag_suggestions": related_tags,
        }

    def get(self, request):
        form = self.form_class()
        context = self._build_context(request, form)
        return render(request, self.template_name, context)

    def post(self, request):
        if request.POST.get("remove_tag"):
            tag_id = request.POST.get("remove_tag")
            user_tag = request.user.user_tags.filter(tag_id=tag_id).first()
            if user_tag:
                user_tag.delete()
                messages.success(request, "관심 태그를 삭제했어요.")
            else:
                messages.warning(request, "이미 삭제된 태그예요.")
            return redirect("mypage")

        form = self.form_class(request.POST)
        if form.is_valid():
            keyword = form.cleaned_data["keyword"]
            tag, _ = Tag.objects.get_or_create(name=keyword)
            try:
                UserTag.objects.get_or_create(user=request.user, tag=tag)
            except IntegrityError:
                # Rare race condition if the same tag is created concurrently.
                messages.info(request, "이미 등록된 태그예요.")
            else:
                messages.success(request, "관심 태그를 추가했어요.")
            return redirect("mypage")

        context = self._build_context(request, form)
        messages.error(request, "관심 태그를 다시 확인해주세요.")
        return render(request, self.template_name, context)
