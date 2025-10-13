from django import forms


class RatingForm(forms.Form):
    difficulty = forms.IntegerField(label="난이도", min_value=1, max_value=10)
    content = forms.CharField(label="후기", widget=forms.Textarea, required=False)
