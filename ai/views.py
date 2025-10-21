import logging

from django.core.exceptions import ImproperlyConfigured
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from certificates.models import Certificate, Tag
from certificates.serializers import CertificateSerializer, TagSerializer
from .models import JobTagContribution, SupportInquiry
from .serializers import (
    ChatRequestSerializer,
    JobOcrRequestSerializer,
    JobRecommendRequestSerializer,
    JobTagContributionRequestSerializer,
    SupportInquiryCreateSerializer,
)
from .services import (
    JobCertificateRecommendationService,
    JobContentFetchError,
    LangChainChatService,
    OCRService,
    OcrError,
)

logger = logging.getLogger(__name__)


class ChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    # JWT 인증을 사용하지 않는 환경에서도 403 대신 401을 반환하도록 인증 클래스를 비워 둔다.
    authentication_classes = []
    serializer_class = ChatRequestSerializer

    def post(self, request):
        _ensure_authenticated(request)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        history = [
            {"role": item["role"], "content": item["content"]}
            for item in data.get("history", [])
            if isinstance(item, dict) and item.get("role") and item.get("content")
        ]
        user_message = data["message"]

        try:
            service = LangChainChatService()
            result = service.run(
                message=user_message,
                history=history,
                temperature=data.get("temperature", 0.3),
            )
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("AI 챗봇 응답 생성 실패: %s", exc)
            fallback_reply = "죄송하지만 지금은 상담을 이용할 수 없어요. 잠시 후 다시 시도해주세요."
            conversation = history + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": fallback_reply},
            ]
            metadata = {
                "intent": "error",
                "needs_admin": False,
                "admin_summary": "",
                "out_of_scope": False,
                "confidence": 0.0,
                "error": "unavailable",
            }
            return Response(
                {"reply": fallback_reply, "history": conversation, "metadata": metadata},
                status=status.HTTP_200_OK,
            )

        reply = result.get("assistant_message") or "죄송하지만 답변을 생성하지 못했습니다."
        intent = result.get("intent") or "general_question"
        needs_admin = bool(result.get("needs_admin"))
        admin_summary = (result.get("admin_summary") or "").strip()
        out_of_scope = bool(result.get("out_of_scope"))
        confidence = float(result.get("confidence") or 0.0)

        if out_of_scope:
            reply = "죄송하지만, 자격증 및 커리어와 직접 관련된 질문에 대해서만 도와드릴 수 있어요."
            needs_admin = False
            admin_summary = ""
            intent = "out_of_scope"

        conversation = history + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": reply},
        ]

        metadata = {
            "intent": intent,
            "needs_admin": needs_admin,
            "admin_summary": admin_summary,
            "out_of_scope": out_of_scope,
            "confidence": confidence,
        }

        return Response(
            {"reply": reply, "history": conversation, "metadata": metadata},
            status=status.HTTP_200_OK,
        )


class JobCertificateRecommendationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = []
    serializer_class = JobRecommendRequestSerializer
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        _ensure_authenticated(request)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = JobCertificateRecommendationService()
        try:
            result = service.recommend(
                image=data.get("image"),
                max_results=data.get("max_results", 5),
                provided_content=data.get("content"),
            )
        except JobContentFetchError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        recommendations = []
        for item in result["recommendations"]:
            certificate = item["certificate"]
            cert_data = CertificateSerializer(certificate, context={"request": request}).data
            recommendations.append(
                {
                    "certificate": cert_data,
                    "score": item["score"],
                    "reasons": item["reasons"],
                }
            )

        response_payload = {
            "job_excerpt": result["job_excerpt"],
            "job_text": result.get("raw_text", ""),
            "analysis": result.get("analysis", {}),
            "recommendations": recommendations,
            "notice": result.get("notice"),
            "missing_keywords": result.get("missing_keywords", []),
            "matched_keywords": result.get("matched_keywords", []),
            "keyword_suggestions": result.get("keyword_suggestions", []),
        }
        return Response(response_payload, status=status.HTTP_200_OK)


class JobOcrView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = JobOcrRequestSerializer

    def post(self, request):
        _ensure_authenticated(request)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = OCRService()
        try:
            text = service.extract_text(data["image"], lang=data.get("lang"))
        except OcrError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response({"text": text}, status=status.HTTP_200_OK)


class JobTagContributionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = []
    parser_classes = [JSONParser]

    def post(self, request):
        _ensure_authenticated(request)
        serializer = JobTagContributionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        normalized_name = data["tag_name"].strip()
        tag = Tag.objects.filter(name__iexact=normalized_name).first()
        tag_created = False
        if tag is None:
            tag = Tag.objects.create(name=normalized_name)
            tag_created = True

        certificate_ids = data["certificate_ids"]
        certificates = list(Certificate.objects.filter(id__in=certificate_ids))
        found_ids = {certificate.id for certificate in certificates}
        missing_ids = sorted(set(certificate_ids) - found_ids)
        if missing_ids:
            raise serializers.ValidationError(
                {"certificate_ids": [f"존재하지 않는 자격증 ID: {missing_ids[0]}"]}
            )

        contribution = JobTagContribution.objects.create(
            user=request.user,
            tag=tag,
            job_excerpt=data.get("job_excerpt", "").strip(),
        )
        contribution.certificates.set(certificates)

        added_certificate_ids: list[int] = []
        already_linked_ids: list[int] = []
        for certificate in certificates:
            if certificate.tags.filter(id=tag.id).exists():
                already_linked_ids.append(certificate.id)
            else:
                certificate.tags.add(tag)
                added_certificate_ids.append(certificate.id)

        if tag_created and added_certificate_ids:
            message = "새 태그를 등록하고 자격증에 연결했습니다."
        elif added_certificate_ids:
            message = "태그를 추가로 연결했습니다."
        elif already_linked_ids:
            message = "이미 연결된 태그와 자격증입니다. 다른 자격증을 선택해보세요."
        else:
            message = "태그 제안을 반영했습니다. 추천 품질 향상에 감사드립니다!"

        response_data = {
            "message": message,
            "tag": TagSerializer(tag, context={"request": request}).data,
            "linked_certificates": [certificate.id for certificate in certificates],
            "tag_created": tag_created,
            "added_certificate_ids": added_certificate_ids,
            "already_linked_ids": already_linked_ids,
        }
        return Response(response_data, status=status.HTTP_201_CREATED)


class SupportInquiryView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = []
    serializer_class = SupportInquiryCreateSerializer

    def post(self, request):
        _ensure_authenticated(request)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        inquiry = SupportInquiry.objects.create(
            user=request.user,
            intent=data["intent"],
            summary=data["summary"][:255],
            detail=data["detail"],
            conversation={"messages": data["conversation"]},
        )

        response = {
            "id": inquiry.id,
            "summary": inquiry.summary,
            "intent": inquiry.intent,
            "status": inquiry.status,
            "created_at": inquiry.created_at,
        }
        return Response(response, status=status.HTTP_201_CREATED)
def _ensure_authenticated(request):
    if not request.user or not request.user.is_authenticated:
        raise NotAuthenticated("Authentication credentials were not provided.")
