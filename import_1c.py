import requests
from django.utils.dateparse import parse_date
from django.utils.dateparse import parse_datetime
from core.models import Client, ClientCar, RepaymentSchedule

ONEC_API_URL = "http://213.109.69.182:11778/service/hs/rep/unaa_report"
USERNAME = "ReportService"
PASSWORD = "vLFuwAFk"

def import_clients_from_1c():
    headers = {"Content-Type": "application/json"}
    payload = {
        "beginDate": "20200101",
        "endDate": "20251104",
        "customerGuid": None,
        "customerName": None
    }

    response = requests.post(ONEC_API_URL, json=payload, headers=headers, auth=(USERNAME, PASSWORD))
    response.raise_for_status()
    result = response.json()
    clients_data = result.get("data", [])

    for item in clients_data:
        client, _ = Client.objects.update_or_create(
            fio=item.get("fio"),
            phone=item.get("phone"),
            defaults={
                "email": item.get("email"),
                "residence": item.get("residentialAddress"),
                "registration_address": item.get("registrationAddress"),
            }
        )

        for car_item in item.get("cars", []):
            try:
                car_year = int(car_item.get("car_year"))
            except (TypeError, ValueError):
                car_year = 0  # или None, если разрешено в модели

            client_car, _ = ClientCar.objects.update_or_create(
                loan_guid=car_item.get("loan_guid"),
                defaults={
                    "client": client,
                    "deal_number": car_item.get("deal_number"),
                    "car_name": car_item.get("car_name"),
                    "car_model": car_item.get("car_model"),
                    "car_year": car_year,
                    "car_color": car_item.get("car_color"),
                    "car_vin": car_item.get("car_vin"),
                    "car_number": car_item.get("car_number"),
                    "total_amount": car_item.get("total_amount"),
                    "paid_amount": car_item.get("paid_amount"),
                    "remaining_amount": car_item.get("principal_balance"),
                    "advance_payment_amount": car_item.get("advance_payment_amount"),
                    "disbursement_date": parse_date(car_item.get("disbursement_date")) if car_item.get("disbursement_date") else None,
                    "last_payment_date": parse_date(car_item.get("last_payment_date")) if car_item.get("last_payment_date") else None,
                    "term": car_item.get("term"),
                    "due_days_principal": car_item.get("due_days_principal"),
                    "due_days_interest": car_item.get("due_days_interest"),
                    "due_amount_principal": car_item.get("due_amount_principal"),
                    "due_amount_interest": car_item.get("due_amount_interest"),
                    "principal_balance": car_item.get("principal_balance"),
                    "interest_balance": car_item.get("interest_balance"),
                    "и": car_item.get("penalty_balance"),
                }
            )

            for schedule_item in car_item.get("repayment_schedules", []):
                paid_date = parse_datetime(schedule_item.get("paid_date"))
                if paid_date is None:
                    continue  # пропускаем, если нет даты

                RepaymentSchedule.objects.create(
                    car_client=client_car,
                    paid_date=paid_date,
                    main_debt=schedule_item.get("main_debt"),
                    interest=schedule_item.get("interest"),
                    total_payment=schedule_item.get("total_amount"),
                    overdue_amount=schedule_item.get("overdue_amount"),
                    is_paid="is_paid" if schedule_item.get("is_paid") == "true" else "not_paid",
                )

    print(f"Импорт завершён: {len(clients_data)} клиентов обработано")
