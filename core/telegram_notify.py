# core/telegram_notify.py
# Уведомления бухгалтеру об оплатах через приложение.

import logging

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _send(text: str) -> bool:
    """
    Отправка сообщения бухгалтеру.

    Никогда не бросает исключение: если телеграм недоступен, оплата
    всё равно должна пройти. Неудачи пишем в лог.
    """
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(settings, "TELEGRAM_ACCOUNTANT_CHAT_ID", "")

    if not token or not chat_id:
        logger.warning("Telegram: не настроены TELEGRAM_BOT_TOKEN / TELEGRAM_ACCOUNTANT_CHAT_ID")
        return False

    try:
        response = requests.post(
            TELEGRAM_API.format(token=token),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        # Сообщение не дошло — оплата при этом уже прошла.
        # Данные есть в базе, их видно в админке.
        logger.error("Telegram: сообщение не отправлено: %s\nТекст:\n%s", e, text)
        return False


def _fmt_money(value) -> str:
    """21175 → '21 175', 3015.94 → '3 015,94'"""
    if value is None:
        return "0"
    amount = float(value)
    if amount == int(amount):
        return f"{int(amount):,}".replace(",", " ")
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",")


def _fmt_dt(value) -> str:
    """Дата и время в местном поясе: '06.08.2026, 21:30'"""
    if not value:
        return ""
    return timezone.localtime(value).strftime("%d.%m.%Y, %H:%M")


def notify_payment_success(payment) -> bool:
    """
    Уведомление о прошедшей оплате.
    Вызывается из вебхука BePay, когда статус стал Success.
    """
    from payments.models import Payment

    client = payment.client
    car = None

    if payment.purpose == Payment.PURPOSE_REPAYMENT and payment.repayment_schedule:
        car = payment.repayment_schedule.car_client
        header = "✅ <b>Оплата получена</b>"
    elif payment.purpose == Payment.PURPOSE_OSAGO and payment.osago_application:
        car = payment.osago_application.client_car
        header = "🛡 <b>Оплачен полис ОСАГО</b>"
    else:
        header = "✅ <b>Оплата получена</b>"

    fio = client.fio if client else "—"
    car_line = "—"
    if car:
        parts = [p for p in (car.car_model, car.car_number) if p]
        car_line = " · ".join(parts) if parts else "—"

    # amount хранится в тыйынах
    amount_som = payment.amount / 100

    text = (
        f"{header}\n\n"
        f"{fio}\n"
        f"{car_line}\n"
        f"{_fmt_money(amount_som)} сом\n\n"
        f"{_fmt_dt(payment.executed_at or timezone.now())}"
    )

    return _send(text)


def notify_daily_summary(day=None) -> bool:
    """
    Итог за день. Отправляется в 18:00.

    Нужен, чтобы заметить потерянные уведомления: если бухгалтер
    видела 5 сообщений, а в итоге 7 — два не дошли, надо смотреть админку.
    """
    from payments.models import Payment

    day = day or timezone.localdate()

    payments = Payment.objects.filter(
        status=Payment.STATUS_SUCCESS,
        executed_at__date=day,
    )

    count = payments.count()
    total_tyiyn = sum(p.amount for p in payments)
    total_som = total_tyiyn / 100

    if count == 0:
        text = (
            f"📊 <b>Итог за {day.strftime('%d.%m.%Y')}</b>\n\n"
            f"Оплат через приложение не было"
        )
        return _send(text)

    repayment = payments.filter(purpose=Payment.PURPOSE_REPAYMENT)
    osago = payments.filter(purpose=Payment.PURPOSE_OSAGO)

    lines = [
        f"📊 <b>Итог за {day.strftime('%d.%m.%Y')}</b>",
        "",
        f"{count} {_plural(count)} на {_fmt_money(total_som)} сом",
    ]

    # разбивку показываем только если есть оба типа
    if repayment.exists() and osago.exists():
        r_sum = sum(p.amount for p in repayment) / 100
        o_sum = sum(p.amount for p in osago) / 100
        lines += [
            "",
            f"график: {repayment.count()} · {_fmt_money(r_sum)} сом",
            f"ОСАГО: {osago.count()} · {_fmt_money(o_sum)} сом",
        ]

    return _send("\n".join(lines))


def _plural(n: int) -> str:
    """7 оплат / 1 оплата / 2 оплаты"""
    if n % 10 == 1 and n % 100 != 11:
        return "оплата"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "оплаты"
    return "оплат"