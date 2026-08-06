from celery import shared_task
from django.db.models import Q
from django.utils import timezone
from datetime import date, timedelta

from .models import RepaymentSchedule, Notification, OsagoApplication
from .telegram_notify import notify_daily_summary
from .expo_push import send_push_message
from accounts.models import User

import logging
 
from .sync_1c import sync_full, import_from_1c, OneCError
 
# Точки напоминания. Отрицательные — "за N дней до", положительные — "через N дней после".
PAYMENT_REMINDER_DAYS_BEFORE = [3, 1, 0]        # за 3 дня, за 1 день, в день платежа
PAYMENT_REMINDER_DAYS_AFTER = [1, 3, 7, 14, 30]  # потом раз в 2 недели, дальше — тишина

INSURANCE_REMINDER_DAYS_BEFORE = [30, 14, 7, 3, 1]
INSURANCE_REMINDER_DAYS_AFTER = [1, 7, 30]


logger = logging.getLogger(__name__)
 
 
@shared_task(bind=True, max_retries=3)
def sync_1c_task(self):
    """
    Ежедневная синхронизация с 1С. Запускается в 07:00 по Бишкеку.
 
    Диапазон берётся из настроек (ONEC_SYNC_DAYS_BACK/FORWARD),
    менять можно через .env без правки кода.
    """
    try:
        stats = sync_full()
        logger.info("Синхронизация с 1С: %s", stats)
        return str(stats)
    except OneCError as e:
        logger.error("Синхронизация с 1С не удалась: %s", e)
        # 1С могла быть недоступна — пробуем ещё через 10 минут
        raise self.retry(exc=e, countdown=600)
 
 
@shared_task
def sync_1c_client_task(customer_guid=None, customer_name=None):
    """Точечная синхронизация одного клиента — для кнопки в админке."""
    try:
        stats = import_from_1c(
            customer_guid=customer_guid,
            customer_name=customer_name,
        )
        return str(stats)
    except OneCError as e:
        return f"error: {e}"

def _get_user_and_token(client_obj):
    """client_obj — Client (через car_client.client или напрямую)."""
    user = User.objects.filter(client=client_obj).first()
    token = getattr(user, "expo_push_token", None)
    return user, token


def _notify(user, token, title, message):
    if not token:
        return False
    send_push_message(token, title, message)
    Notification.objects.create(user=user, message=message)
    return True


@shared_task
def send_notification_task():
    today = date.today()
    _process_repayments(today)
    _process_insurance_upcoming(today)
    _process_insurance_expired(today)
    return "Notification task completed successfully."


def _process_repayments(today):
    # только неоплаченные, и только те, кому вообще может понадобиться напоминание в ближайшее время
    candidates = RepaymentSchedule.objects.filter(
        ~Q(is_paid="is_paid"),
        paid_date__gte=today - timedelta(days=max(PAYMENT_REMINDER_DAYS_AFTER)),
        paid_date__lte=today + timedelta(days=max(PAYMENT_REMINDER_DAYS_BEFORE)),
    ).select_related("car_client", "car_client__client")

    for r in candidates:
        if not r.paid_date:
            continue

        # уже напоминали сегодня — пропускаем, защита от повторного запуска задачи
        if r.last_reminder_sent == today:
            continue

        days_to = (r.paid_date - today).days       # положительное — платёж впереди
        days_overdue = (today - r.paid_date).days  # положительное — просрочен

        car_model = r.car_client.car_model
        total_payment = r.total_payment or 0
        user, token = _get_user_and_token(r.car_client.client)
        if not token:
            continue

        sent = False

        if days_to >= 0 and days_to in PAYMENT_REMINDER_DAYS_BEFORE:
            if days_to == 0:
                title = "Платёж сегодня"
                message = f"Сегодня срок платежа по машине {car_model} на сумму {total_payment} сом."
            else:
                title = "Напоминание о платеже"
                message = (f"Через {days_to} дн. платёж по машине {car_model}, "
                            f"сумма: {total_payment} сом. Не забудьте оплатить.")
            sent = _notify(user, token, title, message)

        elif days_overdue > 0 and days_overdue in PAYMENT_REMINDER_DAYS_AFTER:
            title = "Просрочка платежа"
            message = (f"Платёж по машине {car_model} просрочен на {days_overdue} дн. "
                        f"Сумма: {total_payment} сом.")
            sent = _notify(user, token, title, message)

        if sent:
            r.last_reminder_sent = today
            r.save(update_fields=["last_reminder_sent"])


def _process_insurance_upcoming(today):
    """
    Напоминания о скором окончании полиса.
    Берём ТОЛЬКО выпущенные полисы — черновики и неоплаченные заявки
    не должны порождать уведомления.
    """
    candidates = OsagoApplication.objects.filter(
        status=OsagoApplication.STATUS_CONFIRMED,
        period_do__gte=today,
        period_do__lte=today + timedelta(days=max(INSURANCE_REMINDER_DAYS_BEFORE)),
    ).exclude(
        policy_status__in=['CANCELED', 'EXPIRED']
    ).select_related('client', 'client_car')
 
    for policy in candidates:
        if policy.last_reminder_sent == today:
            continue
 
        days_to_expire = (policy.period_do - today).days
        if days_to_expire not in INSURANCE_REMINDER_DAYS_BEFORE:
            continue
 
        user, token = _get_user_and_token(policy.client)
        if not token:
            continue
 
        title = "Страховка скоро закончится"
        message = (
            f"Полис ОСАГО по машине {policy.client_car.car_model} "
            f"истекает через {days_to_expire} дн."
        )
 
        if _notify(user, token, title, message):
            policy.last_reminder_sent = today
            policy.save(update_fields=['last_reminder_sent'])
 

def _process_insurance_expired(today):
    """Напоминания о просроченном полисе."""
    candidates = OsagoApplication.objects.filter(
        status=OsagoApplication.STATUS_CONFIRMED,
        period_do__lt=today,
        period_do__gte=today - timedelta(days=max(INSURANCE_REMINDER_DAYS_AFTER)),
    ).select_related('client', 'client_car')
 
    for policy in candidates:
        if policy.last_reminder_sent == today:
            continue
 
        days_expired = (today - policy.period_do).days
        if days_expired not in INSURANCE_REMINDER_DAYS_AFTER:
            continue
 
        user, token = _get_user_and_token(policy.client)
        if not token:
            continue
 
        title = "Страховка просрочена"
        message = (
            f"Полис ОСАГО по машине {policy.client_car.car_model} "
            f"просрочен на {days_expired} дн. Пожалуйста, оформите новый."
        )
 
        if _notify(user, token, title, message):
            policy.last_reminder_sent = today
            policy.save(update_fields=['last_reminder_sent'])
 
 
def _get_user_and_token(client):
    """client — объект Client (раньше приходилось идти через ins.client.client)."""
    from accounts.models import User
    user = User.objects.filter(client=client).first()
    return user, getattr(user, 'expo_push_token', None)

@shared_task
def daily_payments_summary_task():
    """Итог за день бухгалтеру. Запускается в 18:00 по Бишкеку."""
    notify_daily_summary()
    return "ok"