from django.urls import path
from .views import UserLoginView, UserRegisterView ,CustomTokenRefreshView, ExpoPushTokenView

urlpatterns = [
    path('sign-in/', UserLoginView.as_view(), name='signin'),
    path('sign-up/', UserRegisterView.as_view(), name='signup'),
    path('refresh-token/', CustomTokenRefreshView.as_view(), name='refresh_token'),
    path('expo-push-token/', ExpoPushTokenView.as_view(), name='expo_push_token'),
]