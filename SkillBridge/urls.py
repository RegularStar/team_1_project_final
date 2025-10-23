from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from ratings.views import DeleteRatingView, SubmitRatingView
from users.views import (
    LogoutView,
    ManageHomeView,
    ManageSupportInquiryView,
    ManageUploadHubView,
    MyPageView,
    SignInView,
    SignUpView,
    UserCertificateReviewView,
    UserPublicProfileView,
)
from . import views as site_views


def healthz(_):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("", site_views.home, name="home"),
    path("job-recommend/", site_views.job_recommendation, name="job_recommendation"),
    path("search/", site_views.search, name="search"),
    path("hall-of-fame/", site_views.hall_of_fame, name="hall_of_fame"),
    path("users/<int:user_id>/", UserPublicProfileView.as_view(), name="user_profile"),
    path("certificates/<str:slug>/reviews/", site_views.certificate_reviews, name="certificate_reviews"),
    path("certificates/<str:slug>/reviews/submit/", SubmitRatingView.as_view(), name="certificate_review_submit"),
    path(
        "certificates/<str:slug>/reviews/<int:review_id>/delete/",
        DeleteRatingView.as_view(),
        name="certificate_review_delete",
    ),
    path("certificates/<str:slug>/statistics/", site_views.certificate_statistics, name="certificate_statistics"),
    path("certificates/<str:slug>/", site_views.certificate_detail, name="certificate_detail"),
    path("boards/", site_views.board_all, name="board_all"),
    path("boards/create/", site_views.board_create, name="board_create"),
    path("boards/<str:slug>/<int:post_id>/like/", site_views.board_toggle_like, name="board_toggle_like"),
    path(
        "boards/<str:slug>/<int:post_id>/comments/<int:comment_id>/delete/",
        site_views.board_comment_delete,
        name="board_comment_delete",
    ),
    path("boards/<str:slug>/<int:post_id>/edit/", site_views.board_edit, name="board_edit"),
    path("boards/<str:slug>/<int:post_id>/delete/", site_views.board_delete, name="board_delete"),
    path("boards/<str:slug>/<int:post_id>/", site_views.board_detail, name="board_detail"),
    path("boards/<str:slug>/", site_views.board_list, name="board_list"),
    path("login/", SignInView.as_view(), name="login"),
    path("register/", SignUpView.as_view(), name="register"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("mypage/", MyPageView.as_view(), name="mypage"),
    path("manage/", ManageHomeView.as_view(), name="manage_home"),
    path("manage/uploads/", ManageUploadHubView.as_view(), name="manage_uploads"),
    path("manage/support-inquiries/", ManageSupportInquiryView.as_view(), name="manage_support_inquiries"),
    path("manage/certificate-requests/", UserCertificateReviewView.as_view(), name="certificate_review"),
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("api/users/", include("users.urls")),
    path("api/", include("certificates.urls")),
    path("api/", include("community.urls")),
    path("api/", include("ratings.urls")),
    path("api/ai/", include("ai.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
