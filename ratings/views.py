from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.text import slugify
from django.views import View
from rest_framework import permissions, viewsets, filters

from certificates.models import Certificate
from .forms import RatingForm
from .models import Rating
from .serializers import RatingSerializer

class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user and request.user.is_staff:
            return True
        return obj.user_id == request.user.id

class RatingViewSet(viewsets.ModelViewSet):
    """
    /api/ratings/
    /api/ratings/{id}/
    """
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [filters.OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Rating.objects.select_related("certificate", "user")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SubmitRatingView(LoginRequiredMixin, View):
    form_class = RatingForm

    def _get_certificate(self, slug: str):
        queryset = Certificate.objects.all()
        if slug.isdigit():
            return queryset.filter(pk=int(slug)).first()
        for cert in queryset:
            if slugify(cert.name) == slug:
                return cert
        return None

    def post(self, request, slug):
        certificate = self._get_certificate(slug)
        if not certificate:
            messages.error(request, "요청하신 자격증을 찾을 수 없어요.")
            return redirect("home")

        form = self.form_class(request.POST)
        next_url = request.POST.get("next") or reverse("certificate_detail", args=[slug])

        if not form.is_valid():
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
            return redirect(next_url)

        difficulty = int(form.cleaned_data["difficulty"])
        content = form.cleaned_data["content"]
        rating_value = max(1, min(10, difficulty))

        Rating.objects.update_or_create(
            user=request.user,
            certificate=certificate,
            defaults={"rating": rating_value, "content": content},
        )
        messages.success(request, "리뷰가 등록되었습니다.")
        return redirect(next_url)
