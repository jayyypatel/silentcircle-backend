from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auth_tokens.models import InviteToken

User = get_user_model()


class AuthFlowTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", "Admin", "password12345", is_staff=True)
        self.user = User.objects.create_user("alice", "Alice", "password12345")

    def test_login_success(self):
        response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "password12345"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh_token", response.cookies)

    def test_login_wrong_password(self):
        response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "bad-pass"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_inactive_user(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "password12345"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invite_complete_success(self):
        invited = User.objects.create_user("bob", "Bob")
        invite = InviteToken.objects.create(
            created_by=self.admin,
            assigned_to=invited,
            expires_at=timezone.now() + timedelta(hours=2),
        )

        response = self.client.post(
            reverse("auth-invite-complete", kwargs={"token": invite.token}),
            {
                "password": "my-new-password",
                "confirm_password": "my-new-password",
                "x25519_public_key": "x-pub-key",
                "ed25519_public_key": "ed-pub-key",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invited.refresh_from_db()
        invite.refresh_from_db()
        self.assertTrue(invited.check_password("my-new-password"))
        self.assertEqual(invited.x25519_public_key, "x-pub-key")
        self.assertEqual(invited.ed25519_public_key, "ed-pub-key")
        self.assertIsNotNone(invite.used_at)
        self.assertEqual(invite.used_by_id, invited.id)

    def test_invite_complete_expired_token(self):
        invited = User.objects.create_user("bob2", "Bob Two")
        invite = InviteToken.objects.create(
            created_by=self.admin,
            assigned_to=invited,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        response = self.client.post(
            reverse("auth-invite-complete", kwargs={"token": invite.token}),
            {
                "password": "my-new-password",
                "confirm_password": "my-new-password",
                "x25519_public_key": "x-pub-key",
                "ed25519_public_key": "ed-pub-key",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invite_complete_used_token(self):
        invited = User.objects.create_user("bob3", "Bob Three")
        invite = InviteToken.objects.create(
            created_by=self.admin,
            assigned_to=invited,
            used_by=invited,
            used_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        response = self.client.post(
            reverse("auth-invite-complete", kwargs={"token": invite.token}),
            {
                "password": "my-new-password",
                "confirm_password": "my-new-password",
                "x25519_public_key": "x-pub-key",
                "ed25519_public_key": "ed-pub-key",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invite_complete_password_mismatch(self):
        invited = User.objects.create_user("bob4", "Bob Four")
        invite = InviteToken.objects.create(
            created_by=self.admin,
            assigned_to=invited,
            expires_at=timezone.now() + timedelta(hours=1),
        )

        response = self.client.post(
            reverse("auth-invite-complete", kwargs={"token": invite.token}),
            {
                "password": "my-new-password",
                "confirm_password": "wrong-password",
                "x25519_public_key": "x-pub-key",
                "ed25519_public_key": "ed-pub-key",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.users.views.redis.from_url")
    def test_ws_ticket_with_valid_jwt(self, redis_from_url_mock):
        redis_client = MagicMock()
        redis_from_url_mock.return_value = redis_client
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("auth-ws-ticket"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("ticket", response.data)
        redis_client.setex.assert_called_once()

    def test_ws_ticket_without_jwt(self):
        response = self.client.get(reverse("auth-ws-ticket"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_uses_cookie(self):
        login = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "password12345"},
            format="json",
        )
        refresh_token = login.cookies["refresh_token"].value

        self.client.cookies["refresh_token"] = refresh_token
        response = self.client.post(reverse("auth-token-refresh"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh_token", response.cookies)

    def test_token_refresh_missing_cookie_returns_401(self):
        response = self.client.post(reverse("auth-token-refresh"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_clears_refresh_cookie(self):
        login = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "password12345"},
            format="json",
        )
        access_token = login.data["access"]
        refresh_token = login.cookies["refresh_token"].value

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        self.client.cookies["refresh_token"] = refresh_token

        response = self.client.post(reverse("auth-logout"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIn("refresh_token", response.cookies)

    def test_change_password_blacklists_existing_refresh_tokens(self):
        login = self.client.post(
            reverse("auth-login"),
            {"username": "alice", "password": "password12345"},
            format="json",
        )
        refresh_token = login.cookies["refresh_token"].value
        access_token = login.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.post(
            reverse("auth-change-password"),
            {"old_password": "password12345", "new_password": "new-password-123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.credentials()
        self.client.cookies["refresh_token"] = refresh_token
        refresh_response = self.client.post(reverse("auth-token-refresh"), {}, format="json")
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserSearchTests(APITestCase):
    def setUp(self):
        self.me = User.objects.create_user("alice", "Alice", "password12345")
        self.other = User.objects.create_user("alina", "Alina", "password12345")
        self.client.force_authenticate(user=self.me)

    def test_user_search_requires_min_length(self):
        response = self.client.get(reverse("users-search"), {"q": "a"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_user_search_excludes_self_and_returns_matches(self):
        response = self.client.get(reverse("users-search"), {"q": "ali"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = {item["username"] for item in response.data}
        self.assertIn("alina", usernames)
        self.assertNotIn("alice", usernames)


class CurrentUserTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("operator", "Operator", "password12345")
        self.client.force_authenticate(user=self.user)

    def test_patch_current_user_updates_public_keys_and_display_name(self):
        response = self.client.patch(
            reverse("users-me"),
            {
                "display_name": "Updated Operator",
                "x25519_public_key": "x-new",
                "ed25519_public_key": "ed-new",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, "Updated Operator")
        self.assertEqual(self.user.x25519_public_key, "x-new")
        self.assertEqual(self.user.ed25519_public_key, "ed-new")


class AdminPermissionTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff", "Staff", "password12345", is_staff=True)
        self.user = User.objects.create_user("plain", "Plain", "password12345")

    def test_admin_endpoint_rejects_non_staff(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("admin-users-list-create"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_endpoint_allows_staff(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(reverse("admin-users-list-create"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AdminInviteFlowTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staffadmin", "Staff Admin", "password12345", is_staff=True)
        self.assigned = User.objects.create_user("targetuser", "Target User", "password12345")

    def test_admin_can_create_list_and_revoke_invite(self):
        self.client.force_authenticate(user=self.staff)
        create_response = self.client.post(
            reverse("admin-invites-list-create"),
            {"assigned_to": str(self.assigned.id), "expires_hours": 24},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        invite_id = create_response.data["id"]

        list_response = self.client.get(reverse("admin-invites-list-create"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item["id"] == invite_id for item in list_response.data))

        revoke_response = self.client.delete(reverse("admin-invites-revoke", kwargs={"pk": invite_id}))
        self.assertEqual(revoke_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_cannot_revoke_used_invite(self):
        invite = InviteToken.objects.create(
            created_by=self.staff,
            assigned_to=self.assigned,
            used_by=self.assigned,
            used_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )
        self.client.force_authenticate(user=self.staff)
        response = self.client.delete(reverse("admin-invites-revoke", kwargs={"pk": invite.id}))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AdminUserStatusTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user("statusstaff", "Status Staff", "password12345", is_staff=True)
        self.target = User.objects.create_user("statususer", "Status User", "password12345")

    def test_admin_can_deactivate_and_reactivate_user(self):
        self.client.force_authenticate(user=self.staff)

        deactivate_response = self.client.post(
            reverse("admin-users-deactivate", kwargs={"pk": self.target.id}),
            {"is_active": False},
            format="json",
        )
        self.assertEqual(deactivate_response.status_code, status.HTTP_200_OK)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

        reactivate_response = self.client.post(
            reverse("admin-users-deactivate", kwargs={"pk": self.target.id}),
            {"is_active": True},
            format="json",
        )
        self.assertEqual(reactivate_response.status_code, status.HTTP_200_OK)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)
