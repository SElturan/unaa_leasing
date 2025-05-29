import requests
from datetime import datetime
from django.db import transaction
from requests.auth import HTTPBasicAuth
from core.models import Client, ClientCar, RepaymentSchedule
from django.db import IntegrityError
from decimal import Decimal
from datetime import datetime, timedelta


def fetch_new_clients_from_1c():
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    begin_date = yesterday.strftime('%Y%m%d')
    end_date = today.strftime('%Y%m%d')

    url = f"http://213.109.69.182:11778/service/hs/rep/unaa_report/{begin_date}/{end_date}"
    auth = HTTPBasicAuth('ReportService', 'vLFuwAFk')

    response = requests.get(url, auth=auth)
    if response.status_code != 200:
        print("Ошибка запроса:", response.text)
        return

    try:
        response_data = response.json()
    except Exception as e:
        print("Ошибка при парсинге JSON:", e)
        return

    for client_data in response_data.get("data", []):
        if not isinstance(client_data, dict):
            continue

        print("Обработка клиента:", client_data.get("fio", "Без имени"))

        try:
            # Создаем/обновляем клиента
            client, _ = Client.objects.update_or_create(
                fio=client_data.get('fio'),
                defaults={
                    'phone': client_data.get('phone'),
                    'email': client_data.get('email', ''),
                    'whatsapp': client_data.get('phone'),
                }
            )

            for car in client_data.get('cars', []):
                loan_guid = car.get('loan_guid')
                if not loan_guid:
                    continue

                try:
                    with transaction.atomic():
                        # Создаем/обновляем автомобиль
                        client_car, created = ClientCar.objects.update_or_create(
                            loan_guid=loan_guid,
                            defaults={
                                'client': client,
                                'client_guid': car.get('client'),
                                'car_name': car.get('car_name'),
                                'car_model': car.get('car_model'),
                                'car_year': int(car.get('car_year')) if car.get('car_year') else None,
                                'car_color': car.get('car_color'),
                                'car_vin': car.get('car_vin'),
                                'car_number': car.get('car_number'),
                                'total_amount': car.get('total_amount'),
                                'paid_amount': car.get('paid_amount'),
                                'remaining_amount': car.get('remaining_amount'),
                            }
                        )

                        # Создаем новые графики платежей
                        schedules_to_create = []
                        for schedule in car.get('repayment_schedules', []):
                            try:
                                paid_date_raw = schedule.get('paid_date')
                                paid_date = datetime.strptime(paid_date_raw.split('T')[0], '%Y-%m-%d').date() if paid_date_raw else None
                                
                                total_amount = Decimal(str(schedule.get('total_amount', 0)))
                                main_debt = Decimal(str(schedule.get('main_debt', 0)))
                                interest = Decimal(str(schedule.get('interest', 0)))
                                
                                if total_amount == 0:
                                    total_amount = main_debt + interest

                                # Обновить или создать запись
                                RepaymentSchedule.objects.update_or_create(
                                    car_client=client_car,
                                    paid_date=paid_date,
                                    defaults={
                                        'total_amount': total_amount,
                                        'main_debt': main_debt,
                                        'interest': interest,
                                        'total_payment': total_amount,
                                        'overdue_amount': Decimal(str(schedule.get('overdue_amount', 0))),
                                        'is_paid': 'paid' if str(schedule.get('is_paid')).lower() == "true" else 'not_paid'
                                    }
                                )

                            except Exception as e:
                                print(f"Ошибка при обработке графика платежа: {e}")
                                continue


                        # Массовое создание всех графиков
                        if schedules_to_create:
                            RepaymentSchedule.objects.bulk_create(schedules_to_create)
                            print(f"Добавлено {len(schedules_to_create)} графиков платежей для автомобиля {loan_guid}")

                except Exception as e:
                    print(f"Ошибка при обработке автомобиля {loan_guid}: {e}")
                    continue

        except Exception as e:
            print("Ошибка при обработке клиента:", e)
            continue
        