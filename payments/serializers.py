# payments/serializers.py
from rest_framework import serializers
from .models import Payment


class CreatePaymentSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=99)
    amount = serializers.IntegerField(min_value=1)
    expires_at = serializers.DateTimeField(required=False)


class PaymentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "user_guid", "description", "amount", "status", "status_display",
            "qr_code_url","providers", "expires_at",
            "executed_at", "created_at",
        ]
        read_only_fields = fields


class BePayWebhookSerializer(serializers.Serializer):
    """То, что BePay присылает на твой webhook-URL при смене статуса."""
    uuid = serializers.UUIDField()               # bepay transaction id
    status = serializers.IntegerField()
    qr_transaction_id = serializers.UUIDField(required=False)
    amount = serializers.IntegerField()
    user_guid = serializers.UUIDField(required=False)