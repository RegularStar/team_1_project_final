# certificates/views.py
from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from openpyxl import load_workbook

from .models import (
    Tag, Certificate, CertificateTag,
    CertificatePhase, CertificateStatistics, UserTag
)
from .serializers import (
    TagSerializer, CertificateSerializer,
    CertificatePhaseSerializer, CertificateStatisticsSerializer, UserTagSerializer
)


class ReadOnlyOrAdmin(permissions.BasePermission):
    """GET/HEAD/OPTIONS 모두 허용, 그 외(POST/PATCH/DELETE)는 관리자만"""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and (request.user.is_staff or request.user.is_superuser))


# ----- Tag -----
class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().order_by("name")
    serializer_class = TagSerializer
    permission_classes = [ReadOnlyOrAdmin]


# ----- Certificate -----
class CertificateViewSet(viewsets.ModelViewSet):
    """
    /api/certificates/  (GET list, POST create[admin], ...)
    """
    queryset = Certificate.objects.all().order_by("name")
    serializer_class = CertificateSerializer
    permission_classes = [ReadOnlyOrAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "overview", "job_roles", "exam_method", "eligibility", "authority", "type"]
    ordering_fields = ["name"]
    ordering = ["name"]

    @action(
        detail=False, methods=["post"], url_path="upload/certificates",
        permission_classes=[permissions.IsAdminUser], parser_classes=[MultiPartParser, FormParser]
    )
    def upload_certificates(self, request):
        """
        엑셀(자격증) 업로드
        헤더 예:
          name, overview, job_roles, exam_method, eligibility,
          authority, type, homepage, rating, expected_duration, expected_duration_major, tags
        - tags는 'AI,데이터,국가기술' 처럼 콤마(,) 구분 문자열
        """
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file 필수"}, status=status.HTTP_400_BAD_REQUEST)

        wb = load_workbook(file, data_only=True)
        ws = wb.active
        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        col = {h: i for i, h in enumerate(headers)}

        def val(row, key):
            idx = col.get(key)
            if idx is None:
                return None
            return row[idx]

        created, updated = 0, 0
        with transaction.atomic():
            for r in ws.iter_rows(min_row=2, values_only=True):
                if not r or col.get("name") is None or not r[col["name"]]:
                    continue
                name = str(r[col["name"]]).strip()

                # 숫자형 안전 캐스팅
                def to_int(x):
                    try:
                        return int(x) if x is not None and str(x).strip() != "" else None
                    except Exception:
                        return None

                defaults = {
                    "overview":            (str(val(r, "overview")).strip() if val(r, "overview") is not None else ""),
                    "job_roles":           (str(val(r, "job_roles")).strip() if val(r, "job_roles") is not None else ""),
                    "exam_method":         (str(val(r, "exam_method")).strip() if val(r, "exam_method") is not None else ""),
                    "eligibility":         (str(val(r, "eligibility")).strip() if val(r, "eligibility") is not None else ""),
                    "authority":           (str(val(r, "authority")).strip() if val(r, "authority") is not None else ""),
                    "type":                (str(val(r, "type")).strip() if val(r, "type") is not None else ""),
                    "homepage":            (str(val(r, "homepage")).strip() if val(r, "homepage") is not None else ""),
                    "rating":              to_int(val(r, "rating")),
                    "expected_duration":   to_int(val(r, "expected_duration")),
                    "expected_duration_major": to_int(val(r, "expected_duration_major")),
                }

                obj, created_flag = Certificate.objects.update_or_create(name=name, defaults=defaults)
                created += int(created_flag)
                updated += int(not created_flag)

                # 태그 처리
                tags_val = val(r, "tags")
                if tags_val:
                    tag_names = [t.strip() for t in str(tags_val).split(",") if t and str(t).strip()]
                    for tname in tag_names:
                        tag, _ = Tag.objects.get_or_create(name=tname)
                        CertificateTag.objects.get_or_create(certificate=obj, tag=tag)

        return Response({"created": created, "updated": updated}, status=status.HTTP_200_OK)


