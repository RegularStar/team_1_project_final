from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from ratings.views import SubmitRatingView
from users.views import LogoutView, MyPageView, SignInView, SignUpView
from . import views as site_views


def healthz(_):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("", site_views.home, name="home"),
    path("ai/job-recommendation/", site_views.job_recommendation, name="job_recommendation"),
    path("search/", site_views.search, name="search"),
    path("certificates/<slug:slug>/reviews/", site_views.certificate_reviews, name="certificate_reviews"),
    path("certificates/<slug:slug>/reviews/submit/", SubmitRatingView.as_view(), name="certificate_review_submit"),
    path("certificates/<slug:slug>/statistics/", site_views.certificate_statistics, name="certificate_statistics"),
    path("certificates/<slug:slug>/", site_views.certificate_detail, name="certificate_detail"),
    path("boards/create/", site_views.board_create, name="board_create"),
    path("boards/<slug:slug>/<int:post_id>/like/", site_views.board_toggle_like, name="board_toggle_like"),
    path("boards/<slug:slug>/<int:post_id>/edit/", site_views.board_edit, name="board_edit"),
    path("boards/<slug:slug>/<int:post_id>/delete/", site_views.board_delete, name="board_delete"),
    path("boards/<slug:slug>/<int:post_id>/", site_views.board_detail, name="board_detail"),
    path("boards/<slug:slug>/", site_views.board_list, name="board_list"),
    path("login/", SignInView.as_view(), name="login"),
    path("register/", SignUpView.as_view(), name="register"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("mypage/", MyPageView.as_view(), name="mypage"),
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("api/users/", include("users.urls")),
    path("api/", include("certificates.urls")),
    path("api/", include("community.urls")),
    path("api/", include("ratings.urls")),
    path("api/ai/", include("ai.urls")),
]
