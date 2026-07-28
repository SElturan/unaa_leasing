from celery import shared_task
from django.db.models import Q
from django.utils import timezone
from datetime import date, timedelta

from .models import RepaymentSchedule, InsuranceClient, Notification
from .expo_push import send_push_message
from accounts.models import User
from core.fetch_1c_data import import_clients_from_1c

# Точки напоминания. Отрицательные — "за N дней до", положительные — "через N дней после".
PAYMENT_REMINDER_DAYS_BEFORE = [3, 1, 0]        # за 3 дня, за 1 день, в день платежа
PAYMENT_REMINDER_DAYS_AFTER = [1, 3, 7, 14, 30]  # потом раз в 2 недели, дальше — тишина

INSURANCE_REMINDER_DAYS_BEFORE = [30, 14, 7, 3, 1]
INSURANCE_REMINDER_DAYS_AFTER = [1, 7, 30]


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
    candidates = InsuranceClient.objects.filter(
        end_date__gte=today,
        end_date__lte=today + timedelta(days=max(INSURANCE_REMINDER_DAYS_BEFORE)),
    ).select_related("client", "client__client")

    for ins in candidates:
        if ins.last_reminder_sent == today:
            continue

        days_to_expire = (ins.end_date - today).days
        if days_to_expire not in INSURANCE_REMINDER_DAYS_BEFORE:
            continue

        user, token = _get_user_and_token(ins.client.client)
        if not token:
            continue

        title = "Страховка скоро закончится"
        message = (f"Страховка {ins.get_insurance_company_display()} по машине "
                    f"{ins.client.car_model} истекает через {days_to_expire} дн.")

        if _notify(user, token, title, message):
            ins.last_reminder_sent = today
            ins.save(update_fields=["last_reminder_sent"])


def _process_insurance_expired(today):
    candidates = InsuranceClient.objects.filter(
        end_date__lt=today,
        end_date__gte=today - timedelta(days=max(INSURANCE_REMINDER_DAYS_AFTER)),
    ).select_related("client", "client__client")

    for ins in candidates:
        if ins.last_reminder_sent == today:
            continue

        days_expired = (today - ins.end_date).days
        if days_expired not in INSURANCE_REMINDER_DAYS_AFTER:
            continue

        user, token = _get_user_and_token(ins.client.client)
        if not token:
            continue

        title = "Страховка просрочена"
        message = (f"Страховка {ins.get_insurance_company_display()} по машине "
                    f"{ins.client.car_model} просрочена на {days_expired} дн. "
                    f"Пожалуйста, обновите полис.")

        if _notify(user, token, title, message):
            ins.last_reminder_sent = today
            ins.save(update_fields=["last_reminder_sent"])


@shared_task
def import_clients_daily():
    import_clients_from_1c()
    return "Импорт из 1С завершён"