from io import BytesIO
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from openpyxl import Workbook

from .models import Tag, Certificate, CertificateTag, CertificatePhase, CertificateStatistics, UserTag

User = get_user_model()


def _as_list(data):
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


class CertificateAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="u", email="u@e.com", password="pass12345")
        self.admin = User.objects.create_user(
            username="admin", email="a@e.com", password="pass12345", is_staff=True, is_superuser=True
        )

        self.tag_ai = Tag.objects.create(name="AI")
        self.cert = Certificate.objects.create(name="정보처리기사", description="설명")
        CertificateTag.objects.create(certificate=self.cert, tag=self.tag_ai)

        # urls
        self.tag_list = reverse("tag-list")
        self.cert_list = reverse("certificate-list")
        self.phase_list = reverse("certificate-phase-list")
        self.stat_list = reverse("certificate-statistics-list")
        self.usertag_list = reverse("user-tag-list")

    # --- 읽기(공개) ---
    def test_public_can_read(self):
        r = self.client.get(self.cert_list)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(_as_list(r.data)), 1)

        r = self.client.get(self.tag_list)
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    # --- 쓰기(관리자만) ---
    def test_non_admin_cannot_write_cert(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.post(self.cert_list, {"name": "빅데이터분석사"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_write_cert(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(self.cert_list, {"name": "빅데이터분석사"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Certificate.objects.filter(name="빅데이터분석사").exists())

    # --- UserTag: 내 것만 ---
    def test_user_tag_crud_only_self(self):
        # 로그인 필요
        r = self.client.post(self.usertag_list, {"tag": self.tag_ai.id}, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

        # user가 자기 태그 추가
        self.client.force_authenticate(user=self.user)
        r = self.client.post(self.usertag_list, {"tag": self.tag_ai.id}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        ut_id = r.data["id"]
        self.assertTrue(UserTag.objects.filter(id=ut_id, user=self.user, tag=self.tag_ai).exists())

        # 목록은 내 것만
        r = self.client.get(self.usertag_list)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(_as_list(r.data)), 1)

        # 다른 유저는 이 레코드 안 보여야 함
        other = User.objects.create_user(username="o", email="o@e.com", password="pass12345")
        self.client.force_authenticate(user=other)
        r = self.client.get(self.usertag_list)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(_as_list(r.data)), 0)

    # --- 업로드(관리자 전용) 간단 검증 ---
    def _wb_bytes(self, headers, rows):
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        for row in rows:
            ws.append(row)
        f = BytesIO()
        wb.save(f)
        f.seek(0)
        return f

    def test_upload_certificates(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("certificate-upload-certificates")
        fileobj = self._wb_bytes(
            headers=["name", "description", "authority", "cert_type", "homepage", "rating", "expected_duration", "expected_duration_major", "tags"],
            rows=[["데이터분석기사", "desc", "HRDK", "국가", "https://hrd", 5, 12, 8, "AI,데이터"]]
        )
        r = self.client.post(url, {"file": fileobj}, format="multipart")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(Certificate.objects.filter(name="데이터분석기사").exists())
        self.assertTrue(Tag.objects.filter(name="데이터").exists())

    def test_upload_phases(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("certificate-phase-upload-phases")
        fileobj = self._wb_bytes(
            headers=["certificate_name", "phase_name", "phase_type"],
            rows=[["정보처리기사", "1차", "필기"], ["정보처리기사", "2차", "실기"]]
        )
        r = self.client.post(url, {"file": fileobj}, format="multipart")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(CertificatePhase.objects.filter(certificate=self.cert).count(), 2)

    def test_upload_statistics(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("certificate-statistics-upload-statistics")
        fileobj = self._wb_bytes(
            headers=["certificate_name", "exam_type", "year", "session", "registered", "applicants", "passers", "pass_rate"],
            rows=[["정보처리기사", "필기", 2024, "1회", 1000, 900, 450, 0.5]]
        )
        r = self.client.post(url, {"file": fileobj}, format="multipart")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(CertificateStatistics.objects.filter(certificate=self.cert, year=2024, session="1회").exists())

    def test_upload_requires_admin(self):
        # 비관리자는 403
        self.client.force_authenticate(user=self.user)
        url = reverse("certificate-upload-certificates")
        fileobj = self._wb_bytes(
            headers=["name"], rows=[["테스트"]]
        )
        r = self.client.post(url, {"file": fileobj}, format="multipart")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)