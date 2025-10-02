from django.test import TestCase
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from certificates.models import Certificate, Tag, UserTag
from ratings.models import Rating

User = get_user_model()


def _as_list(data):
    # 페이지네이션 대응: {"results": [...]} 형태면 results 반환
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


class CertificateAPITests(TestCase):
    def _xlsx_file(self, headers, rows, filename="upload.xlsx"):
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        for row in rows:
            ws.append(row)
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return SimpleUploadedFile(
            filename,
            buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username="admin", password="adminpass")
        self.user = User.objects.create_user(username="user", password="userpass")

        # ✅ description → overview
        self.cert = Certificate.objects.create(name="정보처리기사", overview="설명", type="국가공인")

    def test_public_can_read(self):
        resp = self.client.get("/api/certificates/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_write_cert(self):
        self.client.force_authenticate(self.admin)
        payload = {"id": 999, "name": "빅데이터분석기사", "overview": "설명"}
        resp = self.client.post("/api/certificates/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Certificate.objects.filter(pk=999).exists())
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

    def test_certificate_filter_by_tag_and_type(self):
        ai = Tag.objects.create(name="AI")
        finance = Tag.objects.create(name="금융")

        cert2 = Certificate.objects.create(name="빅데이터분석기사", overview="분석", type="국가공인")
        cert3 = Certificate.objects.create(name="소프트웨어전문가", overview="소프트", type="민간")

        self.cert.tags.add(ai)
        cert2.tags.add(ai)
        cert3.tags.add(finance)

        resp = self.client.get("/api/certificates/?tags=AI&type=국가공인")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = _as_list(resp.data)
        self.assertEqual(len(items), 2)
        returned_names = {item["name"] for item in items}
        self.assertSetEqual(returned_names, {"정보처리기사", "빅데이터분석기사"})

    def test_certificate_ordering_by_applicants(self):
        cert2 = Certificate.objects.create(name="네트워크관리사", overview="네트워크", type="국가공인")

        # Create statistics
        self.cert.statistics.create(year="2023", session=1, applicants=500)
        cert2.statistics.create(year="2023", session=1, applicants=1000)

        resp = self.client.get("/api/certificates/?ordering=-total_applicants")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = _as_list(resp.data)
        self.assertGreaterEqual(len(items), 2)
        self.assertEqual(items[0]["name"], "네트워크관리사")

    def test_certificate_ordering_by_difficulty(self):
        cert2 = Certificate.objects.create(name="클라우드전문가", overview="클라우드", type="민간")

        Rating.objects.create(user=self.user, certificate=self.cert, rating=2)
        Rating.objects.create(user=self.admin, certificate=self.cert, rating=3)
        Rating.objects.create(user=self.user, certificate=cert2, rating=5)

        resp = self.client.get("/api/certificates/?ordering=-avg_difficulty")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = _as_list(resp.data)
        self.assertGreaterEqual(len(items), 2)
        self.assertEqual(items[0]["name"], "클라우드전문가")


    def test_upload_certificates_creates_and_updates(self):
        self.client.force_authenticate(self.admin)
        headers = [
            "id",
            "name",
            "overview",
            "job_roles",
            "exam_method",
            "eligibility",
            "authority",
            "type",
            "homepage",
            "rating",
            "expected_duration",
            "expected_duration_major",
            "tags",
        ]
        rows = [[
            555,
            "AI 전문가",
            "소개",
            "데이터 사이언티스트",
            "필기/실기",
            "관련 전공",
            "과기부",
            "국가공인",
            "https://example.com",
            4.0,
            120.5,
            "90",
            "AI,데이터",
        ]]
        upload = self._xlsx_file(headers, rows, filename="certs.xlsx")
        resp = self.client.post(
            "/api/certificates/upload/certificates/",
            {"file": upload},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, {"created": 1, "updated": 0})

        created_cert = Certificate.objects.get(pk=555)
        self.assertEqual(created_cert.name, "AI 전문가")
        self.assertEqual(created_cert.rating, 4)
        self.assertEqual(created_cert.expected_duration, 120)
        self.assertSetEqual(set(created_cert.tags.values_list("name", flat=True)), {"AI", "데이터"})

        # 업데이트 시나리오 - 태그도 재셋팅
        rows_update = [[
            555,
            "AI 전문가",
            "수정된 소개",
            "데이터 사이언티스트",
            "필기/실기",
            "관련 전공",
            "과기부",
            "국가공인",
            "https://example.com",
            5,
            100,
            "80",
            "AI",
        ]]
        upload_update = self._xlsx_file(headers, rows_update, filename="certs_update.xlsx")
        resp_update = self.client.post(
            "/api/certificates/upload/certificates/",
            {"file": upload_update},
            format="multipart",
        )
        self.assertEqual(resp_update.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_update.data, {"created": 0, "updated": 1})
        created_cert.refresh_from_db()
        self.assertEqual(created_cert.overview, "수정된 소개")
        self.assertEqual(created_cert.rating, 5)
        self.assertSetEqual(set(created_cert.tags.values_list("name", flat=True)), {"AI"})

    def test_upload_phases_creates_records(self):
        self.client.force_authenticate(self.admin)
        headers = ["id", "certificate_id", "certificate_name", "phase_name", "phase_type"]
        rows = [
            [901, self.cert.id, "", "필기", "필기"],
            [902, None, self.cert.name, "실기", "실기"],
        ]
        upload = self._xlsx_file(headers, rows, filename="phases.xlsx")
        resp = self.client.post(
            "/api/certificates/upload/phases/",
            {"file": upload},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, {"created": 2, "updated": 0})
        phase_ids = set(self.cert.phases.values_list("id", flat=True))
        self.assertSetEqual(phase_ids, {901, 902})

    def test_upload_statistics_creates_records(self):
        self.client.force_authenticate(self.admin)
        headers = [
            "id",
            "certificate_id",
            "certificate_name",
            "exam_type",
            "year",
            "session",
            "registered",
            "applicants",
            "passers",
            "pass_rate",
        ]
        rows = [[
            1201,
            self.cert.id,
            "",
            "실기",
            2024,
            1,
            "120",
            "110",
            70,
            0.75,
        ], [
            None,
            None,
            self.cert.name,
            "필기",
            2023,
            None,
            800,
            600,
            420,
            70,
        ]]
        upload = self._xlsx_file(headers, rows, filename="stats.xlsx")
        resp = self.client.post(
            "/api/certificates/upload/statistics/",
            {"file": upload},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, {"created": 2, "updated": 0})

        stat = CertificateStatistics.objects.get(pk=1201)
        self.assertEqual(stat.registered, 120)
        self.assertEqual(stat.pass_rate, 75.0)
        second = self.cert.statistics.get(exam_type="필기", year="2023", session=None)
        self.assertEqual(second.applicants, 600)
        self.assertEqual(second.pass_rate, 70.0)
