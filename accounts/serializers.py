from rest_framework import serializers
from .models import User

class UserLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    password = serializers.CharField(required=True, allow_blank=False, allow_null=False)

class UserRegisterSerializer(serializers.Serializer):
    phone = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    password = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    password2 = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ExpoPushTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['expo_push_token']