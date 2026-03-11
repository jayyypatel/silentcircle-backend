from urllib.parse import parse_qs

import redis
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings
from redis.exceptions import ResponseError

from apps.users.models import User

r = redis.from_url(settings.REDIS_URL)


class WSTicketAuthMiddleware(BaseMiddleware):
    def _consume_ticket(self, ticket):
        key = f"ws_ticket:{ticket}"
        try:
            return r.getdel(key)
        except (AttributeError, ResponseError):
            # Redis < 6.2 fallback when GETDEL is unavailable.
            with r.pipeline() as pipe:
                pipe.get(key)
                pipe.delete(key)
                value, _ = pipe.execute()
                return value

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        ticket = params.get("ticket", [None])[0]

        if not ticket:
            await send({"type": "websocket.close", "code": 4001})
            return

        user_id = self._consume_ticket(ticket)
        if not user_id:
            await send({"type": "websocket.close", "code": 4001})
            return

        user = await self.get_user(user_id.decode())
        if not user:
            await send({"type": "websocket.close", "code": 4001})
            return

        scope["user"] = user
        await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return None
