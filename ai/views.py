from django.core.exceptions import ImproperlyConfigured
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from certificates.serializers import CertificateSerializer

from .serializers import ChatRequestSerializer, JobRecommendRequestSerializer
from .services import (
    LangChainChatService,
    JobCertificateRecommendationService,
    JobContentFetchError,
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
                "recommendations": recommendations,
            },
            status=status.HTTP_200_OK,
        )
