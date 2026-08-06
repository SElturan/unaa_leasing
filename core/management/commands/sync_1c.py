from datetime import date, datetime, timedelta 
from django.conf import settings
from django.core.management.base import BaseCommand
 
from core.sync_1c import import_from_1c, OneCError
 
 
class Command(BaseCommand):
    help = 'Синхронизация данных с 1С'

    def add_arguments(self, parser):
        parser.add_argument('--days-back', type=int, default=None,
                            help='За сколько дней назад тянуть (по умолчанию — с ONEC_SYNC_BEGIN_DATE)')
        parser.add_argument('--guid', type=str, default=None)
        parser.add_argument('--name', type=str, default=None)

    def handle(self, *args, **options):
        today = date.today()

        # endDate всегда сегодня
        end_date = today

        # начало периода: либо смещение из аргумента, либо фиксированная дата из настроек
        if options['days_back']:
            begin_date = today - timedelta(days=options['days_back'])
        else:
            begin_date = datetime.strptime(
                settings.ONEC_SYNC_BEGIN_DATE, '%Y-%m-%d'
            ).date()

        self.stdout.write(f"Период: {begin_date} — {end_date}")

        try:
            stats = import_from_1c(
                begin_date=begin_date,
                end_date=end_date,
                customer_guid=options['guid'],
                customer_name=options['name'],
            )
        except OneCError as e:
            self.stderr.write(self.style.ERROR(f"Ошибка: {e}"))
            return

        self.stdout.write(self.style.SUCCESS(str(stats)))