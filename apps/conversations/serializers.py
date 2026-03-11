from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Conversation, ConversationMember, FriendRequest, Friendship

User = get_user_model()


class BasicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "display_name", "is_staff")


class FriendRequestCreateSerializer(serializers.Serializer):
    username = serializers.CharField(required=False)
    user_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        if not attrs.get("username") and not attrs.get("user_id"):
            raise serializers.ValidationError("Provide username or user_id.")
        return attrs


class FriendRequestSerializer(serializers.ModelSerializer):
    from_user = BasicUserSerializer(read_only=True)
    to_user = BasicUserSerializer(read_only=True)

    class Meta:
        model = FriendRequest
        fields = ("id", "from_user", "to_user", "status", "created_at", "updated_at")


class FriendshipSerializer(serializers.Serializer):
    friend = BasicUserSerializer()
    created_at = serializers.DateTimeField()


class ConversationCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()


class ConversationSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ("id", "type", "other_user", "created_at", "updated_at")

    def get_other_user(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        other_member = obj.members.exclude(user_id=request.user.id).select_related("user").first()
        return BasicUserSerializer(other_member.user).data if other_member else None


class ConversationMemberSerializer(serializers.ModelSerializer):
    user = BasicUserSerializer(read_only=True)

    class Meta:
        model = ConversationMember
        fields = ("id", "user", "joined_at")


class ConversationDetailSerializer(serializers.ModelSerializer):
    members = ConversationMemberSerializer(many=True, read_only=True)
    other_user = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ("id", "type", "other_user", "members", "created_at", "updated_at")

    def get_other_user(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        other_member = obj.members.exclude(user_id=request.user.id).select_related("user").first()
        return BasicUserSerializer(other_member.user).data if other_member else None
