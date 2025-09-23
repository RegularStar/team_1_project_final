# ratings/tests.py
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from certificates.models import Certificate, CertificatePhase
from .models import Rating

User = get_user_model()


def _as_list(data):
    """페이지네이션 유무에 따라 리스트 반환"""
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


class RatingAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username="u1", email="u1@example.com", password="pass12345")
        self.user2 = User.objects.create_user(username="u2", email="u2@example.com", password="pass12345")
        self.admin = User.objects.create_user(
            username="admin", email="a@e.com", password="pass12345",
            is_staff=True, is_superuser=True
        )

        self.cert = Certificate.objects.create(name="정보처리기사")
        self.phase = CertificatePhase.objects.create(
            certificate=self.cert, phase_name="1차", phase_type="필기"
        )

        self.rating1 = Rating.objects.create(
            user=self.user1, cert_phase=self.phase, score=4, content="좋아요"
        )

        self.list_url = reverse("rating-list")
        self.detail_url = lambda pk: reverse("rating-detail", args=[pk])

    def test_list_public(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = _as_list(resp.data)
        self.assertGreaterEqual(len(items), 1)

    def test_create_requires_auth(self):
        payload = {"cert_phase": self.phase.id, "score": 5, "content": "비로그인 불가"}
        resp = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_sets_owner(self):
        self.client.force_authenticate(user=self.user2)
        payload = {"cert_phase": self.phase.id, "score": 5, "content": "좋음"}
        resp = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        rid = resp.data["id"]
        r = Rating.objects.get(id=rid)
        self.assertEqual(r.user_id, self.user2.id)
        self.assertEqual(r.cert_phase_id, self.phase.id)

    def test_unique_user_cert_phase(self):
        self.client.force_authenticate(user=self.user1)
        payload = {"cert_phase": self.phase.id, "score": 3, "content": "중복"}
        resp = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_owner_only(self):
        # 다른 사용자 불가
        self.client.force_authenticate(user=self.user2)
        resp = self.client.patch(self.detail_url(self.rating1.id), {"score": 2}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # 작성자 가능
        self.client.force_authenticate(user=self.user1)
        resp = self.client.patch(self.detail_url(self.rating1.id), {"score": 5}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["score"], 5)

        # 관리자 가능
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(self.detail_url(self.rating1.id), {"content": "관리자수정"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["content"], "관리자수정")

    def test_delete_owner_and_admin_returns_200(self):
        # 작성자 삭제
        self.client.force_authenticate(user=self.user1)
        resp = self.client.delete(self.detail_url(self.rating1.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Rating.objects.filter(id=self.rating1.id).exists())

        # 관리자 삭제
        r2 = Rating.objects.create(user=self.user2, cert_phase=self.phase, score=3, content="삭제테스트")
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.detail_url(r2.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Rating.objects.filter(id=r2.id).exists())