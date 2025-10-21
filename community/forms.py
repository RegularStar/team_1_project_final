from django import forms

from certificates.models import Certificate
from .models import Post, PostComment


class PostForm(forms.ModelForm):
<<<<<<< HEAD
=======
    remove_image = forms.BooleanField(required=False, label="이미지 삭제")

>>>>>>> seil2
    certificate = forms.ModelChoiceField(
        queryset=Certificate.objects.order_by("name"),
        required=True,
        label="자격증 선택",
    )

    class Meta:
        model = Post
<<<<<<< HEAD
        fields = ["certificate", "title", "body"]
=======
        fields = ["certificate", "title", "body", "image"]
>>>>>>> seil2
        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "제목을 입력해주세요.",
            }),
            "body": forms.Textarea(attrs={
                "rows": 8,
                "placeholder": "내용을 입력해주세요.",
            }),
<<<<<<< HEAD
=======
            "image": forms.FileInput(attrs={
                "accept": "image/*",
            }),
        }
        labels = {
            "title": "제목",
            "body": "내용",
            "image": "이미지 (선택)",
>>>>>>> seil2
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["certificate"].widget.attrs.update({"id": "board-select"})
        self.fields["certificate"].empty_label = "게시판 선택"
        self.fields["title"].widget.attrs.setdefault("id", "post-title")
        self.fields["body"].widget.attrs.setdefault("id", "post-body")
<<<<<<< HEAD
=======
        self.fields["image"].widget.attrs.setdefault("id", "post-image")
        self.fields["remove_image"].widget.attrs.setdefault("id", "remove-image")
        if not self.instance or not getattr(self.instance, "image", None):
            self.fields["remove_image"].widget = forms.HiddenInput()
        else:
            self.fields["remove_image"].label = "현재 이미지 삭제"
            self.fields["remove_image"].widget.attrs.setdefault("class", "image-upload__remove-checkbox")

    def save(self, commit=True):
        post = super().save(commit=False)
        remove_image = self.cleaned_data.get("remove_image")
        new_image = self.cleaned_data.get("image")

        if remove_image and not new_image:
            if post.pk and post.image:
                post.image.delete(save=False)
            post.image = None

        if commit:
            post.save()
            self.save_m2m()
        return post
>>>>>>> seil2


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
