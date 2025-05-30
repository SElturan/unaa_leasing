from django.contrib.auth import get_user_model
import requests
import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.serializers.json import DjangoJSONEncoder
from core.models import Send_Message
from .expo_push import send_push_message

User = get_user_model()

@receiver(post_save, sender=Send_Message)
def send_message_to_ws(sender, instance, created, **kwargs):
    if created:
        # 1. WebSocket-сообщение
        # channel_layer = get_channel_layer()
        # async_to_sync(channel_layer.group_send)(
        #     'broadcast',
        #     {
        #         'type': 'send_message',
        #         'message': json.dumps({
        #             'id': instance.id,
        #             'message': instance.message,
        #             'created_at': instance.created_at.isoformat(),
        #         }, cls=DjangoJSONEncoder)
        #     }
        # )

        # 2. Пуш-сообщения всем юзерам с Expo Token
        users_with_token = User.objects.filter(expo_push_token__isnull=False).exclude(expo_push_token='')
        for user in users_with_token:
            send_push_message(
                token=user.expo_push_token,
                title="Новое сообщение",
                message=instance.message
            )
