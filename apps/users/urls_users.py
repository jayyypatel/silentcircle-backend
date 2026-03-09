from django.urls import path

from .views import CurrentUserView, UserSearchView

urlpatterns = [
    path("me/", CurrentUserView.as_view(), name="users-me"),
    path("search/", UserSearchView.as_view(), name="users-search"),
]
