from django import forms

from certificates.models import Certificate
from .models import Post, PostComment


class PostForm(forms.ModelForm):
    certificate = forms.ModelChoiceField(
        queryset=Certificate.objects.order_by("name"),
        required=True,
        label="자격증 선택",
    )

    class Meta:
        model = Post
        fields = ["certificate", "title", "body", "image"]
        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "제목을 입력해주세요.",
            }),
            "body": forms.Textarea(attrs={
                "rows": 8,
                "placeholder": "내용을 입력해주세요.",
            }),
            "image": forms.ClearableFileInput(attrs={
                "accept": "image/*",
            }),
        }
        labels = {
            "title": "제목",
            "body": "내용",
            "image": "이미지 (선택)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["certificate"].widget.attrs.update({"id": "board-select"})
        self.fields["certificate"].empty_label = "게시판 선택"
        self.fields["title"].widget.attrs.setdefault("id", "post-title")
        self.fields["body"].widget.attrs.setdefault("id", "post-body")
        self.fields["image"].widget.attrs.setdefault("id", "post-image")


class PostCommentForm(forms.ModelForm):
    class Meta:
        model = PostComment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "댓글을 입력해주세요.",
            }),
        }
        labels = {
            "body": "댓글",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].widget.attrs.setdefault("id", "comment")
