import requests
import json
from django.conf import settings


class BePayError(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class BePayClient:

    def __init__(self):
        self.base_url = settings.BEPAY_BASE_URL.rstrip("/")

        self.headers = {
            "Content-Type": "application/json",
            "Merchant-id": settings.BEPAY_MERCHANT_ID,
            "Merchant-secret-key": settings.BEPAY_SECRET_KEY,
        }


    def _request(self, method, path, **kwargs):

        url = f"{self.base_url}{path}"

        response = requests.request(
            method,
            url,
            headers=self.headers,
            timeout=15,
            **kwargs
        )


        print("====== BEPAY DEBUG ======")
        print("URL:", url)
        print("STATUS:", response.status_code)
        print("HEADERS:", self.headers)
        print("RESPONSE:", response.text)
        print("=========================")


        # если BePay вернул XML ошибку
        if response.text.startswith("<error>"):
            raise BePayError(
                response.status_code,
                response.text
            )


        try:
            data = response.json()
        except json.JSONDecodeError:
            raise BePayError(
                response.status_code,
                f"Invalid JSON response: {response.text}"
            )


        if response.status_code >= 400:
            detail = self._parse_error(response)
            raise BePayError(response.status_code, detail)

        return data

    @staticmethod
    def _parse_error(response) -> str:
        """
        В v2.2 ошибки приходят списком с указанием поля:
        {"detail": [{"type": "validation_error", "field": "amount",
                     "value": 0, "msg": "Parameter 'amount' must be greater than 0."}]}
        """
        try:
            detail = response.json().get("detail")
        except Exception:
            return response.text[:300]

        if isinstance(detail, list):
            parts = []
            for item in detail:
                if not isinstance(item, dict):
                    parts.append(str(item))
                    continue
                field = item.get("field", "")
                msg = item.get("msg", "")
                parts.append(f"{field}: {msg}" if field else msg)
            return "; ".join(p for p in parts if p)

        return str(detail) if detail else response.text[:300]

    def generate_qr(self, description, amount, expires_at=None, user_guid=None):
            payload = {
                "description": description,
                "amount": int(amount),
            }
            if user_guid:
                payload["user_guid"] = str(user_guid)

            if expires_at:
                if hasattr(expires_at, "strftime"):
                    from django.utils import timezone as dj_tz
                    # BePay игнорирует часовой пояс и читает время как местное (Бишкек),
                    # поэтому UTC отправлять нельзя — он посчитает срок истёкшим
                    local = dj_tz.localtime(expires_at)
                    payload["expires_at"] = local.strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    payload["expires_at"] = expires_at

            print("BEPAY REQUEST:", payload)
            return self._request("POST", "/qr/generate", json=payload)

    def get_status(self, qr_transaction_id):
        """Расширенный статус. В v2.2 путь изменился с /qr/check/status/ на /qr/status/{uuid}/details"""
        return self._request("GET", f"/qr/status/{qr_transaction_id}/details")
