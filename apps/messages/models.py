import uuid

from django.conf import settings
from django.db import models


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey("conversations.Conversation", on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="sent_messages")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="received_messages")
    encrypted_payload = models.TextField()
    nonce = models.CharField(max_length=128)
    signature = models.TextField()
    sender_x25519_public_key = models.TextField(blank=True, default="")
    sender_ed25519_public_key = models.TextField(blank=True, default="")
    sequence_number = models.IntegerField()
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
        constraints = [
            models.UniqueConstraint(fields=["conversation", "recipient", "sequence_number"], name="uniq_msg_sequence_per_recipient"),
        ]
        indexes = [
            models.Index(fields=["conversation", "-sequence_number"]),
            models.Index(fields=["sender"]),
            models.Index(fields=["recipient"]),
        ]


class MessageRead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="message_reads")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "message_reads"
        constraints = [models.UniqueConstraint(fields=["message", "user"], name="uniq_message_read")]
