import logging
from datetime import timedelta
 
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
 
from core.models import RepaymentSchedule, OsagoApplication
from core.osago_service import confirm_and_save
from .models import Payment
from .serializers import PaymentSerializer, BePayWebhookSerializer
from .services import BePayClient, BePayError
from core.telegram_notify import notify_payment_success
 
logger = logging.getLogger(__name__)
 
QR_LIFETIME_MINUTES = 15
 
 
# ---------------------------------------------------------
# ОБЩАЯ ЧАСТЬ
# ---------------------------------------------------------
 
def _generate_qr(payment: Payment):
    """Сходить в BePay за QR и сохранить результат в платёж."""
    expires_at = timezone.now() + timedelta(minutes=QR_LIFETIME_MINUTES)
 
    try:
        bepay_response = BePayClient().generate_qr(
            description=payment.description,
            amount=payment.amount,
            user_guid=payment.user_guid,
            expires_at=expires_at,
        )
    except BePayError as e:
        payment.status = Payment.STATUS_ERROR
        payment.save(update_fields=["status"])
        return Response({"detail": e.detail}, status=e.status_code)
 
    if not bepay_response.get("uuid"):
        payment.status = Payment.STATUS_ERROR
        payment.save(update_fields=["status"])
        logger.error("BePay не вернул uuid для платежа %s", payment.id)
        return Response({"detail": "Не получен uuid от BePay"}, status=502)
 
    payment.bepay_uuid = bepay_response["uuid"]
    payment.qr_code_url = bepay_response.get("qrCode", "")
    payment.qr_base64 = bepay_response.get("qr_base64", "")
    payment.providers = bepay_response.get("providers", [])
    payment.expires_at = expires_at
    payment.save()
 
    return Response(PaymentSerializer(payment).data, status=http_status.HTTP_201_CREATED)
 
 
# ---------------------------------------------------------
# 1. ОПЛАТА ПЛАТЕЖА ПО ГРАФИКУ (как было, ничего не изменилось)
# ---------------------------------------------------------
 
class CreateRepaymentPaymentView(APIView):
    """
    Создать QR для оплаты платежа из графика погашения.
 
    Фронт присылает только repayment_schedule_id.
    Сумма берётся из базы — с фронта не принимается.
    """
    permission_classes = [IsAuthenticated]
 
    @extend_schema(
        summary="Оплатить платёж по графику",
        responses=PaymentSerializer,
        tags=["Платежи"],
    )
    def post(self, request):
        repayment_id = request.data.get("repayment_schedule_id")
        if not repayment_id:
            raise ValidationError({"error": "Не передан repayment_schedule_id"})
 
        try:
            repayment = RepaymentSchedule.objects.select_related("car_client").get(
                id=repayment_id,
                car_client__client=request.user.client,
            )
        except RepaymentSchedule.DoesNotExist:
            raise ValidationError({"error": "Платёж не найден или не принадлежит вам"})
 
        if repayment.is_paid == "is_paid":
            return Response({"error": "Этот платёж уже оплачен"}, status=400)
 
        amount_tyiyn = int((repayment.total_payment * 100).to_integral_value())
 
        payment = Payment.objects.create(
            purpose=Payment.PURPOSE_REPAYMENT,
            client=request.user.client,
            repayment_schedule=repayment,
            description=f"Платёж по графику #{repayment.id}"[:99],
            amount=amount_tyiyn,
        )
 
        return _generate_qr(payment)
 
 
# ---------------------------------------------------------
# 2. ОПЛАТА ПОЛИСА ОСАГО (новое)
# ---------------------------------------------------------
 
class CreateOsagoPaymentView(APIView):
    """
    Создать QR для оплаты полиса ОСАГО.
 
    Фронт присылает только osago_application_id.
    Сумма берётся из заявки — её вернул Сакбол на шаге create_osago.
    """
    permission_classes = [IsAuthenticated]
 
    @extend_schema(
        summary="Оплатить полис ОСАГО",
        responses=PaymentSerializer,
        description="После успешной оплаты полис выпускается автоматически.",
        tags=["ОСАГО"],
    )
    def post(self, request):
        application_id = request.data.get("osago_application_id")
        if not application_id:
            raise ValidationError({"error": "Не передан osago_application_id"})
 
        application = get_object_or_404(
            OsagoApplication, id=application_id, client=request.user.client
        )
 
        if application.status == OsagoApplication.STATUS_CONFIRMED:
            return Response({"error": "Полис уже выпущен"}, status=400)
 
        if not application.external_guid or not application.premiya_insurance:
            return Response(
                {"error": "Заявка не создана в страховой, оплата невозможна"},
                status=400
            )
 
        # если живой QR уже есть — отдаём его, а не создаём второй
        active = application.payments.filter(
            status__in=[Payment.STATUS_CREATED, Payment.STATUS_IN_PROCESS],
            expires_at__gt=timezone.now(),
        ).first()
        if active:
            return Response(PaymentSerializer(active).data, status=200)
 
        payment = Payment.objects.create(
            purpose=Payment.PURPOSE_OSAGO,
            client=request.user.client,
            osago_application=application,
            description=f"ОСАГО {application.client_car.car_number}"[:99],
            amount=application.premium_tyiyn,
        )
 
        return _generate_qr(payment)
 
 