# ----- Phase -----
class CertificatePhaseViewSet(viewsets.ModelViewSet):
    queryset = CertificatePhase.objects.select_related("certificate").all()
    serializer_class = CertificatePhaseSerializer
    permission_classes = [ReadOnlyOrAdmin]

    @action(
        detail=False, methods=["post"], url_path="upload/phases",
        permission_classes=[permissions.IsAdminUser], parser_classes=[MultiPartParser, FormParser]
    )
    def upload_phases(self, request):
        """
        엑셀(단계) 업로드
        헤더 예: certificate_name, phase_name, phase_type(필기/실기 등)
        """
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file 필수"}, status=status.HTTP_400_BAD_REQUEST)

        wb = load_workbook(file, data_only=True)
        ws = wb.active
        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        col = {h: i for i, h in enumerate(headers)}

        def val(row, key):
            idx = col.get(key)
            if idx is None:
                return None
            return row[idx]

        created, updated = 0, 0
        with transaction.atomic():
            for r in ws.iter_rows(min_row=2, values_only=True):
                if not r or col.get("certificate_name") is None or not r[col["certificate_name"]]:
                    continue

                cert_name = str(val(r, "certificate_name")).strip()
                phase_name = (str(val(r, "phase_name")).strip() if val(r, "phase_name") is not None else "")
                phase_type = (str(val(r, "phase_type")).strip() if val(r, "phase_type") is not None else "필기")

                cert = Certificate.objects.filter(name=cert_name).first()
                if not cert:
                    # 자격증이 없으면 건너뜀(필요 시 자동 생성 로직을 추가할 수 있음)
                    continue

                obj, created_flag = CertificatePhase.objects.update_or_create(
                    certificate=cert, phase_name=phase_name, phase_type=phase_type, defaults={}
                )
                created += int(created_flag)
                updated += int(not created_flag)

        return Response({"created": created, "updated": updated}, status=status.HTTP_200_OK)


# ----- Statistics -----
class CertificateStatisticsViewSet(viewsets.ModelViewSet):
    queryset = CertificateStatistics.objects.select_related("certificate").all()
    serializer_class = CertificateStatisticsSerializer
    permission_classes = [ReadOnlyOrAdmin]

    @action(
        detail=False, methods=["post"], url_path="upload/statistics",
        permission_classes=[permissions.IsAdminUser], parser_classes=[MultiPartParser, FormParser]
    )
    def upload_statistics(self, request):
        """
        엑셀(통계) 업로드
        헤더 예: certificate_name, exam_type, year, session, registered, applicants, passers, pass_rate(0~1 또는 0~100)
        - year: 문자열로 저장(ERD: VARCHAR)
        - session: 정수 변환 시도
        - pass_rate: 숫자로 파싱(소수/정수 허용)
        """
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file 필수"}, status=status.HTTP_400_BAD_REQUEST)

        wb = load_workbook(file, data_only=True)
        ws = wb.active
        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        col = {h: i for i, h in enumerate(headers)}

        def val(row, key):
            idx = col.get(key)
            if idx is None:
                return None
            return row[idx]

        def to_int(x):
            try:
                return int(x) if x is not None and str(x).strip() != "" else None
            except Exception:
                return None

        def to_float(x):
            try:
                return float(x) if x is not None and str(x).strip() != "" else None
            except Exception:
                return None

        created, updated = 0, 0
        with transaction.atomic():
            for r in ws.iter_rows(min_row=2, values_only=True):
                if not r or col.get("certificate_name") is None or not r[col["certificate_name"]]:
                    continue

                cert_name = str(val(r, "certificate_name")).strip()
                cert = Certificate.objects.filter(name=cert_name).first()
                if not cert:
                    continue

                exam_type = (str(val(r, "exam_type")).strip() if val(r, "exam_type") is not None else "필기")
                # ERD: year VARCHAR → 문자열로 저장
                year_raw = val(r, "year")
                year = str(year_raw).strip() if year_raw is not None else None
                if not year:
                    continue  # year는 키

                session = to_int(val(r, "session"))
                registered = to_int(val(r, "registered"))
                applicants = to_int(val(r, "applicants"))
                passers = to_int(val(r, "passers"))

                pass_rate = to_float(val(r, "pass_rate"))
                # pass_rate가 1.0 이하(0~1)로 들어오면 0~100 스케일로 환산하고 싶다면 아래 주석 해제
                # if pass_rate is not None and pass_rate <= 1:
                #     pass_rate = round(pass_rate * 100, 1)

                obj, created_flag = CertificateStatistics.objects.update_or_create(
                    certificate=cert, exam_type=exam_type, year=year, session=session,
                    defaults={
                        "registered": registered,
                        "applicants": applicants,
                        "passers": passers,
                        "pass_rate": pass_rate,
                    }
                )
                created += int(created_flag)
                updated += int(not created_flag)

        return Response({"created": created, "updated": updated}, status=status.HTTP_200_OK)


# ----- UserTag (내 태그 관리) -----
class UserTagViewSet(viewsets.ModelViewSet):
    queryset = UserTag.objects.select_related("user", "tag").all()
    serializer_class = UserTagSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)