from django.urls import path
from .views import (
    ClientInfoListAPIView, ClientCarDetailAPIView, CarPaymentInfoRetrieveView, AdCarsListAPIView, AdCarsRetrieveAPIView,CreditCalculatorListAPIView,
    ContactClientCreateAPIView, LocationClientCreateAPIView, InsuranceClientListAPIView, LastThreeDaysMessagesView, 
    ContactClientListIDAPIView, ClientInfoRetrieveAPIView, LocationClientRetrieveAPIView, LocationClientListAPIView, InsuranceClientListByClientIdAPIView
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
    path('api/last-three-days-messages/', LastThreeDaysMessagesView.as_view(), name='last-three-days-messages'),
    path('api/admin/contact-client/<int:client_id>/', ContactClientListIDAPIView.as_view(), name='contact-client-detail'),
    path('api/admin/client-info/<int:id>/', ClientInfoRetrieveAPIView.as_view(), name='client-info-detail'),
    path('api/admin/location-client/', LocationClientListAPIView.as_view(), name='location-client-list'),
    path('api/admin/location-client/<int:id>/', LocationClientRetrieveAPIView.as_view(), name='location-client-detail'),
    path('api/admin/insurance-client/<int:client_id>/', InsuranceClientListByClientIdAPIView.as_view(), name='insurance-client-list-by-client-id'),

]