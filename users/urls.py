from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import SignupView, MeView

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),          # 회원가입
    path('me/', MeView.as_view(), name='me'),                      # 내 정보 조회/수정/삭제
    path('jwt/create/', TokenObtainPairView.as_view(), name='jwt_obtain'),   # 로그인(JWT)
    path('jwt/refresh/', TokenRefreshView.as_view(), name='jwt_refresh'),
]