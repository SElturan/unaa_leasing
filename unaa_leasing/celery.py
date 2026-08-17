import os
from celery import Celery
from celery.schedules import crontab
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unaa_leasing.settings')



app = Celery('unaa_leasing')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
app.conf.timezone = 'Asia/Bishkek'
app.conf.enable_utc = False

app.conf.beat_schedule = {
    'sync_1c_daily': {
        'task': 'core.tasks.sync_1c_task',
        'schedule': crontab(hour=7, minute=0),
    },
    'send_notifications_daily': {
        'task': 'core.tasks.send_notification_task',
        'schedule': crontab(hour=9, minute=0),  # раз в день в 9:00
    },
        'daily_payments_summary': {
        'task': 'core.tasks.daily_payments_summary_task',
        'schedule': crontab(hour=18, minute=0),
    },
}