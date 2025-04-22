# consumers.py

from channels.generic.websocket import AsyncWebsocketConsumer
import json

class BroadcastConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add('broadcast', self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('broadcast', self.channel_name)

    async def send_message(self, event):
        await self.send(text_data=event['message'])
