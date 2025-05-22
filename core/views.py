from django.shortcuts import render
from datetime import date, datetime, timedelta
from django.utils import timezone
from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from decimal import Decimal
from rest_framework import filters, generics, status, viewsets
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from rest_framework.generics import (GenericAPIView, ListAPIView,
                                     UpdateAPIView, mixins, RetrieveAPIView, CreateAPIView)
from django.db.models import OuterRef, Subquery

from .models import (
    Client, RepaymentSchedule, InsuranceClient,
    AdCars, CalculateInfo, ImagesClientCar, ImagesAdCars, ClientCar, ContactClient, Send_Message, LocationClient
)

from .serializers import (
    ClientSerializers, ClientCarSerializers, ClientCarDetailSerializers, RepaymentDetailScheduleSerializer, InsuranceClientSerializers, AdCarsSerializers, AdCarsDetailSerializers, 
    ContactClientSerializers, LocationClientSerializers, SendMessageSerializer, LocationClientDetailSerializers
)

class ClientInfoListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ClientSerializers  # нужно указать хоть один сериализатор

    def list(self, request, *args, **kwargs):
        user = request.user

        if not hasattr(user, 'client') or not user.client:
            return Response({'detail': 'У пользователя нет привязанного клиента'}, status=404)

        client = user.client
        cars = ClientCar.objects.filter(client=client)

        client_data = ClientSerializers(client).data
        car_data = ClientCarSerializers(cars, many=True).data

        return Response({
            'client': client_data,
            'cars': car_data
        })

class ClientInfoRetrieveAPIView(RetrieveAPIView):
    queryset = Client.objects.all()
    serializer_class = ClientSerializers
    lookup_field = 'id'
    
    def retrieve(self, request, *args, **kwargs):
        client = self.get_object()
        cars = ClientCar.objects.filter(client=client)

        # получаем последнюю геолокацию
        latest_location = LocationClient.objects.filter(client=client).order_by('-id').first()

        return Response({
            'client': ClientSerializers(client).data,
            'cars': ClientCarSerializers(cars, many=True).data,
            'location': LocationClientDetailSerializers(latest_location).data if latest_location else None
        })

    
class ClientCarDetailAPIView(RetrieveAPIView):
    queryset = ClientCar.objects.all()
    serializer_class = ClientCarDetailSerializers
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

class CarPaymentInfoRetrieveView(RetrieveAPIView):
    queryset = ClientCar.objects.all()
    serializer_class = ClientCarDetailSerializers
    lookup_field = 'id'  # Убедись, что в urls.py указано <int:id>

    def retrieve(self, request, *args, **kwargs):
        car = self.get_object()
        today = date.today()

        # Все платежи по машине
        repayments = RepaymentSchedule.objects.filter(car_client=car).order_by('paid_date')

        # Следующее ожидаемое погашение
        next_payment = repayments.filter(is_paid=False, paid_date__gte=today).first()

        # Последняя дата погашения
        last_payment = repayments.last()

        # Остаток и график
        remaining = car.remaining_amount or car.total_amount  # Decimal
        repayment_list = []
        next_payment_id = next_payment.id if next_payment else None

        for rep in repayments:
            item = {
                "id": rep.id,
                "date": rep.paid_date,
                "main_debt": float(rep.main_debt),
                "interest": float(rep.interest),
                "total_payment": float(rep.total_payment),
                "remaining_after": float(remaining - rep.total_payment) if not rep.is_paid else float(remaining),
                "is_paid": rep.is_paid,
                "is_next": rep.id == next_payment_id
            }
            if not rep.is_paid and rep.paid_date <= today:
                item["overdue"] = True

            repayment_list.append(item)

            if not rep.is_paid:
                remaining -= rep.total_payment  # всё в Decimal

        # Краткая информация
        short_info = {
            "car_name": f"{car.car_name} {car.car_model}",
            "total_lease_amount": float(car.total_amount),
            "next_payment_date": next_payment.paid_date if next_payment else None,
            "next_payment_amount": float(next_payment.total_payment) if next_payment else None,
            "fully_repaid_date": last_payment.paid_date if last_payment else None,
        }

        return Response({
            "short_info": short_info,
            "repayment_schedule": repayment_list
        }, status=status.HTTP_200_OK)

    
class AdCarsListAPIView(ListAPIView):
    queryset = AdCars.objects.all()
    serializer_class = AdCarsSerializers

class AdCarsRetrieveAPIView(RetrieveAPIView):
    queryset = AdCars.objects.all()
    serializer_class = AdCarsDetailSerializers
    lookup_field = 'id'

