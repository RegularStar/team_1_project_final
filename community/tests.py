from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from community.models import Post, PostComment
from certificates.models import Certificate

User = get_user_model()


def _as_list(data):
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


class CommunityAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="user", password="pass")
        self.admin = User.objects.create_superuser(username="admin", password="adminpass")

        self.cert = Certificate.objects.create(name="정보처리기사", overview="설명")
        self.post = Post.objects.create(user=self.user, title="테스트글", body="본문", certificate=self.cert)
        PostComment.objects.create(user=self.user, post=self.post, body="댓글1")
        PostComment.objects.create(user=self.user, post=self.post, body="댓글2")

        self.post_list_url = "/api/posts/"
        self.post_detail_url = lambda pk: f"/api/posts/{pk}/"
        self.post_comments_url = lambda pk: f"/api/posts/{pk}/comments/"

    def test_post_list_public_ok(self):
        resp = self.client.get(self.post_list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = _as_list(resp.data)
        self.assertGreaterEqual(len(items), 1)
        item = items[0]
        self.assertIn("comment_count", item)
        self.assertIn("like_count", item)

    def test_post_create_sets_owner(self):
        self.client.force_authenticate(self.user)
        payload = {"title": "새글", "body": "내용", "certificate": self.cert.id}
        resp = self.client.post(self.post_list_url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["user"], self.user.id)

    def test_comment_list_on_post_get(self):
        resp = self.client.get(self.post_comments_url(self.post.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = _as_list(resp.data)
        self.assertEqual(len(items), 2)

    def test_comment_create_ok(self):
        self.client.force_authenticate(self.user)
        payload = {"body": "새 댓글"}  # content → body
        resp = self.client.post(self.post_comments_url(self.post.id), payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["user"], self.user.id)