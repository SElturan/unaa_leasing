import os
from celery import Celery
from celery.schedules import crontab
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unaa_leasing.settings')

app = Celery('unaa_leasing')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {

    # Твоя старая задача
    'send_notifications_daily': {
        'task': 'core.tasks.send_notification_task',
        'schedule': timedelta(seconds=10),
    },

    # Производственный вариант — ежедневно в 16:00
    # (оставь закомментированным пока тестируешь)
    'import_1c_every_day_16': {
        'task': 'core.tasks.import_clients_daily',
        'schedule': crontab(hour=16, minute=0),
    },
}
