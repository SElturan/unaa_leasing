from rest_framework import serializers

class UserLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    password = serializers.CharField(required=True, allow_blank=False, allow_null=False)