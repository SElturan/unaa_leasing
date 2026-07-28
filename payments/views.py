# payments/views.py
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from datetime import timedelta

from core.models import RepaymentSchedule
from .models import Payment
from .serializers import (
    CreatePaymentSerializer, PaymentSerializer, BePayWebhookSerializer,
)
from .services import BePayClient, BePayError


class CreateRepaymentPaymentView(APIView):
    """Создать QR для оплаты конкретного платежа из графика погашения."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        repayment_id = request.data.get("repayment_schedule_id")
        if not repayment_id:
            raise ValidationError({"error": "Не передан repayment_schedule_id"})

        try:
            repayment = RepaymentSchedule.objects.select_related("car_client").get(
                id=repayment_id,
                car_client__client=request.user.client,   # проверка владения!
            )
        except RepaymentSchedule.DoesNotExist:
            raise ValidationError({"error": "Платёж не найден или не принадлежит вам"})

        if repayment.is_paid == "is_paid":
            return Response({"error": "Этот платёж уже оплачен"}, status=400)

        # сумма — только из БД, в сомах с копейками (Decimal)
        amount_som = repayment.total_payment
        amount_tyiyn = int((amount_som * 100).to_integral_value())  # 15400.00 сом → 1540000 тыйын

        payment = Payment.objects.create(
            description=f"Платёж по графику #{repayment.id}",
            amount=amount_tyiyn,
            repayment_schedule=repayment,
        )

        expires_at = (timezone.now() + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            bepay_response = BePayClient().generate_qr(
                description=payment.description,
                amount=payment.amount,
                user_guid=payment.user_guid,
                expires_at=expires_at,   # НОВОЕ
            )
        except BePayError as e:
            payment.status = Payment.STATUS_ERROR
            payment.save(update_fields=["status"])
            return Response({"detail": e.detail}, status=e.status_code)

        payment.bepay_uuid = bepay_response["uuid"]
        payment.qr_code_url = bepay_response.get("qrCode", "")
        payment.providers = bepay_response.get("providers", [])
        payment.save()

        return Response(PaymentSerializer(payment).data, status=201)

class PaymentStatusView(APIView):
    """Фронт может периодически опрашивать статус (запасной вариант к webhook)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_guid):
        payment = get_object_or_404(
            Payment,
            user_guid=user_guid,
            repayment_schedule__car_client__client=request.user.client,
        )

        if not payment.is_final() and payment.bepay_uuid:
            try:
                data = BePayClient().get_status(payment.bepay_uuid)
                _apply_status_update(payment, data)
            except BePayError:
                pass  # отдаём последний известный локальный статус

        return Response(PaymentSerializer(payment).data)


class BePayWebhookView(APIView):
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

        # Перепроверяем статус напрямую у BePay, не доверяя только телу вебхука
        try:
            verified_data = BePayClient().get_status(payment.bepay_uuid)
        except BePayError:
            return Response(status=http_status.HTTP_202_ACCEPTED)  # попробуем при следующем вебхуке/поллинге

        _apply_status_update(payment, verified_data)
        return Response(status=http_status.HTTP_200_OK)


def _apply_status_update(payment: Payment, data: dict):
    new_status = data.get("status")
    if new_status is None or payment.status == new_status:
        return

    payment.status = new_status

    if new_status == Payment.STATUS_SUCCESS:
        payment.executed_at = timezone.now()

        # НОВОЕ: если платёж привязан к конкретной строке графика — помечаем оплаченным
        if payment.repayment_schedule and payment.repayment_schedule.is_paid != "is_paid":
            repayment = payment.repayment_schedule
            repayment.is_paid = "is_paid"
            repayment.save(update_fields=["is_paid"])

    payment.save()