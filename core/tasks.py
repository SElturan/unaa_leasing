from celery import shared_task
from .fetch_1c_data import fetch_new_clients_from_1c

@shared_task
def fetch_clients_task():
    fetch_new_clients_from_1c()
    return "Fetch clients task completed successfully."