import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Send_Message

from .expo_push import send_push_message

import os


TOKEN = os.environ.get("EXPO_PUSH_TOKEN")


@receiver(post_save, sender=Send_Message)
def send_message_push(sender, instance, created, **kwargs):
    print("Send_Message signal вызван. created=%s id=%s" % (created, instance.id))
    if not created:
        return

    result = send_push_message(
        token=TOKEN,
        title="Новое сообщение",
        message=instance.message,
    )
