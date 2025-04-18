from django.urls import re_path
from .consumers import InterviewsConsumer

websocket_urlpatterns = [
    re_path(r'ws/interviews/$', InterviewsConsumer.as_asgi()),
]