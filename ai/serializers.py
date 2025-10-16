from rest_framework import serializers


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


class JobRecommendRequestSerializer(serializers.Serializer):
    image = serializers.ImageField()
    content = serializers.CharField(required=False, allow_blank=True)
    max_results = serializers.IntegerField(required=False, min_value=1, max_value=10, default=5)

    def validate(self, attrs):
        content = attrs.get("content", "").strip()
        if content:
            attrs["content"] = content
        return attrs


class JobOcrRequestSerializer(serializers.Serializer):
    image = serializers.ImageField()
    lang = serializers.CharField(required=False, allow_blank=True, default="kor+eng")

    def validate_lang(self, value):
        value = value.strip()
        return value or "kor+eng"
