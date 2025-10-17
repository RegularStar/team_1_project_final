from django.core.exceptions import ImproperlyConfigured
from rest_framework import permissions, serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.authentication import JWTAuthentication

from certificates.models import Certificate, Tag
from certificates.serializers import CertificateSerializer, TagSerializer

from .serializers import (
    ChatRequestSerializer,
    JobRecommendRequestSerializer,
    JobOcrRequestSerializer,
    JobTagContributionRequestSerializer,
)
from .services import (
    LangChainChatService,
    JobCertificateRecommendationService,
    JobContentFetchError,
    OCRService,
    OcrError,
)

from .models import JobTagContribution


class ChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChatRequestSerializer
    authentication_classes = [SessionAuthentication, JWTAuthentication]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            service = LangChainChatService()
            reply = service.run(
                message=data["message"],
                history=data.get("history"),
                temperature=data.get("temperature", 0.3),
            )
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception:
            return Response(
                {"detail": "AI 응답 생성 중 오류가 발생했습니다."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        conversation = data.get("history", []) + [{"role": "assistant", "content": reply}]
        return Response({"reply": reply, "history": conversation}, status=status.HTTP_200_OK)


class JobCertificateRecommendationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = JobRecommendRequestSerializer
    parser_classes = [MultiPartParser, FormParser]
    authentication_classes = [SessionAuthentication, JWTAuthentication]

    def post(self, request):
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

        return Response(
            {
                "job_excerpt": result["job_excerpt"],
                "job_text": result.get("raw_text", ""),
                "analysis": result.get("analysis", {}),
                "recommendations": recommendations,
                "notice": result.get("notice"),
                "missing_keywords": result.get("missing_keywords", []),
                "matched_keywords": result.get("matched_keywords", []),
                "keyword_suggestions": result.get("keyword_suggestions", []),
            },
            status=status.HTTP_200_OK,
        )


class JobOcrView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = JobOcrRequestSerializer
    authentication_classes = [SessionAuthentication, JWTAuthentication]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        image = data["image"]
        lang = data.get("lang")

        service = OCRService()
        try:
            text = service.extract_text(image, lang=lang)
        except OcrError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response({"text": text}, status=status.HTTP_200_OK)


class JobTagContributionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    parser_classes = [JSONParser]

    def post(self, request):
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

        response_message = "태그 제안을 반영했습니다. 추천 품질 향상에 감사드립니다!"
        if tag_created and added_certificate_ids:
            response_message = "새 태그를 등록하고 자격증에 연결했습니다."
        elif added_certificate_ids and not tag_created:
            response_message = "태그를 추가로 연결했습니다."
        elif not added_certificate_ids and already_linked_ids:
            response_message = "이미 연결된 태그와 자격증입니다. 다른 자격증을 선택해보세요."

        response_data = {
            "message": response_message,
            "tag": TagSerializer(tag, context={"request": request}).data,
            "linked_certificates": [certificate.id for certificate in certificates],
            "tag_created": tag_created,
            "added_certificate_ids": added_certificate_ids,
            "already_linked_ids": already_linked_ids,
        }
        return Response(response_data, status=status.HTTP_201_CREATED)
