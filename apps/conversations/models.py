import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class FriendRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_friend_requests")
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_friend_requests")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "friend_requests"
        indexes = [
            models.Index(fields=["from_user", "to_user"]),
            models.Index(fields=["to_user", "status"]),
            models.Index(fields=["from_user", "status"]),
        ]

    def clean(self):
        if self.from_user_id == self.to_user_id:
            raise ValidationError("Cannot send friend request to self.")


class Friendship(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_low = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friendships_low")
    user_high = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friendships_high")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "friendships"
        constraints = [
            models.UniqueConstraint(fields=["user_low", "user_high"], name="uniq_friendship_pair"),
        ]
        indexes = [
            models.Index(fields=["user_low"]),
            models.Index(fields=["user_high"]),
        ]

    def clean(self):
        if self.user_low_id == self.user_high_id:
            raise ValidationError("Friendship requires two different users.")

    @staticmethod
    def canonical_pair(user_a_id, user_b_id):
        if str(user_a_id) < str(user_b_id):
            return user_a_id, user_b_id
        return user_b_id, user_a_id


class Conversation(models.Model):
    TYPE_PRIVATE = "private"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=10, default=TYPE_PRIVATE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversations"
        indexes = [models.Index(fields=["-updated_at"])]


class ConversationMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation_memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversation_members"
        constraints = [models.UniqueConstraint(fields=["conversation", "user"], name="uniq_conversation_member")]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["conversation"]),
        ]
