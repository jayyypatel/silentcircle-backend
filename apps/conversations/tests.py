from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import FriendRequest, Friendship

User = get_user_model()


class FriendRequestTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice2", "Alice", "password12345")
        self.bob = User.objects.create_user("bob2", "Bob", "password12345")

    def test_send_friend_request(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(reverse("friends-request-create"), {"username": "bob2"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], FriendRequest.STATUS_PENDING)

    def test_cross_request_auto_merges_to_friendship(self):
        FriendRequest.objects.create(from_user=self.bob, to_user=self.alice, status=FriendRequest.STATUS_PENDING)
        self.client.force_authenticate(user=self.alice)

        response = self.client.post(reverse("friends-request-create"), {"username": "bob2"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["auto_merged"])

        low, high = Friendship.canonical_pair(self.alice.id, self.bob.id)
        self.assertTrue(Friendship.objects.filter(user_low_id=low, user_high_id=high).exists())

    def test_cannot_request_self(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(reverse("friends-request-create"), {"username": "alice2"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_requires_target_user(self):
        request_obj = FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_PENDING,
        )
        eve = User.objects.create_user("eve2", "Eve", "password12345")
        self.client.force_authenticate(user=eve)
        response = self.client.post(reverse("friends-request-accept", kwargs={"pk": request_obj.id}), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reject_and_cancel_flows(self):
        request_obj = FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_PENDING,
        )

        self.client.force_authenticate(user=self.bob)
        reject_response = self.client.post(
            reverse("friends-request-reject", kwargs={"pk": request_obj.id}),
            {},
            format="json",
        )
        self.assertEqual(reject_response.status_code, status.HTTP_200_OK)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status, FriendRequest.STATUS_REJECTED)

        second = FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_PENDING,
        )
        self.client.force_authenticate(user=self.alice)
        cancel_response = self.client.post(
            reverse("friends-request-cancel", kwargs={"pk": second.id}),
            {},
            format="json",
        )
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        second.refresh_from_db()
        self.assertEqual(second.status, FriendRequest.STATUS_CANCELLED)


class ConversationFriendshipGatingTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice3", "Alice", "password12345")
        self.bob = User.objects.create_user("bob3", "Bob", "password12345")

    def test_private_conversation_requires_friendship(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(
            reverse("conversations-list-create"),
            {"user_id": str(self.bob.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_conversation_reuse_no_duplicate(self):
        low, high = Friendship.canonical_pair(self.alice.id, self.bob.id)
        Friendship.objects.create(user_low_id=low, user_high_id=high)

        self.client.force_authenticate(user=self.alice)
        first = self.client.post(reverse("conversations-list-create"), {"user_id": str(self.bob.id)}, format="json")
        second = self.client.post(reverse("conversations-list-create"), {"user_id": str(self.bob.id)}, format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["id"], second.data["id"])
