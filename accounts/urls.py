from django.urls import path
from .views import UserLoginView

urlpatterns = [
    path('sign-in/', UserLoginView.as_view(), name='signin'),
]