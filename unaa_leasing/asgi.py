import os 
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
# from applications.core.routing import websocket_urlpatterns as core_websocket_urlpatterns
# from applications.chat.routing import websocket_urlpatterns as chat_websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unaa_leasing.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            # core_websocket_urlpatterns + chat_websocket_urlpatterns,

        )
    ),
})