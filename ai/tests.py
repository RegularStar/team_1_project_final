from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from certificates.models import Certificate, Tag
from ai.services import JobContentFetchError


class ChatViewTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    @patch("ai.views.LangChainChatService")
    def test_chat_success(self, mock_service_cls):
        mock_service = mock_service_cls.return_value
        mock_service.run.return_value = "안녕하세요!"

        url = reverse("ai-chat")
        payload = {
            "message": "안녕",
            "history": [{"role": "user", "content": "첫 질문"}],
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["reply"], "안녕하세요!")
        self.assertEqual(mock_service.run.call_count, 1)
        kwargs = mock_service.run.call_args.kwargs
        self.assertEqual(kwargs["message"], "안녕")
        self.assertEqual(kwargs["history"], payload["history"])

    def test_chat_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse("ai-chat")
        response = self.client.post(url, {"message": "hello"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("ai.views.LangChainChatService")
    def test_ai_error_returns_502(self, mock_service_cls):
        mock_service = mock_service_cls.return_value
        mock_service.run.side_effect = RuntimeError("boom")

        url = reverse("ai-chat")
        response = self.client.post(url, {"message": "help"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("detail", response.data)


class JobCertificateRecommendationViewTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="recommender",
            email="recommender@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    def _create_certificate(self, name: str, tags: list[str]):
        certificate = Certificate.objects.create(name=name)
        for tag_name in tags:
            tag, _ = Tag.objects.get_or_create(name=tag_name)
            certificate.tags.add(tag)
        return certificate

    def test_recommendation_with_inline_content(self):
        certificate = self._create_certificate("데이터 분석 전문가", ["데이터", "AI"])

        url = reverse("ai-job-certificates")
        payload = {
            "url": "https://jobs.example.com/123",
            "content": "AI 기반 데이터 분석과 머신러닝 역량을 요구합니다.",
            "max_results": 3,
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["url"], payload["url"])
        self.assertTrue(response.data["job_excerpt"].startswith("AI 기반"))
        self.assertGreaterEqual(len(response.data["recommendations"]), 1)
        self.assertEqual(response.data["recommendations"][0]["certificate"]["id"], certificate.id)
        self.assertTrue(response.data["recommendations"][0]["reasons"])

    def test_recommendation_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse("ai-job-certificates")
        response = self.client.post(
            url,
            {"url": "https://jobs.example.com/1", "content": "security"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("ai.services.JobCertificateRecommendationService._fetch_job_content")
    def test_recommendation_fetch_failure(self, mock_fetch):
        mock_fetch.side_effect = JobContentFetchError("연결 실패")

        url = reverse("ai-job-certificates")
        response = self.client.post(url, {"url": "https://jobs.example.com/404"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("detail", response.data)
