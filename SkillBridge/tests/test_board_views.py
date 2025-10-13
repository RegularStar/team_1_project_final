from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.text import slugify

from certificates.models import Certificate
from community.models import Post, PostComment, PostLike


User = get_user_model()


class BoardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="writer", password="testpass123")
        self.other = User.objects.create_user(username="reader", password="testpass456")
        self.certificate = Certificate.objects.create(name="데이터 분석 개발자")
        self.post = Post.objects.create(
            user=self.user,
            certificate=self.certificate,
            title="첫 번째 게시글",
            body="게시글 본문",
        )
        self.comment = PostComment.objects.create(
            user=self.other,
            post=self.post,
            body="기존 댓글",
        )
        self.slug = slugify(self.certificate.name) or str(self.certificate.pk)

    def test_board_list_shows_posts_from_database(self):
        url = reverse("board_list", args=[self.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.post.title)
        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.paginator.count, 1)

    def test_board_detail_shows_comments(self):
        url = reverse("board_detail", args=[self.slug, self.post.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.comment.body)
        self.assertEqual(response.context["like_count"], 0)

    def test_comment_create_requires_login(self):
        url = reverse("board_detail", args=[self.slug, self.post.id])
        response = self.client.post(url, {"body": "익명 댓글"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("login")))
        self.assertEqual(self.post.comments.count(), 1)

    def test_comment_create_success(self):
        self.client.login(username="reader", password="testpass456")
        url = reverse("board_detail", args=[self.slug, self.post.id])
        response = self.client.post(url, {"body": "새 댓글"})
        self.assertEqual(response.status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.comments.count(), 2)

    def test_board_create_creates_post_for_authenticated_user(self):
        self.client.login(username="writer", password="testpass123")
        url = reverse("board_create")
        response = self.client.post(
            url,
            {
                "certificate": self.certificate.id,
                "title": "새 게시글",
                "body": "내용",
            },
        )
        self.assertEqual(response.status_code, 302)
        new_post = Post.objects.get(title="새 게시글")
        self.assertEqual(new_post.user, self.user)

    def test_board_like_toggle(self):
        self.client.login(username="reader", password="testpass456")
        like_url = reverse("board_toggle_like", args=[self.slug, self.post.id])
        response = self.client.post(like_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PostLike.objects.filter(user=self.other, post=self.post).exists())

        response = self.client.post(like_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PostLike.objects.filter(user=self.other, post=self.post).exists())

    def test_board_edit_updates_post(self):
        self.client.login(username="writer", password="testpass123")
        url = reverse("board_edit", args=[self.slug, self.post.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        payload = {
            "certificate": self.certificate.id,
            "title": "수정된 제목",
            "body": "수정된 본문",
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "수정된 제목")

    def test_board_edit_forbidden_for_non_owner(self):
        self.client.login(username="reader", password="testpass456")
        url = reverse("board_edit", args=[self.slug, self.post.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_board_delete_removes_post(self):
        self.client.login(username="writer", password="testpass123")
        url = reverse("board_delete", args=[self.slug, self.post.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Post.objects.filter(id=self.post.id).exists())

    def test_board_delete_forbidden_for_non_owner(self):
        self.client.login(username="reader", password="testpass456")
        url = reverse("board_delete", args=[self.slug, self.post.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
