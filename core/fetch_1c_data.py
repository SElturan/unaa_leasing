import requests
from requests.auth import HTTPBasicAuth

def fetch_from_1c(customer_guid=None, customer_name=None, begin_date=None, end_date=None):
    url = "http://213.109.69.182:11778/service/hs/rep/unaa_report/"
    auth = HTTPBasicAuth("ReportService", "vLFuwAFk")

    payload = {
        "customerGuid": customer_guid or "null",
        "customerName": customer_name or "null",
        "beginDate": begin_date or "null",
        "endDate": end_date or "null"
    }

    response = requests.post(url, json=payload, auth=auth)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Ошибка запроса в 1С: {response.text}")
