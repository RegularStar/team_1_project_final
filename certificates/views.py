# certificates/views.py
from collections import defaultdict

from django.db import transaction
from django.db.models import Value, Sum, Avg
from django.db.models.functions import Coalesce
from django.utils.text import slugify
from openpyxl import load_workbook
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

import re


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
    queryset = Certificate.objects.all()
    serializer_class = CertificateSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "overview", "job_roles", "exam_method", "eligibility", "authority", "type"]
    ordering_fields = ["name", "total_applicants", "avg_difficulty"]

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .prefetch_related("tags")
            .annotate(
                total_applicants=Coalesce(Sum("statistics__applicants"), 0),
                avg_difficulty=Avg("ratings__rating"),
            )
            .order_by("name")
        )

        params = self.request.query_params
        tags_param = params.get("tags")
        if tags_param:
            tag_names = [t.strip() for t in tags_param.split(",") if t.strip()]
            for tag_name in tag_names:
                qs = qs.filter(tags__name__iexact=tag_name)

        type_param = params.get("type")
        if type_param:
            qs = qs.filter(type__iexact=type_param.strip())

        return qs.distinct()

    def _load_worksheet(self, uploaded_file, request):
        wb = load_workbook(uploaded_file, data_only=True)
        sheet_param = request.query_params.get("sheet")
        if sheet_param:
            try:
                return wb[sheet_param]
            except KeyError:
                raise ValueError(f"시트 '{sheet_param}' 를 찾을 수 없습니다. 시트들: {wb.sheetnames}")
        return wb.active

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

        try:
            ws = self._load_worksheet(file, request)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        col = {h: i for i, h in enumerate(headers) if h}

        aliases = {
            "id": ["id", "cert_id", "certificate_id"],
            "name": ["name"],
            "overview": ["overview", "description"],
            "job_roles": ["job_roles"],
            "exam_method": ["exam_method"],
            "eligibility": ["eligibility"],
            "authority": ["authority"],
            "type": ["type"],
            "homepage": ["homepage"],
            "rating": ["rating"],
            "expected_duration": ["expected_duration"],
            "expected_duration_major": ["expected_duration_major"],
            "tags": ["tags"],
        }

        def column_index(key):
            for alias in aliases.get(key, [key]):
                if alias in col:
                    return col[alias]
            return None

        # id, name은 필수
        missing = [key for key in ["id", "name"] if column_index(key) is None]
        if missing:
            return Response({"detail": f"누락된 헤더: {', '.join(missing)}"}, status=400)

        def val(row, key):
            idx = column_index(key)
            if idx is None:
                return None
            return row[idx]

        created, updated, errors = 0, 0, []

        with transaction.atomic():
            for r_index, r in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                if not r:
                    continue

                raw_id = val(r, "id")
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

        payload = {"created": created, "updated": updated}
        status_code = 200
        if errors:
            payload["errors"] = errors
            status_code = 207

    @action(detail=False, methods=["get"], url_path="rankings")
    def rankings(self, request):
        """Return aggregated ranking data for the home page."""

        try:
            limit = int(request.query_params.get("limit", 10))
        except (TypeError, ValueError):
            limit = 10

        limit = max(1, min(limit, 50))

        certificates = list(
            self.get_queryset()
            .annotate(rating_value=Coalesce("rating", Value(0)))
            .prefetch_related("tags")
        )
        if not certificates:
            return Response({"hot": [], "pass": [], "hard": [], "easy": []})

        cert_map = {cert.id: cert for cert in certificates}

        stats_by_cert = defaultdict(lambda: defaultdict(dict))

        stats_qs = (
            CertificateStatistics.objects.filter(certificate_id__in=cert_map)
            .values(
                "certificate_id",
                "exam_type",
                "year",
                "registered",
                "applicants",
                "passers",
            )
        )

        def normalize_stage(exam_type):
            if not exam_type:
                return None
            text = str(exam_type).strip()
            digit_match = re.search(r"\d+", text)
            if digit_match:
                try:
                    return int(digit_match.group())
                except Exception:
                    pass

            lowered = text.lower()
            if any(keyword in lowered for keyword in ["필기", "서류", "이론"]):
                return 1
            if any(keyword in lowered for keyword in ["실기", "실습", "작업"]):
                return 2
            if any(keyword in lowered for keyword in ["면접", "구술"]):
                return 3
            if "최종" in lowered:
                return 4
            return None

        def year_key(year):
            if year is None:
                return (-float("inf"), "")
            year_text = str(year).strip()
            digit_match = re.search(r"\d+", year_text)
            if digit_match:
                try:
                    return (int(digit_match.group()), year_text)
                except Exception:
                    pass
            return (0, year_text)

        def format_stage_label(entry, stage_num):
            labels = entry.get("labels") or []
            if labels:
                # Choose the shortest label for readability
                return sorted(labels, key=len)[0]
            return f"{stage_num}차"

        for stat in stats_qs:
            cert_id = stat["certificate_id"]
            stage = normalize_stage(stat.get("exam_type"))
            if stage is None:
                continue
            year = stat.get("year")
            year_key_text = str(year).strip() if year is not None else None
            stage_map = stats_by_cert[cert_id].setdefault(year_key_text, {})
            entry = stage_map.setdefault(
                stage,
                {"registered": 0, "applicants": 0, "passers": 0, "labels": set()},
            )
            for field in ("registered", "applicants", "passers"):
                value = stat.get(field)
                if value is not None:
                    entry[field] += value
            label = stat.get("exam_type")
            if label:
                entry["labels"].add(str(label))

        cert_metrics = {}
        for cert in certificates:
            year_data = stats_by_cert.get(cert.id, {})
            stage1_years = [
                year
                for year, stages in year_data.items()
                if 1 in stages and any(
                    (stages[1].get(field) or 0) > 0 for field in ("applicants", "registered", "passers")
                )
            ]

            metrics = {
                "recent_year": None,
                "stage1_applicants": None,
                "stage1_label": None,
                "final_stage": None,
                "final_stage_label": None,
                "final_passers": None,
                "pass_rate": None,
            }

            if stage1_years:
                latest_year = max(stage1_years, key=year_key)
                stages = year_data[latest_year]
                stage1_entry = stages.get(1, {})
                applicants = stage1_entry.get("applicants") or 0
                registered = stage1_entry.get("registered") or 0
                stage1_total = applicants if applicants else registered
                stage1_total = stage1_total or 0

                if stage1_total:
                    final_stage_num = max(stages.keys())
                    final_entry = stages.get(final_stage_num, {})
                    final_passers = final_entry.get("passers") or 0
                    pass_rate = None
                    if stage1_total:
                        pass_rate = round(final_passers / stage1_total * 100, 1) if stage1_total > 0 else None

                    metrics.update(
                        {
                            "recent_year": latest_year,
                            "stage1_applicants": stage1_total,
                            "stage1_label": format_stage_label(stage1_entry, 1),
                            "final_stage": final_stage_num,
                            "final_stage_label": format_stage_label(final_entry, final_stage_num),
                            "final_passers": final_passers,
                            "pass_rate": pass_rate,
                        }
                    )

            cert_metrics[cert.id] = metrics

        def base_item(cert):
            tags = list(cert.tags.all())
            primary_tag = tags[0].name if tags else None
            return {
                "id": cert.id,
                "name": cert.name,
                "slug": slugify(cert.name),
                "tag": primary_tag,
                "rating": cert.rating,
            }

        def format_number(value):
            if value is None:
                return None
            try:
                return f"{int(value):,}"
            except Exception:
                return str(value)

        def metric_for_hot(cert, metrics):
            applicants = metrics.get("stage1_applicants")
            year = metrics.get("recent_year")
            label = metrics.get("stage1_label") or "1차"
            if applicants is None:
                return None
            tooltip = None
            if year:
                tooltip = f"{year}년 응시자 수(1차 기준)"
            value = f"{format_number(applicants)}명" if applicants is not None else None
            return {
                "label": "응시자 수",
                "value": value,
                "raw": applicants,
                "tooltip": tooltip,
            }

        def pass_rate_metric(metrics):
            pass_rate = metrics.get("pass_rate")
            year = metrics.get("recent_year")
            stage1_total = metrics.get("stage1_applicants")
            final_passers = metrics.get("final_passers")
            final_label = metrics.get("final_stage_label") or "최종"
            stage1_label = metrics.get("stage1_label") or "1차"
            if pass_rate is None:
                return None
            tooltip = None
            if year is not None and stage1_total is not None and final_passers is not None:
                tooltip = (
                    "본 합격률은 해당 연도의 1차 시험 응시자 수 대비 최종 합격자 수를 기준으로 산출한 수치입니다.\n"
                    "일부 자격증은 시험 면제 제도가 존재하며, 면제자는 통계에서 제외됩니다. \n"
                    "따라서 이로 인해 실제 합격률과 차이가 있을 수 있습니다.\n"
                    f"{year}년 최종 합격자: {format_number(final_passers)}명 "
                    f"({stage1_label}차 응시자 {format_number(stage1_total)}명)"
                )
            return {
                "label": "합격률",
                "value": f"{pass_rate:.1f}%",
                "raw": pass_rate,
                "tooltip": tooltip,
            }

        cert_payloads = []
        for cert in certificates:
            data = base_item(cert)
            data.update(cert_metrics.get(cert.id, {}))
            data["metric_hot"] = metric_for_hot(cert, data)
            data["metric_pass"] = pass_rate_metric(data)
            data["metric_difficulty"] = {
                "label": "난이도",
                "value": f"{cert.rating}/10" if cert.rating is not None else None,
                "raw": cert.rating,
                "tooltipKey": "difficulty-scale",
                "tooltip": DIFFICULTY_GUIDE,
            }
            cert_payloads.append(data)

        def sort_and_build(items, key_func, metric_selector, secondary_selector=None, tertiary_selector=None):
            sorted_items = [item for item in items if key_func(item) is not None]
            sorted_items.sort(key=key_func, reverse=True)
            results = []
            for index, entry in enumerate(sorted_items[:limit], start=1):
                metric = metric_selector(entry)
                secondary = secondary_selector(entry) if secondary_selector else None
                tertiary = tertiary_selector(entry) if tertiary_selector else None
                results.append(
                    {
                        "id": entry["id"],
                        "name": entry["name"],
                        "rank": index,
                        "slug": entry["slug"],
                        "tag": entry.get("tag"),
                        "rating": entry.get("rating"),
                        "metric": metric,
                        "secondary": secondary,
                        "tertiary": tertiary,
                        "difficulty": entry.get("metric_difficulty"),
                    }
                )
            return results

        hot_items = sort_and_build(
            cert_payloads,
            key_func=lambda item: (item.get("metric_hot") or {}).get("raw"),
            metric_selector=lambda item: item.get("metric_hot"),
            secondary_selector=lambda item: item.get("metric_pass"),
        )

        pass_items = sort_and_build(
            cert_payloads,
            key_func=lambda item: (item.get("metric_pass") or {}).get("raw"),
            metric_selector=lambda item: item.get("metric_pass"),
            secondary_selector=lambda item: {
                "label": "응시자 수",
                "value": (
                    f"{format_number(item.get('stage1_applicants'))}명"
                    if item.get("stage1_applicants") is not None
                    else None
                ),
                "tooltip": (
                    f"{item.get('recent_year')}년 {item.get('stage1_label') or '1차'} 응시자 수 (1차 기준)"
                    if item.get("recent_year") and item.get("stage1_applicants") is not None
                    else None
                ),
            },
        )

        hard_items = sort_and_build(
            cert_payloads,
            key_func=lambda item: item.get("rating") if item.get("rating") is not None else None,
            metric_selector=lambda item: item.get("metric_difficulty"),
            secondary_selector=lambda item: item.get("metric_hot"),
            tertiary_selector=lambda item: item.get("metric_pass"),
        )

        easy_items = sort_and_build(
            cert_payloads,
            key_func=lambda item: (
                -item.get("rating") if item.get("rating") is not None else None
            ),
            metric_selector=lambda item: item.get("metric_difficulty"),
            secondary_selector=lambda item: item.get("metric_hot"),
            tertiary_selector=lambda item: item.get("metric_pass"),
        )

        pass_low_items = sort_and_build(
            cert_payloads,
            key_func=lambda item: (
                -((item.get("metric_pass") or {}).get("raw"))
                if (item.get("metric_pass") or {}).get("raw") is not None
                else None
            ),
            metric_selector=lambda item: item.get("metric_pass"),
            secondary_selector=lambda item: {
                "label": "응시자 수",
                "value": (
                    f"{format_number(item.get('stage1_applicants'))}명"
                    if item.get("stage1_applicants") is not None
                    else None
                ),
                "tooltip": (
                    f"{item.get('recent_year')}년 {item.get('stage1_label') or '1차'} 응시자 수 (1차 기준)"
                    if item.get("recent_year") and item.get("stage1_applicants") is not None
                    else None
                ),
            },
        )

        data = {
            "hot": hot_items,
            "pass": pass_items,
            "pass_low": pass_low_items,
            "hard": hard_items,
            "easy": easy_items,
        }

        return Response(data)


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
        """자격증 단계 일괄 업로드."""
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file 필드를 포함해 업로드하세요."}, status=400)

        try:
            ws = self._load_worksheet(file, request)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        col = {h: i for i, h in enumerate(headers) if h}

        aliases = {
            "id": ["id"],
            "certificate_id": ["certificate_id", "cert_id"],
            "certificate_name": ["certificate_name", "cert_name"],
            "phase_name": ["phase_name"],
            "phase_type": ["phase_type", "phase_category"],
        }

        def column_index(key):
            for alias in aliases.get(key, [key]):
                if alias in col:
                    return col[alias]
            return None

        def val(row, key):
            idx = column_index(key)
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
                if cert is None:
                    raw_cert_name = val(r, "certificate_name")
                    if raw_cert_name not in (None, ""):
                        cert = Certificate.objects.filter(name=str(raw_cert_name).strip()).first()
                if cert is None:
                    continue

                raw_phase_name = val(r, "phase_name")
                phase_name = str(raw_phase_name).strip() if raw_phase_name not in (None, "") else None
                if not phase_name:
                    continue

                raw_phase_type = val(r, "phase_type")
                phase_type = str(raw_phase_type).strip() if raw_phase_type not in (None, "") else ""

                if phase_id is not None:
                    defaults = {
                        "certificate": cert,
                        "phase_name": phase_name,
                        "phase_type": phase_type,
                    }
                    _, is_created = CertificatePhase.objects.update_or_create(
                        id=phase_id,
                        defaults=defaults,
                    )
                else:
                    _, is_created = CertificatePhase.objects.update_or_create(
                        certificate=cert,
                        phase_name=phase_name,
                        phase_type=phase_type,
                        defaults={},
                    )

                created += int(is_created)
                updated += int(not is_created)

        return Response({"created": created, "updated": updated}, status=200)

    @action(
        detail=False,
        methods=["post"],
        url_path="upload/statistics",
        permission_classes=[permissions.IsAdminUser],
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_statistics(self, request):
        """자격증 통계 일괄 업로드."""
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file 필드를 포함해 업로드하세요."}, status=400)

        try:
            ws = self._load_worksheet(file, request)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        col = {h: i for i, h in enumerate(headers) if h}

        aliases = {
            "id": ["id", "stat_id", "cert_stats_id"],
            "certificate_id": ["certificate_id", "cert_id"],
            "certificate_name": ["certificate_name", "cert_name"],
            "exam_type": ["exam_type"],
            "year": ["year"],
            "session": ["session"],
            "registered": ["registered", "registerd"],
            "applicants": ["applicants"],
            "passers": ["passers"],
            "pass_rate": ["pass_rate"],
        }

        def column_index(key):
            for alias in aliases.get(key, [key]):
                if alias in col:
                    return col[alias]
            return None

        def val(row, key):
            idx = column_index(key)
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

                stat_id = to_int(val(r, "id"))

                cert = None
                cert_pk = to_int(val(r, "certificate_id"))
                if cert_pk is not None:
                    cert = Certificate.objects.filter(id=cert_pk).first()
                if cert is None:
                    raw_cert_name = val(r, "certificate_name")
                    if raw_cert_name not in (None, ""):
                        cert = Certificate.objects.filter(name=str(raw_cert_name).strip()).first()
                if cert is None:
                    continue

                exam_type = str(val(r, "exam_type") or "").strip() or "필기"
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
                    _, is_created = CertificateStatistics.objects.update_or_create(
                        id=stat_id,
                        defaults=defaults,
                    )
                else:
                    _, is_created = CertificateStatistics.objects.update_or_create(
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


# ---- Phase ----
class CertificatePhaseViewSet(viewsets.ModelViewSet):
    queryset = CertificatePhase.objects.select_related("certificate").all()
    serializer_class = CertificatePhaseSerializer
    permission_classes = [IsAdminOrReadOnly]


# ---- Statistics ----
class CertificateStatisticsViewSet(viewsets.ModelViewSet):
    queryset = CertificateStatistics.objects.select_related("certificate").all()
    serializer_class = CertificateStatisticsSerializer
    permission_classes = [IsAdminOrReadOnly]


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

DIFFICULTY_GUIDE = (
    "난이도 안내\n"
    "1: 아주 쉬움. 기초 개념 위주라 단기간 준비로 누구나 합격 가능한 수준.\n"
    "2: 쉬움. 기본 지식이 있으면 무난히 도전할 수 있는 입문 수준.\n"
    "3: 보통. 일정한 학습이 필요하지만 꾸준히 준비하면 충분히 합격 가능한 수준.\n"
    "4: 다소 어려움. 이론과 실무를 균형 있게 요구하며, 준비 기간이 다소 긴 수준.\n"
    "5: 중상 난이도. 전공지식과 응용력이 필요해 체계적 학습이 요구되는 수준.\n"
    "6: 어려움. 합격률이 낮고 심화 학습이 필요해 전공자도 부담되는 수준.\n"
    "7: 매우 어려움. 방대한 범위와 높은 난이도로 전공자도 장기간 학습이 필수인 수준.\n"
    "8: 극히 어려움. 전문성·응용력·실무 경험이 모두 요구되는 최상위권 자격 수준.\n"
    "9: 최상 난이도. 전문지식과 실무를 총망라하며, 합격자가 극소수에 불과한 수준.\n"
    "10: 극한 난이도. 수년간 전념해도 합격을 장담할 수 없는, 최고 난도의 자격 수준."
)
