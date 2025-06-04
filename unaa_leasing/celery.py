import os
from celery import Celery
from celery.schedules import crontab
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unaa_leasing.settings')

app = Celery('unaa_leasing')

# Загружаем настройки Celery из Django settings.py по префиксу CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически находит tasks.py во всех приложениях
app.autodiscover_tasks()


CELERY_BEAT_SCHEDULE = {
    'send_notifications_daily': {
        'task': 'core.tasks.send_notification_task',
        'schedule': timedelta(seconds=10),  # ежедневно в 10:00
    },
}

app.conf.beat_schedule = CELERY_BEAT_SCHEDULE
