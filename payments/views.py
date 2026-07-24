# payments/views.py
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status

from .models import Payment
from .serializers import (
    CreatePaymentSerializer, PaymentSerializer, BePayWebhookSerializer,
)
from .services import BePayClient, BePayError


class CreatePaymentView(APIView):

    def post(self, request):

        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data


        payment = Payment.objects.create(
            description=data["description"],
            amount=data["amount"],
            expires_at=data.get("expires_at"),
        )


        try:

            bepay_response = BePayClient().generate_qr(
                description=payment.description,
                amount=payment.amount,
                expires_at=payment.expires_at,
                user_guid=payment.user_guid,
            )


        except BePayError as e:

            payment.status = Payment.STATUS_ERROR
            payment.save()

            return Response(
                {
                    "detail": e.detail
                },
                status=400
            )


        bepay_uuid = bepay_response.get("uuid")


        if not bepay_uuid:

            payment.status = Payment.STATUS_ERROR
            payment.save()

            return Response(
                {
                    "detail": "Не получен uuid от BePay",
                    "bepay_response": bepay_response
                },
                status=400
            )


        payment.bepay_uuid = bepay_uuid
        payment.qr_code_url = bepay_response.get(
            "qrCode",
            ""
        )

        payment.providers = bepay_response.get(
            "providers",
            []
        )

        payment.status = bepay_response.get(
            "status",
            Payment.STATUS_CREATED
        )

        payment.save()


        return Response(
            PaymentSerializer(payment).data,
            status=201
        )

class PaymentStatusView(APIView):
    """Фронт может периодически опрашивать статус (запасной вариант к webhook)."""

    def get(self, request, user_guid):
        payment = Payment.objects.get(user_guid=user_guid)

        if not payment.is_final() and payment.bepay_uuid:
            try:
                data = BePayClient().get_status(payment.bepay_uuid)
                _apply_status_update(payment, data)
            except BePayError:
                pass  # отдаём последний известный локальный статус

        return Response(PaymentSerializer(payment).data)


class BePayWebhookView(APIView):
    """
    URL этого view нужно вписать в личном кабинете BePay как
    Success/Result webhook. BePay сам, без участия фронта,
    стукнется сюда при изменении статуса оплаты.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = BePayWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        try:
            payment = Payment.objects.get(
                bepay_uuid=payload.get("qr_transaction_id") or payload["uuid"]
            )
        except Payment.DoesNotExist:
            return Response(status=http_status.HTTP_404_NOT_FOUND)

        _apply_status_update(payment, payload)
        return Response(status=http_status.HTTP_200_OK)


def _apply_status_update(payment: Payment, data: dict):
    new_status = data.get("status")
    if new_status is None or payment.status == new_status:
        return
    payment.status = new_status
    if new_status == Payment.STATUS_SUCCESS:
        payment.executed_at = timezone.now()
        # здесь: пометить заказ оплаченным, снять товар с резерва,
        # отправить уведомление пользователю и т.д.
    payment.save()