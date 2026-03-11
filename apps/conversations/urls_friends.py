from django.urls import path

from .views import (
    AcceptFriendRequestView,
    CancelFriendRequestView,
    FriendshipListView,
    FriendRequestCreateView,
    IncomingFriendRequestsView,
    OutgoingFriendRequestsView,
    RejectFriendRequestView,
)

urlpatterns = [
    path("requests/", FriendRequestCreateView.as_view(), name="friends-request-create"),
    path("requests/incoming/", IncomingFriendRequestsView.as_view(), name="friends-request-incoming"),
    path("requests/outgoing/", OutgoingFriendRequestsView.as_view(), name="friends-request-outgoing"),
    path("requests/<uuid:pk>/accept/", AcceptFriendRequestView.as_view(), name="friends-request-accept"),
    path("requests/<uuid:pk>/reject/", RejectFriendRequestView.as_view(), name="friends-request-reject"),
    path("requests/<uuid:pk>/cancel/", CancelFriendRequestView.as_view(), name="friends-request-cancel"),
    path("", FriendshipListView.as_view(), name="friends-list"),
]
