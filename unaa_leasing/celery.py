import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unaa_leasing.settings')

app = Celery('unaa_leasing')

# Загружаем настройки Celery из Django settings.py по префиксу CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически находит tasks.py во всех приложениях
app.autodiscover_tasks()
