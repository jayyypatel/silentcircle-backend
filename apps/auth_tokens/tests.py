from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import InviteToken

User = get_user_model()


class InviteTokenModelTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user("admin", "Admin", "password12345")
        self.assigned = User.objects.create_user("alice", "Alice")

    def test_is_valid_when_unused_and_unexpired(self):
        invite = InviteToken.objects.create(
            created_by=self.creator,
            assigned_to=self.assigned,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        self.assertTrue(invite.is_valid)

    def test_is_invalid_when_expired(self):
        invite = InviteToken.objects.create(
            created_by=self.creator,
            assigned_to=self.assigned,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertFalse(invite.is_valid)

    def test_is_invalid_when_already_used(self):
        invite = InviteToken.objects.create(
            created_by=self.creator,
            assigned_to=self.assigned,
            used_by=self.assigned,
            used_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )
        self.assertFalse(invite.is_valid)
