from django.urls import path
from .views import (
    ClientInfoListAPIView, ClientCarDetailAPIView, CarPaymentInfoRetrieveView, AdCarsListAPIView, AdCarsRetrieveAPIView,CreditCalculatorListAPIView,
    ContactClientCreateAPIView, LocationClientCreateAPIView, InsuranceClientListAPIView
)

urlpatterns = [
    path('api/client-info', ClientInfoListAPIView.as_view(), name='client-info'),
    path('api/client-cars-detail/<int:id>/', ClientCarDetailAPIView.as_view(), name='client-car-detail'),
    path('api/repayment-schedule/<int:id>/', CarPaymentInfoRetrieveView.as_view(), name='repayment-schedule'),
    path('api/ad-cars', AdCarsListAPIView.as_view(), name='ad-cars'),
    path('api/ad-cars-detail/<int:id>/', AdCarsRetrieveAPIView.as_view(), name='ad-car-detail'),
    path('api/cars-credit-calc/', CreditCalculatorListAPIView.as_view()),
    path('api/contact-client-create/', ContactClientCreateAPIView.as_view(), name='contact-client'),
    path('api/location-client-create/', LocationClientCreateAPIView.as_view(), name='location-client'),
    path('api/insurance-client-list/', InsuranceClientListAPIView.as_view(), name='insurance-client-list'),


]