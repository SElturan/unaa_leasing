from celery import shared_task
# from .fetch_1c_data import fetch_new_clients_from_1c
from .models import RepaymentSchedule, InsuranceClient, Notification
from datetime import date, timedelta
from .expo_push import send_push_message
from django.db.models import Q
from accounts.models import User

# @shared_task
# def fetch_clients_task():
#     fetch_new_clients_from_1c()
#     return "Fetch clients task completed successfully."

@shared_task
def send_notification_task():
    today = date.today()
    print('-123123')

    # --- ПЛАТЕЖИ ---
    soon_range = [today, today + timedelta(days=3)]
    overdue_cutoff = today - timedelta(days=3)

    repayments = RepaymentSchedule.objects.filter(
        Q(is_paid=False) & (
            Q(paid_date__range=soon_range) |
            Q(paid_date__lt=overdue_cutoff)
        )
    )

    for r in repayments:
        if not r.paid_date:
            continue

        days_to = (r.paid_date - today).days
        days_overdue = (today - r.paid_date).days
        user = User.objects.filter(client=r.car_client.client).first()
        token = getattr(user, 'expo_push_token', None)
        car_model = r.car_client.car_model
        total_payment = r.total_payment if r.total_payment else 0
        message_repayment =f"""Напоминание о платеже",
                Платёж по машине {car_model}, сумма: {total_payment} сом. Не забудьте оплатить во избежание просрочки.
                Осталось {days_to} дней."""
        message_repayment_overdue = f"""Просрочка по платёжке",
                f"Платёж по машине {car_model} просрочен на {days_overdue} дней. Сумма: {total_payment} сом."""

        if not token:
            continue

        if 0 <= days_to <= 3:
            send_push_message(
                token,
                'Напоминание о платеже',
                message_repayment,

            )
            Notification.objects.create(
                    user=user,
                    message=message_repayment,
                )


        elif days_overdue > 3 and days_overdue % 2 == 0:
            send_push_message(
                token,
                'Уведомление о просрочке платежа',
                message_repayment_overdue,
            )
            Notification.objects.create(
                    user=user,
                    message=message_repayment_overdue,
                )
    
    insurance_range = [today, today + timedelta(days=30)]
    insurances = InsuranceClient.objects.filter(end_date__range=insurance_range)

    for ins in insurances:
        days_to_expire = (ins.end_date - today).days
        print(days_to_expire, '-----')
        user = User.objects.filter(client=ins.client.client).first()
        token = getattr(user, 'expo_push_token', None)
        message_insurance = f"""Страховка скоро закончится",
                Страховка по машине {ins.client.car_model} ({ins.insurance_company}) истекает через {days_to_expire} дней."""
        message_insurance_overdue = f"""Страховка просрочена",
                Страховка по машине {ins.client.car_model} ({ins.insurance_company}) просрочена на {days_to_expire} дней. 
                "Пожалуйста, обновите полис."""
        
        if not token:
            continue

 
        send_push_message(
            token,
            'Уведомление о страховке',
            message_insurance,)
        Notification.objects.create(
                user=user,
                message=message_insurance,
            )

    expired_insurances = InsuranceClient.objects.filter(end_date__lt=today)
    for ins in expired_insurances:
        days_expired = (today - ins.end_date).days
        token = getattr(ins.client.client, 'expo_token', None)
        if not token:
            continue


        send_push_message(
            token,
            'Уведомление о просрочке страховки',
            message_insurance_overdue,
        )
        Notification.objects.create(
                user=ins.client.client.user,
                message=message_insurance_overdue,
            )   

    return "Notification task completed successfully."