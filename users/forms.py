from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from certificates.models import Certificate, Tag, UserCertificate

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


class InterestKeywordForm(StyledMixin, forms.Form):
    keyword = forms.CharField(label="관심 태그", max_length=255)

    def clean_keyword(self):
        value = self.cleaned_data.get("keyword", "")
        normalized = str(value).strip()
        if not normalized:
            raise forms.ValidationError("관심 태그를 입력해주세요.")

        # Normalize consecutive spaces to match existing tag formatting expectations.
        normalized = " ".join(normalized.split())

        # Preserve original capitalization but ensure duplicate tags differing only in case reuse existing entry.
        existing = Tag.objects.filter(name__iexact=normalized).first()
        if existing:
            return existing.name
        return normalized


class UserCertificateRequestForm(StyledMixin, forms.ModelForm):
    certificate = forms.ModelChoiceField(
        label="자격증",
        queryset=Certificate.objects.order_by("name"),
        empty_label="자격증을 선택해주세요.",
        widget=forms.HiddenInput,
    )
    acquired_at = forms.DateField(
        label="취득일",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    evidence = forms.FileField(
        label="증빙 자료",
        help_text="이미지 또는 PDF 파일을 업로드하세요.",
    )

    class Meta:
        model = UserCertificate
        fields = ["certificate", "acquired_at", "evidence"]

    def clean_evidence(self):
        file = self.cleaned_data.get("evidence")
        if not file:
            raise forms.ValidationError("증빙 자료를 첨부해주세요.")

        max_size = 5 * 1024 * 1024  # 5MB 기본 제한
        if file.size > max_size:
            raise forms.ValidationError("5MB 이하의 파일만 첨부할 수 있습니다.")
        return file


class AdminExcelUploadForm(forms.Form):
    file = forms.FileField(label="엑셀 파일")
    sheet_name = forms.CharField(label="시트 이름", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            classes = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{classes} form-input".strip()
        self.fields["sheet_name"].widget.attrs.setdefault("placeholder", "기본 시트 사용")

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if not file:
            raise forms.ValidationError("엑셀 파일을 선택해주세요.")
        valid_ext = (".xlsx", ".xlsm", ".xltx", ".xltm")
        if not file.name.lower().endswith(valid_ext):
            raise forms.ValidationError("xlsx 형식의 엑셀 파일을 업로드해주세요.")
        return file
