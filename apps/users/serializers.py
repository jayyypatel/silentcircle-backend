from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.auth_tokens.models import InviteToken

User = get_user_model()


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "display_name", "is_staff")


class InviteCompleteSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    x25519_public_key = serializers.CharField()
    ed25519_public_key = serializers.CharField()

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class TokenRefreshOutputSerializer(serializers.Serializer):
    access = serializers.CharField()


class WSTicketOutputSerializer(serializers.Serializer):
    ticket = serializers.UUIDField()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=12)


class UserSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "display_name")


class AdminUserSerializer(serializers.ModelSerializer):
    invited_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "display_name",
            "is_active",
            "is_staff",
            "invited_by",
            "last_seen",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "last_seen")


class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = User
        fields = ("id", "username", "display_name", "password", "is_staff", "is_active", "invited_by")
        read_only_fields = ("id",)

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        return User.objects.create_user(password=password, **validated_data)


class AdminUserDeactivateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class InviteTokenSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    assigned_to = UserSummarySerializer(read_only=True)
    used_by = UserSummarySerializer(read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = InviteToken
        fields = (
            "id",
            "token",
            "status",
            "created_by",
            "assigned_to",
            "used_by",
            "expires_at",
            "used_at",
            "created_at",
        )

    def get_status(self, obj):
        if obj.used_at:
            return "used"
        if obj.expires_at <= timezone.now():
            return "expired"
        return "active"


class AdminInviteCreateSerializer(serializers.Serializer):
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    expires_hours = serializers.IntegerField(min_value=1, max_value=168, default=24)
