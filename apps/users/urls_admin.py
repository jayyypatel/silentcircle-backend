from django.urls import path

from .views import (
    AdminInviteListCreateView,
    AdminInviteRevokeView,
    AdminUserDeactivateView,
    AdminUserDetailView,
    AdminUserListCreateView,
)

urlpatterns = [
    path("users/", AdminUserListCreateView.as_view(), name="admin-users-list-create"),
    path("users/<uuid:pk>/", AdminUserDetailView.as_view(), name="admin-users-detail"),
    path("users/<uuid:pk>/deactivate/", AdminUserDeactivateView.as_view(), name="admin-users-deactivate"),
    path("invites/", AdminInviteListCreateView.as_view(), name="admin-invites-list-create"),
    path("invites/<uuid:pk>/", AdminInviteRevokeView.as_view(), name="admin-invites-revoke"),
]
