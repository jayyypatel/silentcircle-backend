from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.conversations.models import Conversation
from .models import Message, MessageRead
from .serializers import MessageSerializer


class MessageHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer
    pagination_class = None

    def get_queryset(self):
        conversation = get_object_or_404(Conversation, pk=self.kwargs["pk"])
        if not conversation.members.filter(user=self.request.user).exists():
            return Message.objects.none()
        return Message.objects.filter(conversation=conversation, recipient=self.request.user).order_by("-sequence_number")


class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, msg_id):
        conversation = get_object_or_404(Conversation, pk=pk)
        if not conversation.members.filter(user=request.user).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        message = get_object_or_404(Message, pk=msg_id, conversation=conversation, recipient=request.user)
        MessageRead.objects.get_or_create(message=message, user=request.user)

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{message.sender_id}",
            {
                "type": "read.receipt",
                "message_id": str(message.id),
                "read_by": str(request.user.id),
                "read_at": timezone.now().isoformat(),
            },
        )
        return Response({"detail": "ok"}, status=status.HTTP_200_OK)
