from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from certificates.models import Certificate, Tag, UserTag

User = get_user_model()


def _as_list(data):
    # 페이지네이션 대응: {"results": [...]} 형태면 results 반환
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


class CertificateAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username="admin", password="adminpass")
        self.user = User.objects.create_user(username="user", password="userpass")

        # ✅ description → overview
        self.cert = Certificate.objects.create(name="정보처리기사", overview="설명")

    def test_public_can_read(self):
        resp = self.client.get("/api/certificates/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_write_cert(self):
        self.client.force_authenticate(self.admin)
        payload = {"name": "빅데이터분석기사", "overview": "설명"}
        resp = self.client.post("/api/certificates/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.client.force_authenticate(None)

    def test_non_admin_cannot_write_cert(self):
        self.client.force_authenticate(self.user)
        payload = {"name": "네트워크관리사", "overview": "설명"}
        resp = self.client.post("/api/certificates/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(None)

    def test_user_tag_crud_only_self(self):
        # 로그인(세션) 대신 인증 강제 → 환경에 따라 세션 미사용이어도 통과 보장
        self.client.force_authenticate(self.user)

        # 태그 생성 후 내 태그로 등록
        t = Tag.objects.create(name="AI")
        create_resp = self.client.post("/api/user-tags/", {"tag": t.id}, format="json")
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)

        # 내 태그 목록 조회 → 내가 방금 추가한 태그가 보여야 함
        list_resp = self.client.get("/api/user-tags/")
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        items = _as_list(list_resp.data)
        self.assertGreaterEqual(len(items), 1)
        # serializer가 tag의 PK를 반환하므로 같은지 확인
        self.assertEqual(items[0]["tag"], t.id)

    def test_user_certificate_crud_only_self(self):
        other = User.objects.create_user(username="other", password="otherpass")
        self.client.force_authenticate(self.user)

        create_resp = self.client.post(
            "/api/user-certificates/",
            {"certificate": self.cert.id, "acquired_at": "2024-01-01"},
            format="json",
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)

        list_resp = self.client.get("/api/user-certificates/")
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        items = _as_list(list_resp.data)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["certificate"], self.cert.id)

        # 다른 사용자가 접근하면 빈 결과여야 함
        self.client.force_authenticate(other)
        other_list = self.client.get("/api/user-certificates/")
        self.assertEqual(other_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(_as_list(other_list.data)), 0)
