import uuid
from datetime import timedelta

import redis
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.auth_tokens.models import InviteToken
from .permissions import IsAdminUser
from .serializers import (
    AdminInviteCreateSerializer,
    AdminUserCreateSerializer,
    AdminUserDeactivateSerializer,
    AdminUserSerializer,
    ChangePasswordSerializer,
    InviteCompleteSerializer,
    InviteTokenSerializer,
    LoginSerializer,
    TokenRefreshOutputSerializer,
    UserSearchSerializer,
    UserSummarySerializer,
    WSTicketOutputSerializer,
)

User = get_user_model()


def _cookie_config():
    return {
        "key": settings.AUTH_REFRESH_COOKIE_NAME,
        "httponly": settings.AUTH_REFRESH_COOKIE_HTTPONLY,
        "secure": settings.AUTH_REFRESH_COOKIE_SECURE,
        "samesite": settings.AUTH_REFRESH_COOKIE_SAMESITE,
        "max_age": settings.AUTH_REFRESH_COOKIE_MAX_AGE,
        "path": settings.AUTH_REFRESH_COOKIE_PATH,
    }


def _set_refresh_cookie(response, refresh_token):
    cfg = _cookie_config()
    response.set_cookie(
        cfg["key"],
        str(refresh_token),
        httponly=cfg["httponly"],
        secure=cfg["secure"],
        samesite=cfg["samesite"],
        max_age=cfg["max_age"],
        path=cfg["path"],
    )


def _delete_refresh_cookie(response):
    cfg = _cookie_config()
    response.delete_cookie(cfg["key"], path=cfg["path"], samesite=cfg["samesite"])


def _blacklist_all_user_refresh_tokens(user):
    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)


class InviteValidateView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        invite = InviteToken.objects.filter(token=token).select_related("assigned_to").first()
        if not invite or not invite.is_valid:
            return Response({"detail": "Invite token not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "valid": True,
                "username": invite.assigned_to.username,
                "display_name": invite.assigned_to.display_name,
            }
        )


class InviteCompleteView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, token):
        serializer = InviteCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invite = InviteToken.objects.filter(token=token).select_related("assigned_to").first()
        if not invite:
            return Response({"detail": "Invalid invite token."}, status=status.HTTP_404_NOT_FOUND)
        if invite.used_at is not None:
            return Response({"detail": "Invite token already used."}, status=status.HTTP_400_BAD_REQUEST)
        if invite.expires_at <= timezone.now():
            return Response({"detail": "Invite token expired."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user = invite.assigned_to
            user.set_password(serializer.validated_data["password"])
            user.x25519_public_key = serializer.validated_data["x25519_public_key"]
            user.ed25519_public_key = serializer.validated_data["ed25519_public_key"]
            user.save(update_fields=["password", "x25519_public_key", "ed25519_public_key", "updated_at"])

            invite.used_by = user
            invite.used_at = timezone.now()
            invite.save(update_fields=["used_by", "used_at"])

        refresh = RefreshToken.for_user(user)
        payload = {
            "access": str(refresh.access_token),
            "user": UserSummarySerializer(user).data,
        }
        response = Response(payload, status=status.HTTP_200_OK)
        _set_refresh_cookie(response, refresh)
        return response


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"].strip().lower()
        password = serializer.validated_data["password"]
        user = authenticate(request=request, username=username, password=password)

        if not user or not user.is_active:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                "access": str(refresh.access_token),
                "user": UserSummarySerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )
        _set_refresh_cookie(response, refresh)
        return response


class LogoutView(APIView):
    def post(self, request):
        cookie_name = settings.AUTH_REFRESH_COOKIE_NAME
        raw_refresh = request.COOKIES.get(cookie_name)

        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass

        response = Response(status=status.HTTP_204_NO_CONTENT)
        _delete_refresh_cookie(response)
        return response


class TokenRefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        if not raw_refresh:
            return Response({"detail": "Refresh token missing."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            old_refresh = RefreshToken(raw_refresh)
            user_id = old_refresh.get("user_id")
            user = User.objects.filter(id=user_id, is_active=True).first()
            if not user:
                raise TokenError("User not found")

            if jwt_api_settings.ROTATE_REFRESH_TOKENS:
                new_refresh = RefreshToken.for_user(user)
                if jwt_api_settings.BLACKLIST_AFTER_ROTATION:
                    try:
                        old_refresh.blacklist()
                    except TokenError:
                        pass
            else:
                new_refresh = old_refresh

            access = str(new_refresh.access_token)
        except TokenError:
            return Response({"detail": "Invalid refresh token."}, status=status.HTTP_401_UNAUTHORIZED)

        data = TokenRefreshOutputSerializer({"access": access}).data
        response = Response(data, status=status.HTTP_200_OK)
        _set_refresh_cookie(response, new_refresh)
        return response


class WSTicketView(APIView):
    def get_redis_client(self):
        return redis.from_url(settings.REDIS_URL)

    def get(self, request):
        ticket = uuid.uuid4()
        redis_client = self.get_redis_client()
        redis_client.setex(f"ws_ticket:{ticket}", 30, str(request.user.id))
        data = WSTicketOutputSerializer({"ticket": ticket}).data
        return Response(data, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response({"detail": "Old password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        _blacklist_all_user_refresh_tokens(user)

        return Response({"detail": "Password changed."}, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    def get(self, request):
        return Response(UserSummarySerializer(request.user).data, status=status.HTTP_200_OK)


class UserSearchView(generics.ListAPIView):
    serializer_class = UserSearchSerializer
    pagination_class = None

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip().lower()
        if len(q) < 2:
            return User.objects.none()

        return (
            User.objects.filter(username__icontains=q, is_active=True)
            .exclude(id=self.request.user.id)
            .only("id", "username", "display_name")[:10]
        )


class AdminUserListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    pagination_class = None

    def get_queryset(self):
        return User.objects.all().order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminUserCreateSerializer
        return AdminUserSerializer


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    queryset = User.objects.all().order_by("-created_at")
    serializer_class = AdminUserSerializer


class AdminUserDeactivateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        serializer = AdminUserDeactivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user.is_active = serializer.validated_data["is_active"]
        user.save(update_fields=["is_active", "updated_at"])
        return Response(AdminUserSerializer(user).data, status=status.HTTP_200_OK)


class AdminInviteListCreateView(generics.GenericAPIView):
    permission_classes = [IsAdminUser]
    pagination_class = None

    def get(self, request):
        invites = InviteToken.objects.select_related("created_by", "assigned_to", "used_by").order_by("-created_at")
        return Response(InviteTokenSerializer(invites, many=True).data)

    def post(self, request):
        serializer = AdminInviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invite = InviteToken.objects.create(
            created_by=request.user,
            assigned_to=serializer.validated_data["assigned_to"],
            expires_at=timezone.now() + timedelta(hours=serializer.validated_data["expires_hours"]),
        )
        return Response(InviteTokenSerializer(invite).data, status=status.HTTP_201_CREATED)


class AdminInviteRevokeView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, pk):
        invite = get_object_or_404(InviteToken, pk=pk)
        if invite.used_at is not None:
            return Response({"detail": "Used invite cannot be revoked."}, status=status.HTTP_400_BAD_REQUEST)

        invite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
