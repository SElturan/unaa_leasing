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
            raise BePayError(
                response.status_code,
                data.get("detail", data)
            )


        return data



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
                    # переводим в местное время (Asia/Bishkek) перед отправкой
                    local = dj_tz.localtime(expires_at)
                    payload["expires_at"] = local.strftime("%Y-%m-%dT%H:%M:%S")
                else:
                    payload["expires_at"] = expires_at

            print("BEPAY REQUEST:", payload)
            return self._request("POST", "/qr/generate", json=payload)

    def get_status(self, qr_transaction_id):

        return self._request(
            "GET",
            f"/qr/check/status/{qr_transaction_id}"
        )



    def cancel_qr(self, qr_transaction_id):

        return self._request(
            "POST",
            f"/qr/1/tx/cancel/{qr_transaction_id}"
        )