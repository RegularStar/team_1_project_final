from django.test import TestCase

from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

User = get_user_model()


class UserAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        # 엔드포인트 이름 (users/urls.py에서 name 지정했을 때)
        self.signup_url = reverse("user-register")
        self.jwt_create_url = reverse("token_obtain_pair")
        self.jwt_refresh_url = reverse("token_refresh")
        self.me_url = reverse("user-me")

        # 기본 테스트 유저
        self.username = "tester"
        self.password = "p@ssw0rd123"
        self.email = "tester@example.com"

    def _create_user(self, username=None, email=None, password=None, **extra):
        """DB에 실제 유저를 생성하는 헬퍼"""
        username = username or self.username
        email = email or self.email
        password = password or self.password
        user = User.objects.create(username=username, email=email, **extra)
        user.set_password(password)
        user.save()
        return user

    def _login_and_get_tokens(self, username=None, password=None):
        """JWT access/refresh 토큰을 발급받아 반환"""
        username = username or self.username
        password = password or self.password
        resp = self.client.post(
            self.jwt_create_url,
            {"username": username, "password": password},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        return resp.data["access"], resp.data["refresh"]

    # ---------------------------
    # 회원가입
    # ---------------------------
    def test_signup_success(self):
        payload = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "p@ssw0rd!!",
            "name": "새 유저",
            "phone": "010-1111-2222",
        }
        resp = self.client.post(self.signup_url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)

        # DB에 유저가 생겼는지, 비밀번호가 해시로 저장됐는지 확인
        u = User.objects.get(username="newuser")
        self.assertNotEqual(u.password, payload["password"])
        self.assertTrue(u.check_password(payload["password"]))

    def test_signup_duplicate_username(self):
        self._create_user(username="dupuser", email="dup@example.com")
        resp = self.client.post(
            self.signup_url,
            {"username": "dupuser", "email": "another@example.com", "password": "p@ssw0rd!!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ---------------------------
    # 로그인 (JWT)
    # ---------------------------
    def test_login_jwt_success(self):
        self._create_user()
        resp = self.client.post(
            self.jwt_create_url,
            {"username": self.username, "password": self.password},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_login_jwt_invalid_credentials(self):
        self._create_user()
        resp = self.client.post(
            self.jwt_create_url,
            {"username": self.username, "password": "wrong-pass"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token(self):
        self._create_user()
        access, refresh = self._login_and_get_tokens()
        resp = self.client.post(self.jwt_refresh_url, {"refresh": refresh}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)

    # ---------------------------
    # Me (내 정보)
    # ---------------------------
    def test_me_requires_auth(self):
        resp = self.client.get(self.me_url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_get_success(self):
        # 유저 만들고 로그인
        user = self._create_user(name="홍길동", phone="010-0000-0000")
        access, _ = self._login_and_get_tokens()

        # 인증 헤더 설정
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        # 조회
        resp = self.client.get(self.me_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["username"], user.username)

    def test_me_disallows_modification(self):
        self._create_user()
        access, _ = self._login_and_get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        resp_patch = self.client.patch(self.me_url, {"name": "길동 홍"}, format="json")
        self.assertEqual(resp_patch.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        resp_delete = self.client.delete(self.me_url)
        self.assertEqual(resp_delete.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
