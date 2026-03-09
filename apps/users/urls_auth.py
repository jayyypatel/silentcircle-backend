from django.urls import path

from .views import (
    ChangePasswordView,
    InviteCompleteView,
    InviteValidateView,
    LoginView,
    LogoutView,
    TokenRefreshView,
    WSTicketView,
)

urlpatterns = [
    path("invite/<str:token>/validate/", InviteValidateView.as_view(), name="auth-invite-validate"),
    path("invite/<str:token>/complete/", InviteCompleteView.as_view(), name="auth-invite-complete"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("ws-ticket/", WSTicketView.as_view(), name="auth-ws-ticket"),
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
]
