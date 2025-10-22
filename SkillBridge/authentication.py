from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session 인증을 사용하되 DRF의 CSRF 검사만 비활성화한다."""

    def enforce_csrf(self, request):
        return

