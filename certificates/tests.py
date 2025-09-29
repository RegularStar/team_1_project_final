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
        self.client.login(username="admin", password="adminpass")
        payload = {"name": "빅데이터분석기사", "overview": "설명"}
        resp = self.client.post("/api/certificates/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_non_admin_cannot_write_cert(self):
        self.client.login(username="user", password="userpass")
        payload = {"name": "네트워크관리사", "overview": "설명"}
        resp = self.client.post("/api/certificates/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

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