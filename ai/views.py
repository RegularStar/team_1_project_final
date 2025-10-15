from django.core.exceptions import ImproperlyConfigured
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from certificates.serializers import CertificateSerializer

from .serializers import ChatRequestSerializer, JobRecommendRequestSerializer, JobOcrRequestSerializer
from .services import (
    LangChainChatService,
    JobCertificateRecommendationService,
    JobContentFetchError,
    OCRService,
    OcrError,
)


class ChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChatRequestSerializer

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

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = JobCertificateRecommendationService()
        try:
            result = service.recommend(
                url=data["url"],
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
                "url": data["url"],
                "job_excerpt": result["job_excerpt"],
                "job_text": result.get("raw_text", ""),
                "analysis": result.get("analysis", {}),
                "recommendations": recommendations,
                "notice": result.get("notice"),
            },
            status=status.HTTP_200_OK,
        )


class JobOcrView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = JobOcrRequestSerializer

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
