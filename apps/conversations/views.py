from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, ConversationMember, FriendRequest, Friendship
from .serializers import (
    ConversationCreateSerializer,
    ConversationDetailSerializer,
    ConversationSerializer,
    FriendRequestCreateSerializer,
    FriendRequestSerializer,
    FriendshipSerializer,
)

User = get_user_model()


class FriendRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FriendRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target = None
        if serializer.validated_data.get("user_id"):
            target = User.objects.filter(id=serializer.validated_data["user_id"], is_active=True).first()
        elif serializer.validated_data.get("username"):
            target = User.objects.filter(username=serializer.validated_data["username"].strip().lower(), is_active=True).first()

        if not target:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if target.id == request.user.id:
            return Response({"detail": "Cannot send friend request to yourself."}, status=status.HTTP_400_BAD_REQUEST)

        low, high = Friendship.canonical_pair(request.user.id, target.id)
        if Friendship.objects.filter(user_low_id=low, user_high_id=high).exists():
            return Response({"detail": "Already friends."}, status=status.HTTP_400_BAD_REQUEST)

        existing_outgoing = FriendRequest.objects.filter(
            from_user=request.user,
            to_user=target,
            status=FriendRequest.STATUS_PENDING,
        ).first()
        if existing_outgoing:
            return Response(FriendRequestSerializer(existing_outgoing).data, status=status.HTTP_200_OK)

        existing_reverse = FriendRequest.objects.filter(
            from_user=target,
            to_user=request.user,
            status=FriendRequest.STATUS_PENDING,
        ).first()

        with transaction.atomic():
            if existing_reverse:
                friendship, _ = Friendship.objects.get_or_create(user_low_id=low, user_high_id=high)
                existing_reverse.status = FriendRequest.STATUS_ACCEPTED
                existing_reverse.save(update_fields=["status", "updated_at"])

                accepted = FriendRequest.objects.create(
                    from_user=request.user,
                    to_user=target,
                    status=FriendRequest.STATUS_ACCEPTED,
                )
                return Response(
                    {
                        "auto_merged": True,
                        "friendship": FriendshipSerializer(
                            {"friend": target, "created_at": friendship.created_at}
                        ).data,
                        "request": FriendRequestSerializer(accepted).data,
                    },
                    status=status.HTTP_201_CREATED,
                )

            friend_request = FriendRequest.objects.create(
                from_user=request.user,
                to_user=target,
                status=FriendRequest.STATUS_PENDING,
            )

        return Response(FriendRequestSerializer(friend_request).data, status=status.HTTP_201_CREATED)


class IncomingFriendRequestsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer
    pagination_class = None

    def get_queryset(self):
        return FriendRequest.objects.filter(to_user=self.request.user, status=FriendRequest.STATUS_PENDING).select_related(
            "from_user", "to_user"
        ).order_by("-created_at")


class OutgoingFriendRequestsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer
    pagination_class = None

    def get_queryset(self):
        return FriendRequest.objects.filter(from_user=self.request.user, status=FriendRequest.STATUS_PENDING).select_related(
            "from_user", "to_user"
        ).order_by("-created_at")


class AcceptFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        friend_request = get_object_or_404(FriendRequest, pk=pk)
        if friend_request.to_user_id != request.user.id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        if friend_request.status != FriendRequest.STATUS_PENDING:
            return Response({"detail": "Request is not pending."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            friend_request.status = FriendRequest.STATUS_ACCEPTED
            friend_request.save(update_fields=["status", "updated_at"])
            low, high = Friendship.canonical_pair(friend_request.from_user_id, friend_request.to_user_id)
            Friendship.objects.get_or_create(user_low_id=low, user_high_id=high)

        return Response(FriendRequestSerializer(friend_request).data, status=status.HTTP_200_OK)


class RejectFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        friend_request = get_object_or_404(FriendRequest, pk=pk)
        if friend_request.to_user_id != request.user.id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        if friend_request.status != FriendRequest.STATUS_PENDING:
            return Response({"detail": "Request is not pending."}, status=status.HTTP_400_BAD_REQUEST)

        friend_request.status = FriendRequest.STATUS_REJECTED
        friend_request.save(update_fields=["status", "updated_at"])
        return Response(FriendRequestSerializer(friend_request).data, status=status.HTTP_200_OK)


class CancelFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        friend_request = get_object_or_404(FriendRequest, pk=pk)
        if friend_request.from_user_id != request.user.id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        if friend_request.status != FriendRequest.STATUS_PENDING:
            return Response({"detail": "Request is not pending."}, status=status.HTTP_400_BAD_REQUEST)

        friend_request.status = FriendRequest.STATUS_CANCELLED
        friend_request.save(update_fields=["status", "updated_at"])
        return Response(FriendRequestSerializer(friend_request).data, status=status.HTTP_200_OK)


class FriendshipListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        friendships = Friendship.objects.filter(Q(user_low=request.user) | Q(user_high=request.user)).select_related(
            "user_low", "user_high"
        ).order_by("-created_at")

        data = []
        for fs in friendships:
            friend = fs.user_high if fs.user_low_id == request.user.id else fs.user_low
            data.append(FriendshipSerializer({"friend": friend, "created_at": fs.created_at}).data)
        return Response(data, status=status.HTTP_200_OK)


class ConversationListCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get(self, request):
        conversation_ids = ConversationMember.objects.filter(user=request.user).values_list("conversation_id", flat=True)
        conversations = Conversation.objects.filter(id__in=conversation_ids).prefetch_related("members__user").order_by("-updated_at")
        data = ConversationSerializer(conversations, many=True, context={"request": request}).data
        return Response(data)

    def post(self, request):
        serializer = ConversationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        other = get_object_or_404(User, id=serializer.validated_data["user_id"], is_active=True)

        if other.id == request.user.id:
            return Response({"detail": "Cannot create self conversation."}, status=status.HTTP_400_BAD_REQUEST)

        low, high = Friendship.canonical_pair(request.user.id, other.id)
        if not Friendship.objects.filter(user_low_id=low, user_high_id=high).exists():
            return Response({"detail": "Friendship required before chat."}, status=status.HTTP_403_FORBIDDEN)

        existing = (
            Conversation.objects.filter(type=Conversation.TYPE_PRIVATE, members__user=request.user)
            .filter(members__user=other)
            .prefetch_related("members")
            .distinct()
        )
        for conv in existing:
            if conv.members.count() == 2:
                return Response(ConversationSerializer(conv, context={"request": request}).data, status=status.HTTP_200_OK)

        with transaction.atomic():
            conv = Conversation.objects.create(type=Conversation.TYPE_PRIVATE, created_by=request.user)
            ConversationMember.objects.create(conversation=conv, user=request.user)
            ConversationMember.objects.create(conversation=conv, user=other)

        return Response(ConversationSerializer(conv, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        conv = get_object_or_404(Conversation.objects.prefetch_related("members__user"), pk=pk)
        if not conv.members.filter(user=request.user).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ConversationDetailSerializer(conv, context={"request": request}).data)
