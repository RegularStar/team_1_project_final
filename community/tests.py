from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from .models import Post, PostComment, PostLike

User = get_user_model()


# ✅ 헬퍼: 페이지네이션 응답이면 results만 반환
def _as_list(data):
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


class CommunityAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()

        # 유저 2명 + 관리자
        self.user1 = User.objects.create_user(username="user1", email="u1@example.com", password="pass12345")
        self.user2 = User.objects.create_user(username="user2", email="u2@example.com", password="pass12345")
        self.admin = User.objects.create_user(username="admin", email="admin@example.com", password="pass12345",
                                              is_staff=True, is_superuser=True)

        # user1의 게시글
        self.post1 = Post.objects.create(user=self.user1, title="첫 글", body="본문입니다")

        # 엔드포인트
        self.post_list_url = reverse("post-list")
        self.post_detail_url = lambda pk: reverse("post-detail", args=[pk])
        self.post_like_url = lambda pk: reverse("post-like", args=[pk])
        self.post_comments_url = lambda post_id: reverse("post-comments", kwargs={"post_id": post_id})
        self.comment_detail_url = lambda cid: reverse("comment-detail", kwargs={"comment_id": cid})

    # -----------------------------
    # 게시글 목록/조회
    # -----------------------------
    def test_post_list_public_ok(self):
        resp = self.client.get(self.post_list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = _as_list(resp.data)
        self.assertGreaterEqual(len(items), 1)
        item = items[0]
        self.assertIn("comment_count", item)
        self.assertIn("like_count", item)

    def test_post_detail_public_ok(self):
        resp = self.client.get(self.post_detail_url(self.post1.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["id"], self.post1.id)

    # -----------------------------
    # 게시글 생성/수정/삭제
    # -----------------------------
    def test_post_create_requires_auth(self):
        payload = {"title": "비로그인 작성", "body": "안됨"}
        resp = self.client.post(self.post_list_url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_post_create_sets_owner(self):
        self.client.force_authenticate(user=self.user2)
        payload = {"title": "user2의 글", "body": "내용"}
        resp = self.client.post(self.post_list_url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        post = Post.objects.get(id=resp.data["id"])
        self.assertEqual(post.user_id, self.user2.id)

    def test_post_update_owner_only(self):
        self.client.force_authenticate(user=self.user2)
        resp = self.client.patch(self.post_detail_url(self.post1.id), {"title": "수정"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.user1)
        resp = self.client.patch(self.post_detail_url(self.post1.id), {"title": "작성자 수정"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["title"], "작성자 수정")

    def test_post_delete_owner_returns_200(self):
        self.client.force_authenticate(user=self.user1)
        resp = self.client.delete(self.post_detail_url(self.post1.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Post.objects.filter(id=self.post1.id).exists())

    def test_post_delete_admin_can_delete_others_returns_200(self):
        post = Post.objects.create(user=self.user1, title="지울글", body="to delete")
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.post_detail_url(post.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Post.objects.filter(id=post.id).exists())

    # -----------------------------
    # 좋아요 토글
    # -----------------------------
    def test_like_toggle_returns_200_and_counts_change(self):
        self.client.force_authenticate(user=self.user2)
        resp = self.client.post(self.post_like_url(self.post1.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(PostLike.objects.filter(user=self.user2, post=self.post1).exists())

        detail = self.client.get(self.post_detail_url(self.post1.id)).data
        self.assertEqual(detail["like_count"], 1)

        resp = self.client.delete(self.post_like_url(self.post1.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(PostLike.objects.filter(user=self.user2, post=self.post1).exists())

        detail = self.client.get(self.post_detail_url(self.post1.id)).data
        self.assertEqual(detail["like_count"], 0)

    # -----------------------------
    # 댓글 목록/작성
    # -----------------------------
    def test_comment_list_on_post_get(self):
        PostComment.objects.create(user=self.user1, post=self.post1, body="c1")
        PostComment.objects.create(user=self.user2, post=self.post1, body="c2")

        url = self.post_comments_url(self.post1.id)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = _as_list(resp.data)
        self.assertEqual(len(items), 2)

    def test_comment_create_requires_auth(self):
        url = self.post_comments_url(self.post1.id)
        resp = self.client.post(url, {"body": "비로그인 댓글"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_comment_create_ok(self):
        self.client.force_authenticate(user=self.user2)
        url = self.post_comments_url(self.post1.id)
        resp = self.client.post(url, {"body": "user2 댓글"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        cid = resp.data["id"]
        self.assertTrue(PostComment.objects.filter(id=cid, user=self.user2, post=self.post1).exists())

        detail = self.client.get(self.post_detail_url(self.post1.id)).data
        self.assertEqual(detail["comment_count"], 1)

    # -----------------------------
    # 댓글 수정/삭제
    # -----------------------------
    def test_comment_update_owner_only(self):
        c = PostComment.objects.create(user=self.user1, post=self.post1, body="원본")
        url = self.comment_detail_url(c.id)

        self.client.force_authenticate(user=self.user2)
        resp = self.client.patch(url, {"body": "수정시도"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.user1)
        resp = self.client.patch(url, {"body": "작성자수정"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["body"], "작성자수정")

    def test_comment_delete_owner_returns_200(self):
        c = PostComment.objects.create(user=self.user1, post=self.post1, body="지울댓글")
        url = self.comment_detail_url(c.id)

        self.client.force_authenticate(user=self.user1)
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(PostComment.objects.filter(id=c.id).exists())

    def test_comment_delete_admin_can_delete_others_returns_200(self):
        c = PostComment.objects.create(user=self.user1, post=self.post1, body="지울댓글")
        url = self.comment_detail_url(c.id)

        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(PostComment.objects.filter(id=c.id).exists())

    # -----------------------------
    # 검색/정렬
    # -----------------------------
    def test_post_search_and_ordering(self):
        Post.objects.create(user=self.user1, title="데이터 분석", body="내용")
        Post.objects.create(user=self.user1, title="운동 일지", body="내용")

        resp = self.client.get(self.post_list_url + "?search=분석")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = _as_list(resp.data)
        self.assertEqual(len(items), 1)

        resp = self.client.get(self.post_list_url + "?ordering=created_at")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = _as_list(resp.data)
        self.assertGreaterEqual(len(items), 2)