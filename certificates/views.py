from rest_framework import viewsets, permissions, status
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
    """GET/HEAD/OPTIONS만 모두 허용, 그 외(POST/PATCH/DELETE)는 관리자만"""
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
    queryset = Certificate.objects.all().order_by("name")
    serializer_class = CertificateSerializer
    permission_classes = [ReadOnlyOrAdmin]

    @action(
        detail=False, methods=["post"], url_path="upload/certificates",
        permission_classes=[permissions.IsAdminUser], parser_classes=[MultiPartParser, FormParser]
    )
    def upload_certificates(self, request):
        """
        엑셀(자격증) 업로드
        헤더 예: name, description, authority, cert_type, homepage, rating, expected_duration, expected_duration_major, tags
        tags는 'AI,데이터,국가기술'처럼 콤마 구분
        """
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file 필수"}, status=400)

        wb = load_workbook(file, data_only=True)
        ws = wb.active
        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        col = {h: i for i, h in enumerate(headers)}

        created, updated = 0, 0
        with transaction.atomic():
            for r in ws.iter_rows(min_row=2, values_only=True):
                if not r or col.get("name") is None or not r[col["name"]]:
                    continue
                name = str(r[col["name"]]).strip()

                def val(key):
                    idx = col.get(key)
                    if idx is None:
                        return None
                    return r[idx]

                defaults = {
                    "description": (str(val("description")).strip() if val("description") is not None else ""),
                    "authority": (str(val("authority")).strip() if val("authority") is not None else ""),
                    "cert_type": (str(val("cert_type")).strip() if val("cert_type") is not None else ""),
                    "homepage": (str(val("homepage")).strip() if val("homepage") is not None else ""),
                    "rating": (int(val("rating")) if val("rating") is not None else None),
                    "expected_duration": (int(val("expected_duration")) if val("expected_duration") is not None else None),
                    "expected_duration_major": (int(val("expected_duration_major")) if val("expected_duration_major") is not None else None),
                }

                obj, created_flag = Certificate.objects.update_or_create(name=name, defaults=defaults)
                created += int(created_flag)
                updated += int(not created_flag)

                # 태그 처리
                tags_val = val("tags")
                if tags_val:
                    tag_names = [t.strip() for t in str(tags_val).split(",") if t and str(t).strip()]
                    for tname in tag_names:
                        tag, _ = Tag.objects.get_or_create(name=tname)
                        CertificateTag.objects.get_or_create(certificate=obj, tag=tag)

        return Response({"created": created, "updated": updated}, status=200)


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
        헤더 예: certificate_name, phase_name, phase_type(필기/실기)
        """
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file 필수"}, status=400)

        wb = load_workbook(file, data_only=True)
        ws = wb.active
        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        col = {h: i for i, h in enumerate(headers)}

        created, updated = 0, 0
        with transaction.atomic():
            for r in ws.iter_rows(min_row=2, values_only=True):
                if not r or col.get("certificate_name") is None or not r[col["certificate_name"]]:
                    continue

                def val(key):
                    idx = col.get(key)
                    if idx is None:
                        return None
                    return r[idx]

                cert_name = str(val("certificate_name")).strip()
                phase_name = (str(val("phase_name")).strip() if val("phase_name") is not None else "")
                phase_type = (str(val("phase_type")).strip() if val("phase_type") is not None else "필기")

                cert = Certificate.objects.filter(name=cert_name).first()
                if not cert:
                    # 자격증이 없으면 건너뜀(필요 시 생성 로직 추가 가능)
                    continue

                obj, created_flag = CertificatePhase.objects.update_or_create(
                    certificate=cert, phase_name=phase_name, phase_type=phase_type, defaults={}
                )
                created += int(created_flag)
                updated += int(not created_flag)

        return Response({"created": created, "updated": updated}, status=200)


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
        헤더 예: certificate_name, exam_type, year, session, registered, applicants, passers, pass_rate(0~1)
        """
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file 필수"}, status=400)

        wb = load_workbook(file, data_only=True)
        ws = wb.active
        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        col = {h: i for i, h in enumerate(headers)}

        created, updated = 0, 0
        with transaction.atomic():
            for r in ws.iter_rows(min_row=2, values_only=True):
                if not r or col.get("certificate_name") is None or not r[col["certificate_name"]]:
                    continue

                def val(key):
                    idx = col.get(key)
                    if idx is None:
                        return None
                    return r[idx]

                cert_name = str(val("certificate_name")).strip()
                cert = Certificate.objects.filter(name=cert_name).first()
                if not cert:
                    continue

                exam_type = (str(val("exam_type")).strip() if val("exam_type") is not None else "필기")
                year = (int(val("year")) if val("year") is not None else None)
                session = (str(val("session")).strip() if val("session") is not None else None)
                registered = (int(val("registered")) if val("registered") is not None else None)
                applicants = (int(val("applicants")) if val("applicants") is not None else None)
                passers = (int(val("passers")) if val("passers") is not None else None)
                pass_rate = val("pass_rate")
                if pass_rate is not None:
                    try:
                        pass_rate = float(pass_rate)
                    except Exception:
                        pass_rate = None

                if year is None:
                    continue

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

        return Response({"created": created, "updated": updated}, status=200)


# ----- UserTag (내 태그 관리) -----
class UserTagViewSet(viewsets.ModelViewSet):
    queryset = UserTag.objects.select_related("user", "tag").all()
    serializer_class = UserTagSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)