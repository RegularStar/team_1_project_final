from django.urls import path

from .views import ChatView, JobCertificateRecommendationView

urlpatterns = [
    path("chat/", ChatView.as_view(), name="ai-chat"),
    path("job-certificates/", JobCertificateRecommendationView.as_view(), name="ai-job-certificates"),
]
