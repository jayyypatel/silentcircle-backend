from django.urls import path

from .views import ConversationDetailView, ConversationListCreateView

urlpatterns = [
    path("", ConversationListCreateView.as_view(), name="conversations-list-create"),
    path("<uuid:pk>/", ConversationDetailView.as_view(), name="conversations-detail"),
]
