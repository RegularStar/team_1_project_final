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
    url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    content = serializers.CharField(required=False, allow_blank=True)
    max_results = serializers.IntegerField(required=False, min_value=1, max_value=10, default=5)

    def validate(self, attrs):
        url = attrs.get("url")
        if url in ("", None):
            url = None
        attrs["url"] = url

        content = attrs.get("content", "")
        content = content.strip()
        if content:
            attrs["content"] = content
        else:
            attrs["content"] = ""

        if not url and not content:
            raise serializers.ValidationError("채용공고 URL 또는 내용을 최소 한 가지 입력해주세요.")

        return attrs
