# signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Send_Message
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.serializers.json import DjangoJSONEncoder
import json

@receiver(post_save, sender=Send_Message)
def send_message_to_ws(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'broadcast',  # группа WebSocket
            {
                'type': 'send_message',
                'message': json.dumps({
                    'id': instance.id,
                    'message': instance.message,
                    'created_at': instance.created_at.isoformat(),
                }, cls=DjangoJSONEncoder)
            }
        )
