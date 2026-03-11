from django.urls import path

from .views import CurrentUserView, UserPublicKeysView, UserSearchView

urlpatterns = [
    path("me/", CurrentUserView.as_view(), name="users-me"),
    path("search/", UserSearchView.as_view(), name="users-search"),
    path("<uuid:user_id>/public-keys/", UserPublicKeysView.as_view(), name="users-public-keys"),
]
