from django.db import transaction
from django.db.models import Max
from django.utils import timezone

import redis
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from apps.conversations.models import Conversation, Friendship
from apps.messages.models import Message, MessageRead

r = redis.from_url(settings.REDIS_URL)


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.user_group = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()
        await self.set_presence(True)
        await self.send_json({"type": "connected", "user_id": str(self.user.id)})

    async def disconnect(self, code):
        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
        await self.set_presence(False)
        await self.update_last_seen()

    async def receive_json(self, content, **kwargs):
        event_type = content.get("type")
        handlers = {
            "send_message": self.handle_send_message,
            "typing_start": self.handle_typing_start,
            "typing_stop": self.handle_typing_stop,
            "message_read": self.handle_message_read,
        }
        handler = handlers.get(event_type)
        if handler:
            await handler(content)
        else:
            await self.send_json({"type": "error", "code": "UNKNOWN_TYPE"})

    async def handle_send_message(self, data):
        required = ["conversation_id", "recipient_id", "encrypted_payload", "nonce", "signature"]
        if not all(data.get(item) for item in required):
            await self.send_json({"type": "error", "code": "INVALID_PAYLOAD"})
            return

        is_member = await self.check_membership(data["conversation_id"], self.user.id)
        if not is_member:
            await self.send_json({"type": "error", "code": "NOT_MEMBER"})
            return

        is_friend = await self.check_friendship(self.user.id, data["recipient_id"])
        if not is_friend:
            await self.send_json({"type": "error", "code": "NOT_FRIENDS"})
            return

        message = await self.save_message(data)
        await self.touch_conversation(data["conversation_id"])

        await self.send_json(
            {
                "type": "message_ack",
                "temp_id": data.get("temp_id"),
                "message_id": str(message.id),
                "sequence_number": message.sequence_number,
                "created_at": message.created_at.isoformat(),
            }
        )

        await self.channel_layer.group_send(
            f"user_{data['recipient_id']}",
            {
                "type": "chat.message",
                "message_id": str(message.id),
                "conversation_id": data["conversation_id"],
                "sender_id": str(self.user.id),
                "recipient_id": str(data["recipient_id"]),
                "encrypted_payload": data["encrypted_payload"],
                "nonce": data["nonce"],
                "signature": data["signature"],
                "sender_x25519_public_key": message.sender_x25519_public_key,
                "sender_ed25519_public_key": message.sender_ed25519_public_key,
                "sequence_number": message.sequence_number,
                "created_at": message.created_at.isoformat(),
            },
        )

        if r.exists(f"presence:{data['recipient_id']}"):
            await self.mark_delivered(message.id)
            await self.send_json({"type": "delivered_receipt", "message_id": str(message.id)})

    async def handle_typing_start(self, data):
        recipient_id = data.get("recipient_id")
        conversation_id = data.get("conversation_id")
        if not recipient_id or not conversation_id:
            return
        r.setex(f"typing:{conversation_id}:{self.user.id}", 5, "1")
        await self.channel_layer.group_send(
            f"user_{recipient_id}",
            {
                "type": "typing.event",
                "conversation_id": conversation_id,
                "user_id": str(self.user.id),
                "is_typing": True,
            },
        )

    async def handle_typing_stop(self, data):
        recipient_id = data.get("recipient_id")
        conversation_id = data.get("conversation_id")
        if not recipient_id or not conversation_id:
            return
        r.delete(f"typing:{conversation_id}:{self.user.id}")
        await self.channel_layer.group_send(
            f"user_{recipient_id}",
            {
                "type": "typing.event",
                "conversation_id": conversation_id,
                "user_id": str(self.user.id),
                "is_typing": False,
            },
        )

    async def handle_message_read(self, data):
        message_id = data.get("message_id")
        if not message_id:
            return
        message = await self.mark_read(message_id)
        if not message:
            return

        await self.channel_layer.group_send(
            f"user_{message.sender_id}",
            {
                "type": "read.receipt",
                "message_id": str(message.id),
                "read_by": str(self.user.id),
                "read_at": timezone.now().isoformat(),
            },
        )

    async def chat_message(self, event):
        await self.send_json(
            {
                "type": "receive_message",
                "message_id": event["message_id"],
                "conversation_id": event["conversation_id"],
                "sender_id": event["sender_id"],
                "recipient_id": event.get("recipient_id"),
                "encrypted_payload": event["encrypted_payload"],
                "nonce": event["nonce"],
                "signature": event["signature"],
                "sender_x25519_public_key": event.get("sender_x25519_public_key", ""),
                "sender_ed25519_public_key": event.get("sender_ed25519_public_key", ""),
                "sequence_number": event["sequence_number"],
                "created_at": event["created_at"],
            }
        )

    async def read_receipt(self, event):
        await self.send_json(
            {
                "type": "read_receipt",
                "message_id": event["message_id"],
                "read_by": event["read_by"],
                "read_at": event["read_at"],
            }
        )

    async def typing_event(self, event):
        await self.send_json(
            {
                "type": "typing",
                "conversation_id": event["conversation_id"],
                "user_id": event["user_id"],
                "is_typing": event["is_typing"],
            }
        )

    @sync_to_async
    def set_presence(self, online):
        if online:
            r.setex(f"presence:{self.user.id}", 300, "1")
        else:
            r.delete(f"presence:{self.user.id}")

    @sync_to_async
    def update_last_seen(self):
        self.user.last_seen = timezone.now()
        self.user.save(update_fields=["last_seen", "updated_at"])

    @sync_to_async
    def check_membership(self, conversation_id, user_id):
        return Conversation.objects.filter(id=conversation_id, members__user_id=user_id).exists()

    @sync_to_async
    def check_friendship(self, user_a_id, user_b_id):
        low, high = Friendship.canonical_pair(user_a_id, user_b_id)
        return Friendship.objects.filter(user_low_id=low, user_high_id=high).exists()

    @sync_to_async
    def touch_conversation(self, conversation_id):
        Conversation.objects.filter(id=conversation_id).update(updated_at=timezone.now())

    @sync_to_async
    def mark_delivered(self, message_id):
        Message.objects.filter(id=message_id).update(delivered_at=timezone.now())

    @sync_to_async
    def mark_read(self, message_id):
        message = Message.objects.filter(id=message_id, recipient=self.user).first()
        if not message:
            return None
        MessageRead.objects.get_or_create(message=message, user=self.user)
        return message

    @sync_to_async
    def save_message(self, data):
        with transaction.atomic():
            max_seq = (
                Message.objects.filter(conversation_id=data["conversation_id"], recipient_id=data["recipient_id"])
                .select_for_update()
                .aggregate(Max("sequence_number"))
            )
            sequence_number = (max_seq["sequence_number__max"] or 0) + 1

            return Message.objects.create(
                conversation_id=data["conversation_id"],
                sender_id=self.user.id,
                recipient_id=data["recipient_id"],
                encrypted_payload=data["encrypted_payload"],
                nonce=data["nonce"],
                signature=data["signature"],
                sender_x25519_public_key=self.user.x25519_public_key,
                sender_ed25519_public_key=self.user.ed25519_public_key,
                sequence_number=sequence_number,
            )
