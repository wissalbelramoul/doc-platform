from django.urls import path
from .views import LoginView, CustomTokenRefreshView, LogoutView, VerifyTokenView

urlpatterns = [
    path("login", LoginView.as_view(), name="auth-login"),
    path("refresh", CustomTokenRefreshView.as_view(), name="auth-refresh"),
    path("logout", LogoutView.as_view(), name="auth-logout"),
    path("verify", VerifyTokenView.as_view(), name="auth-verify"),
]