# ---------------------------------------------------------
# 3. СТАТУС ПЛАТЕЖА (общий для обоих видов)
# ---------------------------------------------------------
 
class PaymentStatusView(APIView):
    """Опрос статуса платежа. Работает и для графика, и для ОСАГО."""
    permission_classes = [IsAuthenticated]
 
    @extend_schema(summary="Статус платежа", responses=PaymentSerializer, tags=["Платежи"])
    def get(self, request, user_guid):
        # Проверка владельца по прямому FK client.
        # Раньше шла через repayment_schedule — для ОСАГО так не работает.
        payment = get_object_or_404(
            Payment, user_guid=user_guid, client=request.user.client
        )
 
        if not payment.is_final() and payment.bepay_uuid:
            try:
                data = BePayClient().get_status(payment.bepay_uuid)
                _apply_status_update(payment, data)
            except BePayError:
                pass  # отдаём последний известный локальный статус
 
        return Response(PaymentSerializer(payment).data)
 
 
# ---------------------------------------------------------
# 4. ВЕБХУК BEPAY
# ---------------------------------------------------------
 
class BePayWebhookView(APIView):
    """
    Этот URL вписывается в личном кабинете BePay.
    BePay стучится сюда сам, когда меняется статус оплаты.
    """
    authentication_classes = []
    permission_classes = []
 
    def post(self, request):
        serializer = BePayWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
 
        try:
            payment = Payment.objects.get(
                bepay_uuid=payload.get("transaction_id") or payload["uuid"]
            )
        except Payment.DoesNotExist:
            logger.warning("BePay webhook: платёж не найден, uuid=%s", payload.get("uuid"))
            return Response(status=http_status.HTTP_404_NOT_FOUND)
 
        # Телу вебхука не доверяем: подписи у него нет.
        # Используем его только как сигнал "иди проверь статус".
        try:
            verified = BePayClient().get_status(payment.bepay_uuid)
        except BePayError as e:
            logger.warning("BePay webhook: не удалось проверить статус: %s", e)
            return Response(status=http_status.HTTP_202_ACCEPTED)
 
        _apply_status_update(payment, verified)
        return Response(status=http_status.HTTP_200_OK)
 
 
def _apply_status_update(payment: Payment, data: dict):
    """
    Обновляет статус платежа.
    Что делать дальше — зависит от назначения платежа.
    """
    new_status = data.get("status")
    if new_status is None or payment.status == new_status:
        return
 
    payment.status = new_status
 
    if new_status == Payment.STATUS_SUCCESS:
        payment.executed_at = timezone.now()
 
        if payment.purpose == Payment.PURPOSE_REPAYMENT:
            _on_repayment_paid(payment)
        elif payment.purpose == Payment.PURPOSE_OSAGO:
            _on_osago_paid(payment)
 
    payment.save()

    if new_status == Payment.STATUS_SUCCESS:
        notify_payment_success(payment)
 
 
def _on_repayment_paid(payment: Payment):
    """Платёж по графику оплачен — помечаем строку графика."""
    schedule = payment.repayment_schedule
    if not schedule or schedule.is_paid == "is_paid":
        return
 
    schedule.is_paid = "is_paid"
    schedule.is_paid_1c = "is_paid"
    schedule.save(update_fields=["is_paid", "is_paid_1c"])
    logger.info("График #%s оплачен через BePay", schedule.id)
 
 
def _on_osago_paid(payment: Payment):
    """
    Полис оплачен — теперь можно вызывать confirm_osago,
    который списывает деньги с баланса компании у Сакбола.
    """
    application = payment.osago_application
    if not application or application.status == OsagoApplication.STATUS_CONFIRMED:
        return
 
    application.status = OsagoApplication.STATUS_PAID
    application.save(update_fields=["status"])
 
    # Если Сакбол недоступен — статус останется paid,
    # и OsagoStatusView попробует снова при следующем опросе.
    confirm_and_save(application)
 