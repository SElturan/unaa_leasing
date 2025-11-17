import pandas as pd
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from datetime import datetime

from core.models import ClientCar, InsuranceClient


class Command(BaseCommand):
    help = "Импорт ОСАГО из Excel и привязка по номеру автомобиля"

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Путь к Excel файлу со страховками'
        )

    def handle(self, *args, **options):
        file_path = options['file']

        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка чтения файла: {e}"))
            return

        COL_POLICY = "№ Полиса или договора перестрахования"
        COL_START = "Дата начала договора"
        COL_END = "Дата окончания"
        COL_CAR_NUMBER = "Госномер"

        required_columns = [COL_POLICY, COL_START, COL_END, COL_CAR_NUMBER]
        for col in required_columns:
            if col not in df.columns:
                self.stdout.write(self.style.ERROR(f"В Excel нет колонки: {col}"))
                return

        def parse_date_custom(v):
            """Парсер дат формата DD-MM-YYYY"""
            if not v or str(v).lower() == "nan":
                return None
            try:
                return datetime.strptime(str(v), "%d-%m-%Y").date()
            except:
                return None

        created_count = 0
        skipped_no_car = 0
        skipped_no_dates = 0

        for _, row in df.iterrows():

            car_number = str(row[COL_CAR_NUMBER]).strip().upper()

            if not car_number:
                skipped_no_car += 1
                continue

            car = ClientCar.objects.filter(car_number__iexact=car_number).first()

            if not car:
                skipped_no_car += 1
                continue

            start_date = parse_date_custom(row[COL_START])
            end_date = parse_date_custom(row[COL_END])

            if not start_date or not end_date:
                skipped_no_dates += 1
                continue

            InsuranceClient.objects.create(
                client=car,
                insurance_company="OSAGO",
                policy_number=str(row[COL_POLICY]).strip(),
                start_date=start_date,
                end_date=end_date,
            )

            created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Готово! Добавлено страховок: {created_count}, "
            f"пропущено из-за отсутствия машины: {skipped_no_car}, "
            f"пропущено из-за некорректной даты: {skipped_no_dates}"
        ))
