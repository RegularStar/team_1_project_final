from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from certificates.models import Certificate
from ratings.models import Rating

User = get_user_model()


class RatingAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username="user1", password="pass1")
        self.user2 = User.objects.create_user(username="user2", password="pass2")
        self.admin = User.objects.create_superuser(username="admin", password="adminpass")

        self.cert = Certificate.objects.create(name="정보처리기사", overview="설명")
        self.rating1 = Rating.objects.create(user=self.user1, certificate=self.cert, rating=4, content="좋아요")

        self.list_url = "/api/ratings/"
        self.detail_url = lambda pk: f"/api/ratings/{pk}/"

    def test_list_public(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_create_requires_auth(self):
        payload = {"certificate": self.cert.id, "rating": 5, "content": "좋음"}
        resp = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_sets_owner(self):
        self.client.force_authenticate(self.user1)  # 로그인 대체
        payload = {"certificate": self.cert.id, "rating": 5, "content": "좋음"}
        resp = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["user"], self.user1.id)

    def test_update_owner_only(self):
        self.client.force_authenticate(self.user2)
        resp = self.client.patch(self.detail_url(self.rating1.id), {"rating": 2}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_owner_and_admin_returns_200(self):
        # 소유자 삭제
        self.client.force_authenticate(self.user1)
        resp = self.client.delete(self.detail_url(self.rating1.id))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

        # 관리자 삭제
        r = Rating.objects.create(user=self.user1, certificate=self.cert, rating=3)
        self.client.force_authenticate(self.admin)
        resp = self.client.delete(self.detail_url(r.id))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_unique_user_cert_phase(self):
        self.client.force_authenticate(self.user1)
        payload = {"certificate": self.cert.id, "rating": 3, "content": "중복"}
        resp = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)