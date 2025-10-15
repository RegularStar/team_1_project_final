from django.urls import path

from .views import ChatView, JobCertificateRecommendationView, JobOcrView

urlpatterns = [
    path("chat/", ChatView.as_view(), name="ai-chat"),
    path("job-certificates/", JobCertificateRecommendationView.as_view(), name="ai-job-certificates"),
    path("job-certificates/ocr/", JobOcrView.as_view(), name="ai-job-ocr"),
]
