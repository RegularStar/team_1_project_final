from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class StyledMixin:
    def _update_widgets(self):
        for name, field in self.fields.items():
            classes = field.widget.attrs.get("class", "")
            classes = f"{classes} form-input".strip()
            field.widget.attrs["class"] = classes
            field.widget.attrs.setdefault("placeholder", field.label)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._update_widgets()
        for field in self.fields.values():
            field.help_text = ""


class SignInForm(StyledMixin, AuthenticationForm):
    username = forms.CharField(label="아이디", max_length=150)
    password = forms.CharField(label="비밀번호", widget=forms.PasswordInput)


class SignUpForm(StyledMixin, UserCreationForm):
    username = forms.CharField(label="아이디", max_length=150)
    name = forms.CharField(label="이름", max_length=255, required=False)
    email = forms.EmailField(label="이메일", required=False)
    password1 = forms.CharField(label="비밀번호", widget=forms.PasswordInput)
    password2 = forms.CharField(label="비밀번호 확인", widget=forms.PasswordInput)
    field_order = ["username", "name", "email", "password1", "password2"]

    class Meta:
        model = User
        fields = ("username", "name", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.name = self.cleaned_data.get("name", "")
        user.email = self.cleaned_data.get("email", "")
        if commit:
            user.save()
        return user
