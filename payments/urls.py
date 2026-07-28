# payments/urls.py
from django.urls import path
from .views import CreateRepaymentPaymentView, PaymentStatusView, BePayWebhookView

urlpatterns = [
    path("payments/create/", CreateRepaymentPaymentView.as_view(), name="payment-create"),
    path("payments/<uuid:user_guid>/status/", PaymentStatusView.as_view(), name="payment-status"),
    path("payments/webhook/bepay/", BePayWebhookView.as_view(), name="bepay-webhook"),
]