class CreditCalculatorListAPIView(ListAPIView):
    serializer_class = AdCarsSerializers  # можно вернуть сериализованные данные
    queryset = AdCars.objects.filter(is_active=True, is_sold=False)

    def list(self, request, *args, **kwargs):
        down_payment = Decimal(request.GET.get('down_payment', 0))

        calc_info = CalculateInfo.objects.last()
        if not calc_info:
            return Response({"error": "Нет данных для расчета"}, status=status.HTTP_400_BAD_REQUEST)

        rate = calc_info.interest_rate / Decimal(100) / 12
        months = calc_info.leasing_term

        cars = self.get_queryset()
        results = []

        for car in cars:
            car_price = car.price
            total_down = down_payment + calc_info.gps_cost + calc_info.insurance_cost + calc_info.decor_cost
            credit_amount = car_price - total_down

            if credit_amount <= 0:
                continue

            if rate == 0:
                monthly_payment = credit_amount / months
            else:
                monthly_payment = credit_amount * rate * ((1 + rate) ** months) / (((1 + rate) ** months) - 1)

            results.append({
                "car_id": car.id,
                "car_name": car.car_name,
                "car_model": car.car_model,
                "car_price": float(car_price),
                "down_payment": float(total_down),
                "credit_amount": float(credit_amount),
                "monthly_payment": round(float(monthly_payment), 2),
                "months": months,
                "interest_rate": float(calc_info.interest_rate),
            })

        return Response(results)
    
class ContactClientCreateAPIView(CreateAPIView):
    serializer_class = ContactClientSerializers
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        raw_data = request.data

        if not isinstance(raw_data, list):
            return Response({"error": "Ожидается список контактов"}, status=status.HTTP_400_BAD_REQUEST)

        phones = [item.get("phone") for item in raw_data if "phone" in item]
        existing_phones = set(
            ContactClient.objects.filter(phone__in=phones).values_list("phone", flat=True)
        )

        new_data = [item for item in raw_data if item.get("phone") not in existing_phones]
        skipped_data = [item for item in raw_data if item.get("phone") in existing_phones]

        serializer = self.get_serializer(data=new_data, many=True)
        serializer.is_valid(raise_exception=True)

        client = request.user.client
        contacts = [
            ContactClient(client=client, **contact)
            for contact in serializer.validated_data
        ]
        ContactClient.objects.bulk_create(contacts)

        return Response({
            "status": "created",
            "added": len(contacts),
            "skipped": len(skipped_data),
            "skipped_contacts": skipped_data,
        }, status=status.HTTP_201_CREATED)
    
class ContactClientListIDAPIView(ListAPIView):
    serializer_class = ContactClientSerializers
    lookup_field = 'client_id'

    def get_queryset(self):
        return ContactClient.objects.filter(client_id=self.kwargs['client_id'])
    
class LocationClientCreateAPIView(CreateAPIView):
    serializer_class = LocationClientSerializers

    def perform_create(self, serializer):
        serializer.save(client=self.request.user.client)

class LocationClientListAPIView(ListAPIView):
    serializer_class = LocationClientSerializers

    def get_queryset(self):
        # Подзапрос: получить последнюю локацию по каждому клиенту
        latest_location_subquery = LocationClient.objects.filter(
            client=OuterRef('client')
        ).order_by('-id')  # или '-created_at' если есть

        return LocationClient.objects.filter(
            id__in=LocationClient.objects.filter(
                id__in=Subquery(
                    LocationClient.objects.filter(
                        client=OuterRef('client')
                    ).order_by('-id').values('id')[:1]
                )
            )
        ).distinct('client')

class LocationClientRetrieveAPIView(RetrieveAPIView):
    queryset = LocationClient.objects.all()
    serializer_class = LocationClientDetailSerializers
    lookup_field = 'id'

    def retrieve(self, request, *args, **kwargs):
        # получаем клиента через объект локации (только чтобы узнать клиента)
        location = self.get_object()
        client = location.client

        # последняя геолокация клиента
        latest_location = LocationClient.objects.filter(client=client).order_by('-id').first()

        # все машины клиента
        client_cars = ClientCar.objects.filter(client=client)

        return Response({
            'client': ClientSerializers(client).data,
            'cars': ClientCarSerializers(client_cars, many=True).data,
            'location': LocationClientDetailSerializers(latest_location).data if latest_location else None
        })

class InsuranceClientListAPIView(ListAPIView):
    serializer_class = InsuranceClientSerializers
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = InsuranceClient.objects.filter(client=user.client.id)
        if queryset:
            return queryset
        return InsuranceClient.objects.none()

class InsuranceClientListByClientIdAPIView(ListAPIView):
    serializer_class = InsuranceClientSerializers
    lookup_field = 'client_id'

    def get_queryset(self):
        return InsuranceClient.objects.filter(client__client_id=self.kwargs['client_id'])
    
class LastThreeDaysMessagesView(ListAPIView):
    serializer_class = SendMessageSerializer

    def get_queryset(self):
        three_days_ago = timezone.now() - timedelta(days=3)
        return Send_Message.objects.filter(created_at__gte=three_days_ago)
    

class ClientAllListAPIView(ListAPIView):
    queryset = Client.objects.all()
    serializer_class = ClientSerializers
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['fio', 'phone']
