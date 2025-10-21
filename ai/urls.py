from django.urls import path

<<<<<<< HEAD
from .views import ChatView, JobCertificateRecommendationView, JobOcrView
=======
from .views import (
    ChatView,
    JobCertificateRecommendationView,
    JobOcrView,
    JobTagContributionView,
    SupportInquiryView,
)
>>>>>>> seil2

urlpatterns = [
    path("chat/", ChatView.as_view(), name="ai-chat"),
    path("job-certificates/", JobCertificateRecommendationView.as_view(), name="ai-job-certificates"),
    path("job-certificates/ocr/", JobOcrView.as_view(), name="ai-job-ocr"),
<<<<<<< HEAD
=======
    path(
        "job-certificates/feedback/",
        JobTagContributionView.as_view(),
        name="ai-job-certificates-feedback",
    ),
    path("support-inquiries/", SupportInquiryView.as_view(), name="ai-support-inquiry"),
>>>>>>> seil2
]
