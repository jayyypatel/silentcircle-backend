from rest_framework import serializers

from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = (
            "id",
            "conversation_id",
            "sender_id",
            "recipient_id",
            "encrypted_payload",
            "nonce",
            "signature",
            "sender_x25519_public_key",
            "sender_ed25519_public_key",
            "sequence_number",
            "delivered_at",
            "created_at",
        )
