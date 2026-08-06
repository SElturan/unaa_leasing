# payments/urls.py
from django.urls import path
from .views import (
    CreateRepaymentPaymentView, CreateOsagoPaymentView,
    PaymentStatusView, BePayWebhookView,
    
)
 
urlpatterns = [
    path("payments/create/", CreateRepaymentPaymentView.as_view(), name="payment-create"),
    path("payments/osago/create/", CreateOsagoPaymentView.as_view(), name="osago-payment-create"),
    path("payments/<uuid:user_guid>/status/", PaymentStatusView.as_view(), name="payment-status"),
    path("payments/webhook/bepay/", BePayWebhookView.as_view(), name="bepay-webhook"),
    path("payments/osago/create/", CreateOsagoPaymentView.as_view(), name="osago-payment-create"),
]