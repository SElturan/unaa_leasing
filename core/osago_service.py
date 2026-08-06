import logging

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


# =========================================================
# ОШИБКИ
# =========================================================

class OsagoError(Exception):
    """Ошибка при работе с API Сакбола."""

    ERROR_MESSAGES = {
        "1": "Неправильный ключ API",
        "2": "Поля заполнены не полностью либо некорректно",
    }

    def __init__(self, code=None, detail=None):
        self.code = str(code) if code is not None else None
        self.detail = detail or self.ERROR_MESSAGES.get(self.code, "Неизвестная ошибка страховой")
        super().__init__(f"OSAGO error {self.code}: {self.detail}")


# =========================================================
# HTTP-КЛИЕНТ
# =========================================================

class OsagoClient:
    """
    Три метода из документации Сакбола:
        create_policy  → POST /create_osago   создать заявку, узнать цену
        confirm_policy → POST /confirm_osago  выпустить полис (списание денег)
        get_status     → POST /status_osago   проверить статус

    Плюс справочники для формы.

    Настройки в .env:
        OSAGO_BASE_URL=https://.../api
        OSAGO_API_KEY=...
        OSAGO_TIMEOUT=60
    """

    def __init__(self, timeout=None):
        self.base_url = settings.OSAGO_BASE_URL.rstrip("/")
        self.timeout = timeout or settings.OSAGO_TIMEOUT
        self.headers = {
            "Authorization": f"Bearer {settings.OSAGO_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}/{path.lstrip('/')}"

        try:
            response = requests.request(
                method, url, headers=self.headers, timeout=self.timeout, **kwargs
            )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout:
            raise OsagoError(detail=f"Страховая не ответила за {self.timeout} сек")
        except requests.RequestException as e:
            raise OsagoError(detail=f"Ошибка запроса к страховой: {e}")
        except ValueError:
            raise OsagoError(detail=f"Страховая вернула не-JSON: {response.text[:300]}")

        # Сакбол отдаёт ошибку в теле ответа, а не HTTP-статусом
        if isinstance(data, dict) and "error" in data:
            raise OsagoError(code=data["error"])

        return data

    def create_policy(self, payload: dict) -> dict:
        """
        Шаг 1. Создание заявки. Деньги НЕ списываются, полиса ещё нет.
        Ответ: {"guid", "summa_insurance", "premiya_insurance"}
        """
        logger.info("ОСАГО → create_osago, авто %s", payload.get("car_license_number"))
        return self._request("POST", "/create_osago", json=payload)

    def confirm_policy(self, guid: str) -> dict:
        """
        Шаг 3. Выпуск полиса. ЗДЕСЬ СПИСЫВАЮТСЯ ДЕНЬГИ с баланса компании.
        Вызывать только после того, как клиент оплатил.

        Идемпотентен: повторный вызов не списывает повторно и возвращает
        тот же результат.

        Ответ: {"success": "true", "pdf": "url", "polis": "серия и номер"}
        """
        logger.info("ОСАГО → confirm_osago guid=%s", guid)
        return self._request("POST", "/confirm_osago", json={"guid": str(guid)})

    def get_status(self, guid: str) -> dict:
        """
        Статус полиса.
        Ответ: {"status", "polis", "summa_insurance", "premiya_insurance", "pdf"}
        Статусы: ACTIVE, CANCELED, EXPIRED, NOT_ACTIVE
        """
        return self._request("POST", "/status_osago", json={"guid": str(guid)})

    def get_reference(self, name: str) -> list:
        """
        Справочники для выпадающих полей формы.
        name: country | insurance_territory | transport_type | car_of_use | type_document
        Ответ: [{"codeid": 1, "nameid": "..."}, ...]
        Кэш на сутки.
        """
        cache_key = f"osago_ref_{name}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        data = self._request("GET", f"/osago/get_code_sp_{name}")
        cache.set(cache_key, data, 60 * 60 * 24)
        return data


# =========================================================
# ПОДТВЕРЖДЕНИЕ ПОЛИСА
# =========================================================

def confirm_and_save(application) -> bool:
    """
    Вызывает confirm_osago и сохраняет результат в заявку.

    Вызывается из двух мест:
      1. вебхук BePay — сразу после подтверждения оплаты
      2. OsagoStatusView — повторная попытка, если первая не прошла

    Идемпотентна: если полис уже выпущен, ничего не делает.
    Возвращает True, если полис выпущен.
    """
    from .models import OsagoApplication

    if application.status == OsagoApplication.STATUS_CONFIRMED:
        return True

    if not application.external_guid:
        application.status = OsagoApplication.STATUS_FAILED
        application.last_error = "Нет guid — заявка не создавалась в страховой"
        application.save(update_fields=["status", "last_error"])
        return False

    try:
        result = OsagoClient().confirm_policy(application.external_guid)
    except OsagoError as e:
        # Страховая недоступна. Статус остаётся paid — попробуем позже.
        application.status = OsagoApplication.STATUS_PAID
        application.last_error = str(e)
        application.save(update_fields=["status", "last_error"])
        logger.error(
            "ОСАГО: confirm не прошёл. Заявка %s, клиент %s, сумма %s. Ошибка: %s",
            application.id, application.client.fio, application.premiya_insurance, e,
        )
        return False

    application.polis_number = result.get("polis", "")
    application.pdf_url = result.get("pdf", "")
    application.status = OsagoApplication.STATUS_CONFIRMED
    application.confirmed_at = timezone.now()
    application.last_error = ""
    application.save()

    logger.info("ОСАГО: полис %s выпущен (заявка %s)",
                application.polis_number, application.id)
    return True


# =========================================================
# СБОРКА PAYLOAD ДЛЯ create_osago
# =========================================================
# Правила Сакбола: null передавать нельзя, только пустую строку.
# Даты строго YYYY-MM-DD.

def _s(value) -> str:
    """Любое значение → строка. None и 'none' → пустая строка."""
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("none", "null") else text


def _d(value) -> str:
    """Дата → 'YYYY-MM-DD' или пустая строка."""
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return _s(value)


def build_create_payload(client, car, form: dict) -> dict:
    """
    Собирает тело запроса create_osago.

    client, car — модели Client и ClientCar (данные из 1С)
    form        — данные, которые ввёл пользователь в приложении

    Приоритет: если поле есть в форме — берём оттуда, иначе из нашей базы.
    """
    return {
        # --- страхователь ---
        "code_sp_type_client": _s(form.get("code_sp_type_client", 1)),
        "inn": _s(form.get("inn")),
        "nameid": _s(form.get("nameid") or client.fio),
        "date_birth": _d(form.get("date_birth")),
        "gender": _s(form.get("gender")),
        "passport_series": _s(form.get("passport_series")),
        "passport_number": _s(form.get("passport_number")),
        "passport_issue": _s(form.get("passport_issue")),
        "passport_date_issue": _d(form.get("passport_date_issue")),
        "address_code_country": _s(form.get("address_code_country")),
        "address_region": _s(form.get("address_region")),
        "address_area": _s(form.get("address_area")),
        "address_locality": _s(form.get("address_locality")),
        "address_street_house_flat": _s(
            form.get("address_street_house_flat") or client.residence
        ),
        "phone": _s(form.get("phone") or client.phone),

        # --- собственник ТС (по умолчанию = страхователь) ---
        "car_owner_policyholder_is_owner": _s(form.get("car_owner_policyholder_is_owner", 1)),
        "car_owner_inn": _s(form.get("car_owner_inn") or form.get("inn")),
        "car_owner_nameid": _s(form.get("car_owner_nameid") or client.fio),
        "car_owner_date_birth": _d(form.get("car_owner_date_birth") or form.get("date_birth")),
        "car_owner_gender": _s(form.get("car_owner_gender") or form.get("gender")),
        "car_owner_passport_series": _s(
            form.get("car_owner_passport_series") or form.get("passport_series")
        ),
        "car_owner_passport_number": _s(
            form.get("car_owner_passport_number") or form.get("passport_number")
        ),
        "car_owner_passport_issue": _s(
            form.get("car_owner_passport_issue") or form.get("passport_issue")
        ),
        "car_owner_passport_date_issue": _d(
            form.get("car_owner_passport_date_issue") or form.get("passport_date_issue")
        ),
        "car_owner_address_code_country": _s(
            form.get("car_owner_address_code_country") or form.get("address_code_country")
        ),
        "car_owner_address_region": _s(
            form.get("car_owner_address_region") or form.get("address_region")
        ),
        "car_owner_address_area": _s(
            form.get("car_owner_address_area") or form.get("address_area")
        ),
        "car_owner_address_locality": _s(
            form.get("car_owner_address_locality") or form.get("address_locality")
        ),
        "car_owner_address_street_house_flat": _s(
            form.get("car_owner_address_street_house_flat")
            or form.get("address_street_house_flat")
            or client.residence
        ),
        "car_owner_phone": _s(form.get("car_owner_phone") or client.phone),

        # --- период и территория страхования ---
        "period_ot": _d(form.get("period_ot")),
        "period_do": _d(form.get("period_do")),
        "code_sp_insurance_territory": _s(form.get("code_sp_insurance_territory")),

        # --- предыдущий полис ---
        "old_isset_polis": _s(form.get("old_isset_polis", 0)),
        "old_insurer": _s(form.get("old_insurer")),
        "old_prefix_polis": _s(form.get("old_prefix_polis")),
        "old_number_polis": _s(form.get("old_number_polis")),

        # --- доверенность ---
        "car_owner_isset_procuration": _s(form.get("car_owner_isset_procuration", 0)),
        "car_owner_procuration_series": _s(form.get("car_owner_procuration_series")),
        "car_owner_procuration_number": _s(form.get("car_owner_procuration_number")),
        "car_owner_procuration_date_issue": _d(form.get("car_owner_procuration_date_issue")),

        # --- транспортное средство ---
        "car_is_register_kr": _s(form.get("car_is_register_kr", 1)),
        "car_code_transport_type": _s(form.get("car_code_transport_type")),
        "car_sp_marka": _s(form.get("car_sp_marka") or car.car_model),
        "car_sp_model": _s(form.get("car_sp_model") or car.car_model),
        "car_engine_displacement": _s(form.get("car_engine_displacement")),
        "car_electro_car": _s(form.get("car_electro_car", 0)),
        "car_engine_power": _s(form.get("car_engine_power")),
        "car_code_steering_position": _s(form.get("car_code_steering_position")),
        "car_max_weight": _s(form.get("car_max_weight")),
        "car_count_passengers": _s(form.get("car_count_passengers")),
        "car_weight": _s(form.get("car_weight")),
        "car_is_trailer": _s(form.get("car_is_trailer", 0)),
        "car_code_car_of_use": _s(form.get("car_code_car_of_use")),
        "car_code_type_document": _s(form.get("car_code_type_document")),
        "car_year_issue": _s(form.get("car_year_issue") or car.car_year),
        "car_vin": _s(form.get("car_vin") or car.car_vin),
        "car_chassis": _s(form.get("car_chassis")),
        "car_body": _s(form.get("car_body")),
        "car_series_number_document": _s(form.get("car_series_number_document")),
        "car_issuing_authority": _s(form.get("car_issuing_authority")),
        "car_document_issue_date": _d(form.get("car_document_issue_date")),
        "car_license_number": _s(form.get("car_license_number") or car.car_number),

        # --- техосмотр ---
        "car_tech_inspection": _s(form.get("car_tech_inspection", 0)),
        # В документации у этого ключа пробел на конце. Отправляем как в доке.
        "car_series_tech_inspection ": _s(form.get("car_series_tech_inspection")),
        "car_number_tech_inspection": _s(form.get("car_number_tech_inspection")),
        "car_date_tech_inspection": _d(form.get("car_date_tech_inspection")),
        "car_expired_date_tech_inspection": _d(form.get("car_expired_date_tech_inspection")),

        # --- водители ---
        "car_unlimited_driwers": _s(form.get("car_unlimited_driwers", 0)),
        "driwers": [
            {
                "nameid": _s(d.get("nameid")),
                "inn": _s(d.get("inn")),
                "date_birth": _d(d.get("date_birth")),
                "driver_license": _s(d.get("driver_license")),
                "date_issue_license": _d(d.get("date_issue_license")),
            }
            for d in (form.get("driwers") or [])
        ],
    }