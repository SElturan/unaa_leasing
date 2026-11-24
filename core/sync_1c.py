# core/sync_1c.py

import logging
import re
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional
import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Client, ClientCar, RepaymentSchedule

logger = logging.getLogger(__name__)


# =========================================================
# НОРМАЛИЗАЦИЯ ТЕЛЕФОНОВ
# =========================================================

def normalize_phone(raw) -> str:
    """
    Приводит любой формат телефона к единому виду: 0XXXXXXXXX (10 цифр).

    Примеры:
        "0500534343"        → "0500534343"
        "996500534343"      → "0500534343"
        "+996 500 53 43 43" → "0500534343"
        "0500 53 43 43"     → "0500534343"
        "500534343"         → "0500534343"
        "0996500534343"     → "0500534343"   (кривой ввод, тоже чиним)
        "(0708) 55-11-54"   → "0708551154"

    Возвращает "" если номер не похож на кыргызстанский —
    такие записи логируем и не используем для поиска.
    """
    if not raw:
        return ""

    # оставляем только цифры
    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return ""

    # убираем ведущие нули: "0500..." → "500...", "0996500..." → "996500..."
    digits = digits.lstrip("0")

    # убираем код страны, если он есть
    if digits.startswith("996") and len(digits) > 9:
        digits = digits[3:]

    # у номера КР ровно 9 цифр: код оператора (3) + номер (6)
    if len(digits) != 9:
        logger.warning("Не удалось нормализовать телефон: %r → %r", raw, digits)
        return ""

    return "0" + digits


# =========================================================
# ПАРСЕРЫ (данные из 1С приходят "грязными")
# =========================================================

def to_decimal(value, default=None):
    if value in (None, "", "none", "null"):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def to_int(value, default=None):
    if value in (None, "", "none", "null"):
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def to_date(value):
    """Принимает '2021-01-27' и '2021-01-30T00:00:00'."""
    if not value or str(value).lower() in ("none", "null", ""):
        return None
    text = str(value).split("T")[0]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        logger.warning("Не удалось разобрать дату: %r", value)
        return None


