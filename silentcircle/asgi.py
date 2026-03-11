"""ASGI config for silentcircle project."""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from apps.realtime.middleware import WSTicketAuthMiddleware
from apps.realtime.routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "silentcircle.settings.development")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": WSTicketAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
