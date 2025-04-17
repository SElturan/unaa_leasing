from django.urls import path
from .views import UserLoginView, CustomTokenRefreshView

urlpatterns = [
    path('sign-in/', UserLoginView.as_view(), name='signin'),
    path('refresh-token/', CustomTokenRefreshView.as_view(), name='refresh_token'),
]