def is_paid_from_1c(value) -> bool:
    """1С присылает is_paid строкой: "true" / "false"."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "да")


def is_empty(value) -> bool:
    return value is None or str(value).strip().lower() in ("", "none", "null")


# =========================================================
# HTTP-КЛИЕНТ К 1С
# =========================================================

class OneCError(Exception):
    pass


class OneCClient:
    """
    Обёртка над HTTP-сервисом 1С.

    Настройки в .env:
        ONEC_URL=http://213.109.69.182:11778/service/hs/rep/unaa_report
        ONEC_USER=ReportService
        ONEC_PASSWORD=...
    """

    def __init__(self, timeout=None):
        self.url = settings.ONEC_URL
        self.auth = (settings.ONEC_USER, settings.ONEC_PASSWORD)
        self.timeout = timeout or settings.ONEC_TIMEOUT

    def fetch(self, begin_date=None, end_date=None, customer_guid=None, customer_name=None) -> list:
        payload = {
            "beginDate": self._fmt(begin_date),
            "endDate": self._fmt(end_date),
            "customerGuid": str(customer_guid) if customer_guid else "null",
            "customerName": customer_name or "null",
        }

        logger.info("1C → запрос: %s", payload)
        started = timezone.now()

        try:
            response = requests.post(
                self.url, json=payload, auth=self.auth, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout:
            raise OneCError(f"1С не ответила за {self.timeout} сек")
        except requests.RequestException as e:
            raise OneCError(f"Ошибка запроса к 1С: {e}")
        except ValueError:
            raise OneCError(f"1С вернула не-JSON: {response.text[:300]}")

        records = data.get("data", []) or []
        elapsed = (timezone.now() - started).total_seconds()
        logger.info("1C ← получено записей: %s (за %.1f сек)", len(records), elapsed)

        return records

    @staticmethod
    def _fmt(value) -> str:
        """1С ждёт формат YYYYMMDD."""
        if not value:
            return ""
        if isinstance(value, str):
            return value
        return value.strftime("%Y%m%d")


# =========================================================
# СТАТИСТИКА ИМПОРТА
# =========================================================

class ImportStats:
    def __init__(self):
        self.clients_created = 0
        self.clients_updated = 0
        self.cars_created = 0
        self.cars_updated = 0
        self.schedules_created = 0
        self.schedules_updated = 0
        self.paid_synced = 0        # 1С подтвердила оплату, у нас было "не оплачено"
        self.paid_kept_local = 0    # у нас оплачено (BePay), в 1С ещё нет
        self.bad_phones = 0
        self.errors = 0

    def __str__(self):
        return (
            f"клиенты +{self.clients_created}/~{self.clients_updated} | "
            f"машины +{self.cars_created}/~{self.cars_updated} | "
            f"график +{self.schedules_created}/~{self.schedules_updated} | "
            f"оплат подтверждено из 1С: {self.paid_synced} | "
            f"оплат сохранено локально: {self.paid_kept_local} | "
            f"кривых телефонов: {self.bad_phones} | ошибок: {self.errors}"
        )


# =========================================================
# ГЛАВНАЯ ТОЧКА ВХОДА
# =========================================================

def import_from_1c(begin_date=None, end_date=None, customer_guid=None, customer_name=None,
                   timeout=None) -> ImportStats:
    """
    Тянет данные из 1С и раскладывает по базе.

    Идемпотентна: повторный запуск с теми же данными не создаёт дубликатов.
    Каждый клиент импортируется в своей транзакции — битые данные одного
    клиента не ломают весь импорт.
    """
    stats = ImportStats()
    records = OneCClient(timeout=timeout).fetch(begin_date, end_date, customer_guid, customer_name)

    for record in records:
        try:
            with transaction.atomic():
                _import_client(record, stats)
        except Exception:
            stats.errors += 1
            logger.exception("1C: ошибка импорта клиента %r", record.get("fio"))

    logger.info("1C импорт завершён: %s", stats)
    return stats


def _import_client(record: dict, stats: ImportStats):
    fio = (record.get("fio") or "").strip()
    phone_raw = record.get("phone", "")
    phone = normalize_phone(phone_raw)

    if not phone:
        stats.bad_phones += 1
        logger.warning("1C: клиент %r с некорректным телефоном %r", fio, phone_raw)

    if not phone and not fio:
        return  # совсем пустая запись

    cars_data = record.get("cars") or []

    # GUID клиента лежит внутри машины (car["client"])
    client_guid = None
    for car in cars_data:
        if not is_empty(car.get("client")):
            client_guid = car["client"]
            break

    client = _upsert_client(record, fio, phone, client_guid, stats)

    for car_data in cars_data:
        _upsert_car(client, car_data, stats)


def _upsert_client(record, fio, phone, client_guid, stats) -> Client:
    """
    Ищем клиента по приоритету:
      1. GUID из 1С — самый надёжный
      2. нормализованный телефон
      3. ФИО (последний шанс, может дать ложное совпадение у однофамильцев)
    """
    client = None

    if client_guid:
        client = Client.objects.filter(client_guid=client_guid).first()
    if not client and phone:
        client = Client.objects.filter(phone=phone).first()
    if not client and fio:
        client = Client.objects.filter(fio__iexact=fio).first()

    fields = {
        "fio": fio,
        "residence": record.get("residentialAddress") or "",
        "registration_address": record.get("registrationAddress") or "",
        "email": record.get("email") or "",
        "synced_at": timezone.now(),
    }
    if phone:
        fields["phone"] = phone            # пишем ТОЛЬКО нормализованный
    if client_guid:
        fields["client_guid"] = client_guid

    if client:
        for key, value in fields.items():
            setattr(client, key, value)
        client.save()
        stats.clients_updated += 1
    else:
        client = Client.objects.create(**fields)
        stats.clients_created += 1

    return client


def _upsert_car(client: Client, data: dict, stats: ImportStats):
    loan_guid = data.get("loan_guid")
    if is_empty(loan_guid):
        logger.warning("1C: машина без loan_guid у клиента %s — пропуск", client.fio)
        return

    total_amount = to_decimal(data.get("total_amount"), Decimal("0"))
    paid_amount = to_decimal(data.get("paid_amount"))

    fields = {
        "client": client,
        "client_guid": data.get("client") or None,
        "deal_number": data.get("deal_number") or "",
        "car_name": data.get("car_name") or "",
        "car_model": data.get("car_model") or "",
        "car_year": to_int(data.get("car_year")),
        "car_color": data.get("car_color") or "",
        "car_vin": data.get("car_vin") or "",
        "car_number": data.get("car_number") or "",
        "total_amount": total_amount,
        "paid_amount": paid_amount,
        "advance_payment_amount": to_decimal(data.get("advance_payment_amount")),
        "disbursement_date": to_date(data.get("disbursement_date")),
        "last_payment_date": to_date(data.get("last_payment_date")),
        "term": to_int(data.get("term")),
        "due_days_principal": to_int(data.get("due_days_principal")),
        "due_days_interest": to_int(data.get("due_days_interest")),
        "due_amount_principal": to_decimal(data.get("due_amount_principal")),
        "due_amount_interest": to_decimal(data.get("due_amount_interest")),
        "principal_balance": to_decimal(data.get("principal_balance")),
        "interest_balance": to_decimal(data.get("interest_balance")),
        "penalty_balance": to_decimal(data.get("penalty_balance")),
        "synced_at": timezone.now(),
    }

    # остаток к погашению 1С отдельным полем не отдаёт — считаем сами
    if total_amount is not None and paid_amount is not None:
        fields["remaining_amount"] = total_amount - paid_amount

    car, created = ClientCar.objects.update_or_create(
        loan_guid=loan_guid, defaults=fields
    )
    if created:
        stats.cars_created += 1
    else:
        stats.cars_updated += 1

    _upsert_schedules(car, data.get("repayment_schedules") or [], stats)

def _upsert_schedules(car: ClientCar, rows: list, stats: ImportStats):
    """
    Обновляем строки графика по ключу (машина + дата платежа).

    НИКОГДА не удаляем и не пересоздаём строки: у Payment есть FK
    на RepaymentSchedule, при удалении связь с оплатой через BePay
    потеряется навсегда.

    Правило статусов:
        оплачено в 1С ИЛИ оплачено у нас  →  оба поля 'is_paid'
        не оплачено нигде                 →  оба поля 'not_paid'
    """
    for row in rows:
        paid_date = to_date(row.get("paid_date"))
        if not paid_date:
            continue

        paid_in_1c = is_paid_from_1c(row.get("is_paid"))

        schedule = RepaymentSchedule.objects.filter(
            car_client=car, paid_date=paid_date
        ).first()

        if schedule is None:
            schedule = RepaymentSchedule(car_client=car, paid_date=paid_date)
            paid_locally = False
            stats.schedules_created += 1
        else:
            paid_locally = schedule.is_paid == "is_paid"
            stats.schedules_updated += 1

        # --- поля, которыми владеет 1С: перезаписываем всегда ---
        schedule.main_debt = to_decimal(row.get("main_debt"))
        schedule.interest = to_decimal(row.get("interest"))
        # ВНИМАНИЕ: в 1С "total_amount" внутри графика — это сумма платежа,
        # она ложится в наше total_payment (не путать с total_amount машины)
        schedule.total_payment = to_decimal(row.get("total_amount"), Decimal("0"))
        schedule.overdue_amount = to_decimal(row.get("overdue_amount"))
        schedule.total_amount = car.total_amount

        # --- статус оплаты: один true → оба true ---
        if paid_in_1c or paid_locally:
            schedule.is_paid = "is_paid"
            schedule.is_paid_1c = "is_paid"

            if paid_in_1c and not paid_locally:
                # заплатил наличными в офисе, 1С подтвердила
                stats.paid_synced += 1
            elif paid_locally and not paid_in_1c:
                # заплатил через BePay, бухгалтер ещё не провёл —
                # НЕ откатываем, держим оплаченным
                stats.paid_kept_local += 1
        else:
            # если по этому платежу прямо сейчас висит неоплаченный QR
            # (статус in_process) — не сбрасываем его в not_paid
            if schedule.is_paid != "in_process":
                schedule.is_paid = "not_paid"
            schedule.is_paid_1c = "not_paid"

        schedule.save()


# =========================================================
# ГОТОВЫЕ СЦЕНАРИИ
# =========================================================

def sync_full() -> ImportStats:
    """
    Ежедневная полная синхронизация.
    Период: с фиксированной даты (ONEC_SYNC_BEGIN_DATE) по сегодняшний день.
    """
    begin = datetime.strptime(settings.ONEC_SYNC_BEGIN_DATE, '%Y-%m-%d').date()
    end = date.today() + timedelta(days=1)

    return import_from_1c(begin_date=begin, end_date=end)
def find_client_in_1c(phone_raw: str, days: int = None) -> Optional[Client]:
    """
    Ищет клиента в 1С по телефону за последние N дней.
    Используется при регистрации, когда клиента ещё нет в нашей базе.
    """
    phone = normalize_phone(phone_raw)
    if not phone:
        return None

    days = days or settings.ONEC_REGISTRATION_DAYS
    today = date.today()

    import_from_1c(
        begin_date=today - timedelta(days=days),
        end_date=today + timedelta(days=days),
        # (подключение, чтение): в сумме должно быть меньше таймаута
        # воркера gunicorn (30 сек), иначе клиент получит 502
        timeout=(5, settings.ONEC_REGISTRATION_TIMEOUT),
    )

    return Client.objects.filter(phone=phone).first()