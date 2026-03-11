from django.urls import path

from .views import MarkReadView, MessageHistoryView

urlpatterns = [
    path("<uuid:pk>/messages/", MessageHistoryView.as_view(), name="conversations-message-history"),
    path("<uuid:pk>/messages/<uuid:msg_id>/read/", MarkReadView.as_view(), name="conversations-mark-read"),
]
