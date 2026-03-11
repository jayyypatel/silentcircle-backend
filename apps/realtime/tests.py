import asyncio
import uuid
from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.conversations.models import Conversation, ConversationMember, Friendship

from .consumers import ChatConsumer
from .middleware import WSTicketAuthMiddleware

User = get_user_model()


class WSTicketAuthMiddlewareTests(TestCase):
    def test_missing_ticket_closes_socket(self):
        events = []

        async def app(scope, receive, send):
            events.append("app-called")

        middleware = WSTicketAuthMiddleware(app)

        async def runner():
            sent = []

            async def send(message):
                sent.append(message)

            await middleware({"query_string": b""}, AsyncMock(), send)
            return sent

        sent_messages = asyncio.run(runner())
        self.assertEqual(events, [])
        self.assertEqual(sent_messages[0]["type"], "websocket.close")


class FakeRedis:
    def __init__(self):
        self.values = {}

    def setex(self, key, ttl, value):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)

    def exists(self, key):
        return 1 if key in self.values else 0


class FakeChannelLayer:
    def __init__(self):
        self.events = []

    async def group_send(self, group, payload):
        self.events.append((group, payload))


@override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
class ChatConsumerTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("rtalice", "RT Alice", "password12345")
        self.bob = User.objects.create_user("rtbob", "RT Bob", "password12345")
        low, high = Friendship.canonical_pair(self.alice.id, self.bob.id)
        Friendship.objects.create(user_low_id=low, user_high_id=high)
        self.conversation = Conversation.objects.create(type=Conversation.TYPE_PRIVATE, created_by=self.alice)
        ConversationMember.objects.create(conversation=self.conversation, user=self.alice)
        ConversationMember.objects.create(conversation=self.conversation, user=self.bob)

    @patch("apps.realtime.consumers.r", new_callable=FakeRedis)
    def test_send_ack_receive_and_read_receipt(self, _redis_mock):
        async def runner():
            _redis_mock.setex(f"presence:{self.bob.id}", 300, "1")

            consumer = ChatConsumer()
            consumer.scope = {"user": self.alice}
            consumer.user = self.alice
            consumer.channel_layer = FakeChannelLayer()
            consumer.send_json = AsyncMock()
            consumer.check_membership = AsyncMock(return_value=True)
            consumer.check_friendship = AsyncMock(return_value=True)
            consumer.touch_conversation = AsyncMock()
            consumer.mark_delivered = AsyncMock()
            fake_message = type(
                "Msg",
                (),
                {
                    "id": uuid.uuid4(),
                    "sequence_number": 7,
                    "created_at": timezone.now(),
                    "sender_id": self.alice.id,
                    "sender_x25519_public_key": "xpub",
                    "sender_ed25519_public_key": "epub",
                },
            )()
            consumer.save_message = AsyncMock(return_value=fake_message)

            await consumer.handle_send_message(
                {
                    "type": "send_message",
                    "temp_id": "tmp-1",
                    "conversation_id": str(self.conversation.id),
                    "recipient_id": str(self.bob.id),
                    "encrypted_payload": "abc123",
                    "nonce": "n1",
                    "signature": "sig1",
                }
            )

            read_consumer = ChatConsumer()
            read_consumer.scope = {"user": self.bob}
            read_consumer.user = self.bob
            read_consumer.channel_layer = FakeChannelLayer()
            read_consumer.send_json = AsyncMock()
            read_consumer.mark_read = AsyncMock(return_value=fake_message)
            await read_consumer.handle_message_read({"message_id": str(fake_message.id)})

            return consumer, read_consumer, fake_message

        sender_consumer, reader_consumer, message = asyncio.run(runner())
        sender_events = [call.args[0] for call in sender_consumer.send_json.call_args_list]
        self.assertEqual(sender_events[0]["type"], "message_ack")
        self.assertEqual(sender_events[1]["type"], "delivered_receipt")
        self.assertEqual(sender_events[0]["message_id"], str(message.id))

        self.assertEqual(len(sender_consumer.channel_layer.events), 1)
        group, payload = sender_consumer.channel_layer.events[0]
        self.assertEqual(group, f"user_{self.bob.id}")
        self.assertEqual(payload["type"], "chat.message")

        self.assertEqual(len(reader_consumer.channel_layer.events), 1)
        read_group, read_payload = reader_consumer.channel_layer.events[0]
        self.assertEqual(read_group, f"user_{self.alice.id}")
        self.assertEqual(read_payload["type"], "read.receipt")

    @patch("apps.realtime.middleware.r.getdel")
    def test_invalid_ticket_closes_socket(self, getdel_mock):
        getdel_mock.return_value = None
        events = []

        async def app(scope, receive, send):
            events.append("app-called")

        middleware = WSTicketAuthMiddleware(app)

        async def runner():
            sent = []

            async def send(message):
                sent.append(message)

            await middleware({"query_string": b"ticket=abc"}, AsyncMock(), send)
            return sent

        sent_messages = asyncio.run(runner())
        self.assertEqual(events, [])
        self.assertEqual(sent_messages[0]["type"], "websocket.close")
