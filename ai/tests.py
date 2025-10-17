from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from certificates.models import Certificate, Tag
from ai.models import JobTagContribution
from ai.services import JobContentFetchError
from PIL import Image


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

    def _create_image_file(self, name: str = "job.png"):
        image = Image.new("RGB", (60, 60), color=(255, 255, 255))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return SimpleUploadedFile(name, buffer.read(), content_type="image/png")

    def _create_certificate(self, name: str, tags: list[str]):
        certificate = Certificate.objects.create(name=name)
        for tag_name in tags:
            tag, _ = Tag.objects.get_or_create(name=tag_name)
            certificate.tags.add(tag)
        return certificate

    def test_recommendation_with_inline_content(self):
        certificate = self._create_certificate("데이터 분석 전문가", ["데이터", "AI"])

        url = reverse("ai-job-certificates")
        image_file = self._create_image_file()
        payload = {
            "image": image_file,
            "content": "AI 기반 데이터 분석과 머신러닝 역량을 요구합니다.",
            "max_results": 3,
        }

        response = self.client.post(url, payload, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["job_excerpt"].startswith("AI 기반"))
        self.assertGreaterEqual(len(response.data["recommendations"]), 1)
        self.assertEqual(response.data["recommendations"][0]["certificate"]["id"], certificate.id)
        self.assertTrue(response.data["recommendations"][0]["reasons"])
        self.assertIn("analysis", response.data)
        self.assertIn("missing_keywords", response.data)
        self.assertIsInstance(response.data["missing_keywords"], list)
        self.assertIn("matched_keywords", response.data)
        self.assertIsInstance(response.data["matched_keywords"], list)
        self.assertIn("keyword_suggestions", response.data)
        self.assertIsInstance(response.data["keyword_suggestions"], list)

    def test_recommendation_with_text_only(self):
        certificate = self._create_certificate("정보보안 전문가", ["보안", "네트워크"])

        url = reverse("ai-job-certificates")
        payload = {
            "content": "정보보안 정책 수립과 네트워크 보안 관제 경험을 요구합니다.",
            "max_results": 2,
        }

        response = self.client.post(url, payload, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["recommendations"]), 1)
        self.assertEqual(response.data["recommendations"][0]["certificate"]["id"], certificate.id)
        self.assertIn("missing_keywords", response.data)
        self.assertIn("matched_keywords", response.data)
        self.assertIn("keyword_suggestions", response.data)

    def test_recommendation_requires_content_or_image(self):
        url = reverse("ai-job-certificates")
        response = self.client.post(url, {"max_results": 2}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)

    def test_recommendation_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse("ai-job-certificates")
        image_file = self._create_image_file("secure.png")
        response = self.client.post(
            url,
            {"image": image_file, "content": "security"},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("ai.services.JobCertificateRecommendationService._extract_text_from_image")
    def test_recommendation_fetch_failure(self, mock_extract):
        mock_extract.side_effect = JobContentFetchError("연결 실패")

        url = reverse("ai-job-certificates")
        image_file = self._create_image_file("fail.png")
        response = self.client.post(url, {"image": image_file}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("detail", response.data)


class JobTagContributionViewTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="contributor",
            email="contributor@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    def _create_certificate(self, name: str) -> Certificate:
        return Certificate.objects.create(name=name)

    def test_create_new_tag_and_link_certificate(self):
        certificate = self._create_certificate("클라우드 전문가")
        url = reverse("ai-job-certificates-feedback")
        payload = {
            "tag_name": "클라우드",
            "certificate_ids": [certificate.id],
            "job_excerpt": "클라우드 아키텍처 구성 경험",
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["tag_created"])
        self.assertEqual(response.data["linked_certificates"], [certificate.id])
        tag = Tag.objects.get(name="클라우드")
        self.assertTrue(certificate.tags.filter(id=tag.id).exists())
        self.assertEqual(JobTagContribution.objects.count(), 1)
        self.assertEqual(response.data["added_certificate_ids"], [certificate.id])
        self.assertEqual(response.data["already_linked_ids"], [])

    def test_existing_tag_additional_link(self):
        certificate = self._create_certificate("정보보안 기사")
        tag = Tag.objects.create(name="보안")
        url = reverse("ai-job-certificates-feedback")
        payload = {
            "tag_name": "보안",
            "certificate_ids": [certificate.id],
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["tag_created"])
        self.assertTrue(certificate.tags.filter(id=tag.id).exists())
        self.assertEqual(JobTagContribution.objects.filter(tag=tag).count(), 1)
        self.assertEqual(response.data["added_certificate_ids"], [certificate.id])
        self.assertEqual(response.data["already_linked_ids"], [])

    def test_duplicate_relationship_reports_already_linked(self):
        certificate = self._create_certificate("데이터 분석 전문가")
        tag = Tag.objects.create(name="데이터")
        certificate.tags.add(tag)

        url = reverse("ai-job-certificates-feedback")
        payload = {
            "tag_name": "데이터",
            "certificate_ids": [certificate.id],
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn(certificate.id, response.data["already_linked_ids"])
        self.assertEqual(response.data["added_certificate_ids"], [])
        self.assertIn("이미 연결된", response.data["message"])

    def test_invalid_certificate_id_returns_error(self):
        url = reverse("ai-job-certificates-feedback")
        payload = {
            "tag_name": "데이터",
            "certificate_ids": [99999],
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("certificate_ids", response.data)
