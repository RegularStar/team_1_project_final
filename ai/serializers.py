from rest_framework import serializers

from .models import SupportInquiry


class ChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField()


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField()
    history = ChatMessageSerializer(many=True, required=False)
    temperature = serializers.FloatField(required=False, min_value=0.0, max_value=2.0)

    def validate_history(self, value):
        filtered = []
        for item in value:
            content = item["content"].strip()
            if not content:
                raise serializers.ValidationError("history 항목의 content는 비어있을 수 없습니다.")
            filtered.append({"role": item["role"], "content": content})
        return filtered

    def validate_message(self, value):
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("message는 비어있을 수 없습니다.")
        return stripped


class SupportInquiryCreateSerializer(serializers.Serializer):
    intent = serializers.ChoiceField(choices=[choice[0] for choice in SupportInquiry.Intent.choices])
    summary = serializers.CharField(max_length=255)
    detail = serializers.CharField()
    conversation = serializers.ListField(child=ChatMessageSerializer(), allow_empty=False)

    def validate_summary(self, value):
        summary = value.strip()
        if not summary:
            raise serializers.ValidationError("요약을 입력해주세요.")
        return summary

    def validate_detail(self, value):
        detail = value.strip()
        if not detail:
            raise serializers.ValidationError("문의 상세 내용을 입력해주세요.")
        return detail


class JobRecommendRequestSerializer(serializers.Serializer):
    image = serializers.ImageField(required=False, allow_null=True)
    content = serializers.CharField(required=False, allow_blank=True)
    max_results = serializers.IntegerField(required=False, min_value=1, max_value=10, default=5)

    def validate(self, attrs):
        content = attrs.get("content", "").strip()
        image = attrs.get("image")

        if content:
            attrs["content"] = content

        if not image and not content:
            raise serializers.ValidationError("텍스트를 입력하거나 텍스트가 담긴 이미지를 업로드해주세요.")

        return attrs


class JobOcrRequestSerializer(serializers.Serializer):
    image = serializers.ImageField()
    lang = serializers.CharField(required=False, allow_blank=True, default="kor+eng")

    def validate_lang(self, value):
        value = value.strip()
        return value or "kor+eng"


class JobTagContributionRequestSerializer(serializers.Serializer):
    tag_name = serializers.CharField(max_length=255)
    certificate_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
    )
    job_excerpt = serializers.CharField(required=False, allow_blank=True)

    def validate_tag_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("태그 이름을 입력해주세요.")
        if len(name) < 2:
            raise serializers.ValidationError("태그 이름은 두 글자 이상이어야 합니다.")
        return name

    def validate_certificate_ids(self, value):
        unique_ids = []
        seen = set()
        for item in value:
            if item in seen:
                continue
            seen.add(item)
            unique_ids.append(item)
        return unique_ids
