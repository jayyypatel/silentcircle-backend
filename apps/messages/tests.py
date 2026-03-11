from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.conversations.models import Conversation, ConversationMember
from .models import Message, MessageRead

User = get_user_model()


class MessageApiTests(APITestCase):
    def setUp(self):
        self.sender = User.objects.create_user("msender", "Sender", "password12345")
        self.recipient = User.objects.create_user("mrecipient", "Recipient", "password12345")
        self.conv = Conversation.objects.create(type=Conversation.TYPE_PRIVATE, created_by=self.sender)
        ConversationMember.objects.create(conversation=self.conv, user=self.sender)
        ConversationMember.objects.create(conversation=self.conv, user=self.recipient)

    def test_history_returns_only_recipient_messages(self):
        Message.objects.create(
            conversation=self.conv,
            sender=self.sender,
            recipient=self.recipient,
            encrypted_payload="enc1",
            nonce="n1",
            signature="s1",
            sequence_number=1,
        )
        Message.objects.create(
            conversation=self.conv,
            sender=self.recipient,
            recipient=self.sender,
            encrypted_payload="enc2",
            nonce="n2",
            signature="s2",
            sequence_number=1,
        )

        self.client.force_authenticate(user=self.recipient)
        response = self.client.get(reverse("conversations-message-history", kwargs={"pk": self.conv.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(str(response.data[0]["recipient_id"]), str(self.recipient.id))

    @patch("apps.messages.views.get_channel_layer")
    def test_mark_read_creates_read_row(self, get_channel_layer_mock):
        layer = MagicMock()
        layer.group_send = AsyncMock()
        get_channel_layer_mock.return_value = layer

        msg = Message.objects.create(
            conversation=self.conv,
            sender=self.sender,
            recipient=self.recipient,
            encrypted_payload="enc1",
            nonce="n1",
            signature="s1",
            sequence_number=1,
        )

        self.client.force_authenticate(user=self.recipient)
        response = self.client.post(
            reverse("conversations-mark-read", kwargs={"pk": self.conv.id, "msg_id": msg.id}),
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(MessageRead.objects.filter(message=msg, user=self.recipient).exists())
