# certificates/views.py
from django.db import transaction
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from openpyxl import load_workbook


def to_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


from .models import (
    Tag,
    Certificate,
    CertificatePhase,
    CertificateStatistics,
    UserTag,
    UserCertificate,
)
from .serializers import (
    TagSerializer,
    CertificateSerializer,
    CertificatePhaseSerializer,
    CertificateStatisticsSerializer,
    UserTagSerializer,
    UserCertificateSerializer,
)


class IsAdminOrReadOnly(permissions.BasePermission):
    """GET은 모두, POST/PATCH/DELETE는 관리자만"""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


# ---- Tag ----
class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().order_by("name")
    serializer_class = TagSerializer
    permission_classes = [IsAdminOrReadOnly]


# ---- Certificate ----
class CertificateViewSet(viewsets.ModelViewSet):
    queryset = Certificate.objects.all().order_by("name")
    serializer_class = CertificateSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "overview", "job_roles", "exam_method", "eligibility", "authority", "type"]
    ordering_fields = ["name"]

    @action(
        detail=False,
        methods=["post"],
        url_path="upload/certificates",
        permission_classes=[permissions.IsAdminUser],
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_certificates(self, request):
        """
        XLSX 업로드 (자격증 마스터 전용)
        ✅ 엑셀 맨 앞 열 'id'를 Certificate.pk로 **그대로 사용** (필수)
        ✅ 시트 선택: ?sheet=Certificates (없으면 첫 번째 시트 사용)

        예상 헤더(필수: id, name):
          id, name, overview, job_roles, exam_method, eligibility,
          authority, type, homepage, rating, expected_duration, expected_duration_major, tags

        - 동일 id가 있으면 갱신, 없으면 해당 id로 생성
        - name은 unique라 충돌 시 에러에 기록
        - tags: 'AI,데이터,국가기술' 콤마 구분, 제공 시 set(덮어쓰기), 빈 문자열/None이면 clear()
        """
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file 필드를 포함해 업로드하세요."}, status=400)

        wb = load_workbook(file, data_only=True)

        # 시트 선택(없으면 첫 시트)
        sheet_param = request.query_params.get("sheet")
        try:
            ws = wb[sheet_param] if sheet_param else wb.active
        except KeyError:
            return Response({"detail": f"시트 '{sheet_param}' 를 찾을 수 없습니다. 시트들: {wb.sheetnames}"}, status=400)

        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        col = {h: i for i, h in enumerate(headers) if h}

        # id, name은 필수
        required = ["cert_id", "name"]
        missing = [h for h in required if h not in col]
        if missing:
            return Response({"detail": f"누락된 헤더: {', '.join(missing)}"}, status=400)

        def val(row, key):
            idx = col.get(key)
            if idx is None:
                return None
            return row[idx]

        created, updated, errors = 0, 0, []

        with transaction.atomic():
            for r_index, r in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                if not r:
                    continue

                raw_id = val(r, "cert_id")
                raw_name = val(r, "name")

                # 필수 값 체크
                if raw_id in (None, "") or raw_name in (None, ""):
                    errors.append(f"{r_index}행: id 또는 name 누락")
                    continue

                try:
                    cid = int(raw_id)
                except Exception:
                    errors.append(f"{r_index}행: id가 정수가 아닙니다 → {raw_id}")
                    continue

                defaults = {
                    "name": str(raw_name).strip(),
                    "overview": (str(val(r, "overview")).strip() if val(r, "overview") is not None else ""),
                    "job_roles": (str(val(r, "job_roles")).strip() if val(r, "job_roles") is not None else ""),
                    "exam_method": (str(val(r, "exam_method")).strip() if val(r, "exam_method") is not None else ""),
                    "eligibility": (str(val(r, "eligibility")).strip() if val(r, "eligibility") is not None else ""),
                    "authority": (str(val(r, "authority")).strip() if val(r, "authority") is not None else ""),
                    "type": (str(val(r, "type")).strip() if val(r, "type") is not None else ""),
                    "homepage": (str(val(r, "homepage")).strip() if val(r, "homepage") is not None else ""),
                    "rating": to_int(val(r, "rating")),
                    "expected_duration": to_int(val(r, "expected_duration")),
                    "expected_duration_major": to_int(val(r, "expected_duration_major")),
                }

                try:
                    # 동일 PK가 있으면 갱신, 없으면 명시적 PK로 생성
                    obj = Certificate.objects.filter(pk=cid).first()
                    if obj:
                        for k, v in defaults.items():
                            setattr(obj, k, v)
                        obj.save()
                        updated += 1
                    else:
                        obj = Certificate(id=cid, **defaults)
                        obj.save()
                        created += 1

                    # 태그 동기화(열이 존재할 때만)
                    if "tags" in col:
                        tags_cell = val(r, "tags")
                        if tags_cell in (None, ""):
                            obj.tags.clear()
                        else:
                            tag_names = [t.strip() for t in str(tags_cell).split(",") if t and str(t).strip()]
                            if tag_names:
                                tag_objs = []
                                for tname in tag_names:
                                    tag, _ = Tag.objects.get_or_create(name=tname)
                                    tag_objs.append(tag)
                                obj.tags.set(tag_objs)
                            else:
                                obj.tags.clear()

                except Exception as e:
                    # name unique 충돌 등 모든 예외를 수집
                    errors.append(f"{r_index}행: 오류 - {e}")

        return Response(
            {"created": created, "updated": updated, "errors": errors},
            status=(200 if not errors else 207),
        )


# ---- Phase ----
class CertificatePhaseViewSet(viewsets.ModelViewSet):
    queryset = CertificatePhase.objects.select_related("certificate").all()
    serializer_class = CertificatePhaseSerializer
    permission_classes = [IsAdminOrReadOnly]

    @action(
        detail=False,
        methods=["post"],
        url_path="upload/phases",
        permission_classes=[permissions.IsAdminUser],
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_phases(self, request):
        """
        XLSX 업로드 (자격증 단계)
        예상 헤더:
          id, certificate_id, certificate_name, phase_name, phase_type
        - certificate_id로 FK를 우선 매칭하고, 없으면 certificate_name으로 보조 매칭
        - id를 지정하면 해당 PK로 생성/갱신
        """
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file 필드를 포함해 업로드하세요."}, status=400)

        wb = load_workbook(file, data_only=True)
        ws = wb.active
        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        col = {h: i for i, h in enumerate(headers) if h}

        def val(row, key):
            idx = col.get(key)
            if idx is None:
                return None
            return row[idx]

        created, updated = 0, 0
        with transaction.atomic():
            for r in ws.iter_rows(min_row=2, values_only=True):
                if not r:
                    continue
                phase_id = to_int(val(r, "id"))
                cert = None

                cert_pk = to_int(val(r, "certificate_id"))
                if cert_pk is not None:
                    cert = Certificate.objects.filter(id=cert_pk).first()
                if cert is None and "certificate_name" in col:
                    raw_cert_name = val(r, "certificate_name")
                    if raw_cert_name not in (None, ""):
                        cert = Certificate.objects.filter(name=str(raw_cert_name).strip()).first()
                if cert is None:
                    continue

                phase_name = (str(val(r, "phase_name")).strip() if val(r, "phase_name") not in (None, "") else None)
                if not phase_name:
                    continue
                phase_type = (str(val(r, "phase_type")).strip() if val(r, "phase_type") not in (None, "") else "")

                if phase_id is not None:
                    defaults = {
                        "certificate": cert,
                        "phase_name": phase_name,
                        "phase_type": phase_type,
                    }
                    obj, is_created = CertificatePhase.objects.update_or_create(
                        id=phase_id,
                        defaults=defaults,
                    )
                else:
                    obj, is_created = CertificatePhase.objects.update_or_create(
                        certificate=cert,
                        phase_name=phase_name,
                        phase_type=phase_type,
                        defaults={},
                    )
                created += int(is_created)
                updated += int(not is_created)

        return Response({"created": created, "updated": updated}, status=200)


# ---- Statistics ----
class CertificateStatisticsViewSet(viewsets.ModelViewSet):
    queryset = CertificateStatistics.objects.select_related("certificate").all()
    serializer_class = CertificateStatisticsSerializer
    permission_classes = [IsAdminOrReadOnly]

    @action(
        detail=False,
        methods=["post"],
        url_path="upload/statistics",
        permission_classes=[permissions.IsAdminUser],
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_statistics(self, request):
        """
        XLSX 업로드 (자격증 통계)
        예상 헤더:
          id, certificate_id, certificate_name, exam_type, year, session,
          registered, applicants, passers, pass_rate
        - certificate_id로 FK를 우선 매칭하고, 없으면 certificate_name으로 보조 매칭
        - pass_rate: 0~1 또는 0~100 형태 모두 허용 (저장은 0~100, 소수 1자리)
        """
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file 필드를 포함해 업로드하세요."}, status=400)

        wb = load_workbook(file, data_only=True)
        ws = wb.active
        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        col = {h: i for i, h in enumerate(headers) if h}

        aliases = {
            "registered": ["registered", "registerd"],
        }
        for canonical, keys in aliases.items():
            if canonical not in col:
                for k in keys:
                    if k in col:
                        col[canonical] = col[k]
                        break

        def val(row, key):
            idx = col.get(key)
            if idx is None:
                return None
            return row[idx]

        def normalize_rate(x):
            if x in (None, ""):
                return None
            try:
                f = float(x)
                if 0 <= f <= 1:
                    return round(f * 100, 1)
                if 0 <= f <= 100:
                    return round(f, 1)
            except Exception:
                pass
            return None

        created, updated = 0, 0
        with transaction.atomic():
            for r in ws.iter_rows(min_row=2, values_only=True):
                if not r:
                    continue

                stat_id = to_int(val(r, "cert_stats_id"))

                cert = None
                cert_pk = to_int(val(r, "cert_id"))
                if cert_pk is not None:
                    cert = Certificate.objects.filter(id=cert_pk).first()
                if cert is None and "certificate_name" in col:
                    raw_cert_name = val(r, "certificate_name")
                    if raw_cert_name not in (None, ""):
                        cert = Certificate.objects.filter(name=str(raw_cert_name).strip()).first()
                if cert is None:
                    continue

                exam_type = (str(val(r, "exam_type")).strip() if val(r, "exam_type") not in (None, "") else "필기")
                year_raw = val(r, "year")
                year = str(year_raw).strip() if year_raw not in (None, "") else None
                if not year:
                    continue
                session = to_int(val(r, "session"))
                registered = to_int(val(r, "registered"))
                applicants = to_int(val(r, "applicants"))
                passers = to_int(val(r, "passers"))
                pass_rate = normalize_rate(val(r, "pass_rate"))

                if stat_id is not None:
                    defaults = {
                        "certificate": cert,
                        "exam_type": exam_type,
                        "year": year,
                        "session": session,
                        "registered": registered,
                        "applicants": applicants,
                        "passers": passers,
                        "pass_rate": pass_rate,
                    }
                    obj, is_created = CertificateStatistics.objects.update_or_create(
                        id=stat_id,
                        defaults=defaults,
                    )
                else:
                    obj, is_created = CertificateStatistics.objects.update_or_create(
                        certificate=cert,
                        exam_type=exam_type,
                        year=year,
                        session=session,
                        defaults={
                            "registered": registered,
                            "applicants": applicants,
                            "passers": passers,
                            "pass_rate": pass_rate,
                        },
                    )
                created += int(is_created)
                updated += int(not is_created)

        return Response({"created": created, "updated": updated}, status=200)


# ---- UserTag (내 태그만 관리) ----
class UserTagViewSet(viewsets.ModelViewSet):
    serializer_class = UserTagSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserTag.objects.select_related("tag").filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ---- UserCertificate (내 취득 자격증 관리) ----
class UserCertificateViewSet(viewsets.ModelViewSet):
    serializer_class = UserCertificateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserCertificate.objects.select_related("certificate").filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)