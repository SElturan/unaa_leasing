from decimal import Decimal
from datetime import date, datetime, timedelta

from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.utils.timezone import now
from django.db.models import Prefetch, OuterRef, Subquery

from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import filters, generics, status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.generics import (
    GenericAPIView, ListAPIView, UpdateAPIView, mixins,
    RetrieveAPIView, CreateAPIView,
)

from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import (
    Client, ClientCar, RepaymentSchedule, InsuranceClient,
    AdCars, CalculateInfo, ImagesClientCar, ImagesAdCars, ContactClient,
    Send_Message, LocationClient, Notification, WaybillExtraName,
    AppVersion, AppAndroidVersion,
)
from .serializers import (
    ClientSerializers, ClientCarSerializers, ClientCarDetailSerializers,
    RepaymentDetailScheduleSerializer, InsuranceClientSerializers,
    AdCarsSerializers, AdCarsDetailSerializers, ContactClientSerializers,
    LocationClientSerializers, LocationClientDetailSerializers,
    SendMessageSerializer, NotificationSerializer,
    LeasingCalcInputSerializer, LeasingResultSerializer,
    WaybillExtraNameSerializer, AppVersionSerializer, AppAndroidVersionSerializer,
)
from .calculations import calculate_leasing


# ==========================================================
# КЛИЕНТ — профиль и общая инфа о клиенте (для мобилки)
# ==========================================================

@extend_schema_view(
    get=extend_schema(
        summary="Мои данные + мои машины",
        description="Возвращает клиента, привязанного к текущему пользователю, и список всех его машин. "
                    "Если у пользователя вообще нет привязанного клиента — 404.",
        tags=["Клиент"],
    )
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
            'cars': car_data,
        })


@extend_schema_view(
    get=extend_schema(
        summary="Карточка клиента по id (для админки)",
        description="Полная информация по клиенту: машины (детально), страховки по всем его машинам "
                    "и последняя известная геолокация.",
        tags=["Клиент"],
    )
)
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
            'cars': ClientCarDetailSerializers(cars, many=True).data,
            'insurance': InsuranceClientSerializers(InsuranceClient.objects.filter(client__in=cars), many=True).data,
            'location': LocationClientDetailSerializers(latest_location).data if latest_location else None,
        })


@extend_schema_view(
    get=extend_schema(
        summary="Детальная карточка машины клиента",
        description="Полная информация по одной машине: марка, модель, VIN, суммы, просрочки и т.д.",
        tags=["Клиент"],
    )
)
class ClientCarDetailAPIView(RetrieveAPIView):
    queryset = ClientCar.objects.all()
    serializer_class = ClientCarDetailSerializers
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'


# ==========================================================
# ГРАФИК ПЛАТЕЖЕЙ ПО МАШИНЕ
# ==========================================================

@extend_schema_view(
    get=extend_schema(
        summary="График платежей по конкретной машине",
        description="Отдаёт полный график погашения по машине: краткую сводку (сумма лизинга, дата "
                    "следующего платежа, дата полного погашения) и построчный график с отметками "
                    "какой платёж следующий (is_next) и какие просрочены (overdue).",
        tags=["График платежей"],
    )
)
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
                "remaining_after": float(remaining - rep.total_payment) if rep.is_paid != 'is_paid' else float(remaining),
                "is_paid": rep.is_paid,
                "is_next": rep.id == next_payment_id,
            }
            if rep.is_paid != 'is_paid' and rep.paid_date <= today:
                item["overdue"] = True

            repayment_list.append(item)

            if rep.is_paid != 'is_paid':
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
            "repayment_schedule": repayment_list,
        }, status=status.HTTP_200_OK)


# ==========================================================
# ГЛАВНЫЙ ЭКРАН — карточка "ближайший/просроченный платёж"
# ==========================================================

class HomeNextPaymentAPIView(APIView):
    """
    Для главного экрана приложения: по каждой машине клиента отдельно
    показываем либо просрочку, либо ближайший ещё не оплаченный платёж.
    Если платежей несколько машин — возвращается массив, по одному
    элементу на каждую машину.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Ближайший/просроченный платёж по каждой машине клиента",
        description="Для каждой машины клиента отдельно возвращает: просрочку (если есть) "
                    "или ближайший ещё не оплаченный платёж, без ограничения по сроку. "
                    "Если у клиента несколько машин — в ответе будет несколько элементов массива.",
        tags=["Главный экран"],
    )
    def get(self, request, *args, **kwargs):
        client = getattr(request.user, "client", None)
        if not client:
            return Response({"detail": "У пользователя нет привязанного клиента"}, status=404)

        today = date.today()
        cars = ClientCar.objects.filter(client=client).order_by("id")

        results = []
        for car in cars:
            payment_data = self._get_payment_for_car(car, today)
            if payment_data:
                results.append(payment_data)

        return Response(results)

    def _get_payment_for_car(self, car, today):
        """Возвращает просрочку (если есть) или ближайший будущий платёж по одной машине."""
        base_qs = RepaymentSchedule.objects.filter(
            car_client=car
        ).exclude(is_paid="is_paid")

        # просрочка — самая свежая (ближайшая к сегодня)
        overdue = base_qs.filter(paid_date__lt=today).order_by("-paid_date").first()
        if overdue:
            return self._build_payload(car, overdue, today, is_overdue=True)

        # иначе — ближайший будущий платёж, без ограничения по дням
        upcoming = base_qs.filter(paid_date__gte=today).order_by("paid_date").first()
        if upcoming:
            return self._build_payload(car, upcoming, today, is_overdue=False)

        return None  # у этой машины вообще нет неоплаченных платежей

    def _build_payload(self, car, payment, today, is_overdue):
        """Собирает один элемент ответа: сумма, дата, машина + days_left/days_overdue."""
        data = {
            "type": "overdue" if is_overdue else "upcoming",
            "paid_date": payment.paid_date,
            "amount": float(payment.total_payment),
            "car": {
                "id": car.id,
                "car_name": car.car_name,
                "car_model": car.car_model,
                "car_number": car.car_number,
            },
        }
        if is_overdue:
            data["days_overdue"] = (today - payment.paid_date).days
        else:
            data["days_left"] = (payment.paid_date - today).days
        return data


# ==========================================================
# ОБЪЯВЛЕНИЯ О ПРОДАЖЕ АВТО + КРЕДИТНЫЙ КАЛЬКУЛЯТОР ПО НИМ
# ==========================================================

@extend_schema_view(
    get=extend_schema(
        summary="Список объявлений о продаже машин",
        description="Только активные и ещё не проданные объявления (фильтруется на уровне сериализатора/шаблона).",
        tags=["Объявления"],
    )
)
class AdCarsListAPIView(ListAPIView):
    queryset = AdCars.objects.all()
    serializer_class = AdCarsSerializers


@extend_schema_view(
    get=extend_schema(
        summary="Детальная карточка объявления",
        tags=["Объявления"],
    )
)
class AdCarsRetrieveAPIView(RetrieveAPIView):
    queryset = AdCars.objects.all()
    serializer_class = AdCarsDetailSerializers
    lookup_field = 'id'


class CreditCalculatorListAPIView(ListAPIView):
    """
    Считает примерный ежемесячный платёж по лизингу для каждой машины
    из объявлений, с учётом первоначального взноса, GPS/страховки/оформления.
    """
    serializer_class = AdCarsSerializers  # можно вернуть сериализованные данные
    queryset = AdCars.objects.filter(is_active=True, is_sold=False)

    @extend_schema(
        summary="Расчёт ежемесячного платежа по всем машинам объявлений",
        description="Принимает query-параметр down_payment (первоначальный взнос) и считает "
                    "ежемесячный платёж по всем активным непроданным объявлениям сразу.",
        tags=["Объявления"],
    )
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


# ==========================================================
# КОНТАКТЫ КЛИЕНТА
# ==========================================================

class ContactClientCreateAPIView(CreateAPIView):
    """
    Массовое добавление контактов клиента. Ожидает список объектов
    (не один объект!), сам отсекает дубликаты — как внутри одного
    запроса, так и уже существующие в базе для этого клиента.
    """
    serializer_class = ContactClientSerializers
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Массовое добавление контактов клиента",
        description="Тело запроса — список контактов [{name, phone}, ...]. Уже существующие "
                    "телефоны у этого клиента и дубли внутри самого запроса пропускаются, "
                    "без ошибки — в ответе видно сколько реально добавлено и что пропущено.",
        tags=["Контакты"],
    )
    def create(self, request, *args, **kwargs):
        raw_data = request.data

        if not isinstance(raw_data, list):
            return Response({"error": "Ожидается список контактов"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=raw_data, many=True)
        serializer.is_valid(raise_exception=True)

        client = request.user.client

        # телефоны из запроса
        phones = [item["phone"] for item in serializer.validated_data]

        # телефоны, которые уже есть в базе
        existing_phones = set(
            ContactClient.objects.filter(client=client, phone__in=phones)
            .values_list("phone", flat=True)
        )

        # убираем дубликаты внутри одного запроса
        unique_data = {item["phone"]: item for item in serializer.validated_data}.values()

        # фильтруем только новые
        new_contacts = [item for item in unique_data if item["phone"] not in existing_phones]

        # создаём новые
        ContactClient.objects.bulk_create(
            [ContactClient(client=client, **data) for data in new_contacts],
            ignore_conflicts=True,
        )

        return Response({
            "status": "created",
            "added": len(new_contacts),
            "skipped": len(phones) - len(new_contacts),
            "skipped_phones": list(existing_phones),
        }, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        summary="Контакты клиента по client_id (для админки)",
        tags=["Контакты"],
    )
)
class ContactClientListIDAPIView(ListAPIView):
    serializer_class = ContactClientSerializers
    lookup_field = 'client_id'

    def get_queryset(self):
        return ContactClient.objects.filter(client_id=self.kwargs['client_id'])


# ==========================================================
# ГЕОЛОКАЦИЯ КЛИЕНТА
# ==========================================================

class LocationClientCreateAPIView(CreateAPIView):
    """Клиент периодически шлёт свои координаты — просто пишем новую запись."""
    serializer_class = LocationClientSerializers

    @extend_schema(
        summary="Отправить текущую геолокацию клиента",
        tags=["Геолокация"],
    )
    def perform_create(self, serializer):
        serializer.save(client=self.request.user.client)


@extend_schema_view(
    get=extend_schema(
        summary="Последняя геолокация по каждому клиенту (для админки/карты)",
        description="Для каждого клиента берётся только самая свежая точка (по id), "
                    "не вся история перемещений.",
        tags=["Геолокация"],
    )
)
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


@extend_schema_view(
    get=extend_schema(
        summary="Карточка клиента через его геолокацию (для админки/карты)",
        description="Точка входа — конкретная запись геолокации, но в ответе — весь клиент "
                    "целиком: его машины и последняя (не обязательно эта же) геолокация.",
        tags=["Геолокация"],
    )
)
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
            'location': LocationClientDetailSerializers(latest_location).data if latest_location else None,
        })


# ==========================================================
# СТРАХОВКИ (ОСАГО / КАСКО)
# ==========================================================

@extend_schema_view(
    get=extend_schema(
        summary="Мои страховки",
        description="Все страховки по всем машинам текущего клиента (ОСАГО и КАСКО вперемешку).",
        tags=["Страховки"],
    )
)
class InsuranceClientListAPIView(ListAPIView):
    serializer_class = InsuranceClientSerializers
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = InsuranceClient.objects.filter(client=user.client.id)
        if queryset:
            return queryset
        return InsuranceClient.objects.none()


@extend_schema_view(
    get=extend_schema(
        summary="Страховки по client_id (для админки)",
        tags=["Страховки"],
    )
)
class InsuranceClientListByClientIdAPIView(ListAPIView):
    serializer_class = InsuranceClientSerializers
    lookup_field = 'client_id'

    def get_queryset(self):
        return InsuranceClient.objects.filter(client_id=self.kwargs['client_id'])


# ==========================================================
# РАССЫЛКИ И УВЕДОМЛЕНИЯ
# ==========================================================

@extend_schema_view(
    get=extend_schema(
        summary="Сообщения рассылки за последние 3 дня",
        description="Общая лента объявлений/рассылок компании (не персональные уведомления).",
        tags=["Уведомления"],
    )
)
class LastThreeDaysMessagesView(ListAPIView):
    serializer_class = SendMessageSerializer

    def get_queryset(self):
        three_days_ago = timezone.now() - timedelta(days=3)
        return Send_Message.objects.filter(created_at__gte=three_days_ago).order_by('-created_at')


@extend_schema_view(
    get=extend_schema(
        summary="Мои персональные уведомления",
        description="История пуш-уведомлений конкретно для текущего пользователя "
                    "(напоминания о платежах, страховках и т.д.), сначала новые.",
        tags=["Уведомления"],
    )
)
class NotificationListView(ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Notification.objects.filter(user=user).order_by('-created_at')


# ==========================================================
# АДМИНСКИЕ ОТЧЁТЫ ПО ВСЕМ КЛИЕНТАМ
# ==========================================================

@extend_schema_view(
    get=extend_schema(
        summary="Список всех клиентов (для админки)",
        description="Поддерживает фильтрацию по fio и phone через query-параметры.",
        tags=["Отчёты"],
    )
)
class ClientAllListAPIView(ListAPIView):
    queryset = Client.objects.all()
    serializer_class = ClientSerializers
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['fio', 'phone']


class ClientReportListView(ListAPIView):
    """
    Полный отчёт по всем клиентам и всем их машинам сразу, с суммами,
    просрочками и датами страховок ОСАГО/КАСКО — то, что обычно
    выгружают в Excel для бухгалтерии/менеджеров.
    """

    @extend_schema(
        summary="Общий отчёт по всем клиентам и их машинам",
        description="Плоский список: одна строка = одна машина одного клиента, со всеми "
                    "суммами (долг, просрочка, остаток) и датами ОСАГО/КАСКО.",
        tags=["Отчёты"],
    )
    def list(self, request, *args, **kwargs):
        clients = Client.objects.prefetch_related(
            Prefetch('client_car__insurances')
        )

        report = []
        for client in clients:
            for car in client.client_car.all():
                osago = next((ins for ins in car.insurances.all() if ins.insurance_company == 'OSAGO'), None)
                kasko = next((ins for ins in car.insurances.all() if ins.insurance_company == 'KASKO'), None)

                report.append({
                    "client_fio": client.fio,
                    "client_phone": client.phone,
                    "client_email": client.email,
                    "client_residence": client.residence,
                    "client_registration_address": client.registration_address,

                    "car_number": car.car_number,
                    "car_name": car.car_name,
                    "car_model": car.car_model,
                    "car_year": car.car_year,
                    "car_total_cost": car.total_amount,
                    "car_remaining_amount": car.remaining_amount,
                    "car_paid_amount": car.paid_amount,
                    "car_due_days_principal": car.due_days_principal,
                    "car_due_days_interest": car.due_days_interest,
                    "car_due_amount_principal": car.due_amount_principal,
                    "car_due_amount_interest": car.due_amount_interest,
                    "car_principal_balance": car.principal_balance,
                    "car_interest_balance": car.interest_balance,
                    "car_penalty_balance": car.penalty_balance,
                    "OSAGO_start": osago.start_date if osago else None,
                    "KASKO_start": kasko.start_date if kasko else None,
                    "OSAGO_end": osago.end_date if osago else None,
                    "KASKO_end": kasko.end_date if kasko else None,
                })

        return Response(report, status=status.HTTP_200_OK)


class ClientReportOneView(RetrieveAPIView):
    """То же самое, что ClientReportListView, но только по одному клиенту."""
    queryset = Client.objects.all()
    serializer_class = ClientSerializers
    lookup_field = 'id'

    @extend_schema(
        summary="Отчёт по одному клиенту",
        description="Все машины одного клиента с суммами, просрочками и датами ОСАГО/КАСКО.",
        tags=["Отчёты"],
    )
    def retrieve(self, request, *args, **kwargs):
        client = self.get_object()
        cars = client.client_car.all()

        report = []
        for car in cars:
            osago = next((ins for ins in car.insurances.all() if ins.insurance_company == 'OSAGO'), None)
            kasko = next((ins for ins in car.insurances.all() if ins.insurance_company == 'KASKO'), None)

            report.append({
                "car_number": car.car_number,
                "car_name": car.car_name,
                "car_model": car.car_model,
                "car_year": car.car_year,
                "car_total_cost": car.total_amount,
                "car_remaining_amount": car.remaining_amount,
                "car_paid_amount": car.paid_amount,
                "OSAGO_start": osago.start_date if osago else None,
                "KASKO_start": kasko.start_date if kasko else None,
                "OSAGO_end": osago.end_date if osago else None,
                "KASKO_end": kasko.end_date if kasko else None,
            })

        return Response({
            "client_fio": client.fio,
            "report": report,
        }, status=status.HTTP_200_OK)


# ==========================================================
# ЛИЗИНГОВЫЙ КАЛЬКУЛЯТОР
# ==========================================================

class LeasingCalcAPIView(APIView):
    """Считает итоговую стоимость лизинга и ежемесячный платёж по вводным клиента."""

    @extend_schema(
        request=LeasingCalcInputSerializer,
        responses=LeasingResultSerializer,
        summary="Лизинговый калькулятор",
        description="Возвращает сумму всех выплат, ежемесячный платёж и детализацию расходов.",
        tags=["Лизинг"],
    )
    def post(self, request, *args, **kwargs):
        input_serializer = LeasingCalcInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        result = calculate_leasing(
            car_price=Decimal(data['car_price']),
            down_payment=Decimal(data['down_payment']),
            leasing_term_months=int(data['leasing_term_months']),
        )
        comment = {
            "car_total_cost": "Итоговая сумма, которую клиент заплатит за автомобиль со всеми расходами за весь срок.",
            "monthly_payment": "Ежемесячный платёж по договору лизинга.",
            "initial_payment_total": "Сумма, которую нужно внести в самом начале (первоначальный взнос, комиссия, ОСАГО).",
            "details": {
                "down_payment": "Первоначальный взнос (выбран клиентом).",
                "commission": "Комиссия за рассмотрение (2% от суммы лизинга).",
                "osago": "ОСАГО — обязательное страхование, фиксированная сумма.",
            },
        }
        return Response({
            "result": result,
            "description": comment,
        }, status=status.HTTP_200_OK)


# ==========================================================
# ПУТЕВОЙ ЛИСТ
# ==========================================================

class WaybillAPIView(APIView):
    """
    Путевой лист выдаётся, пока клиент платит вовремя. Если платёж
    просрочен — даём ещё GRACE_PERIOD_DAYS дней "на подумать", и только
    после этого срока путевой лист перестаёт выдаваться (402).
    """
    permission_classes = [IsAuthenticated]
    GRACE_PERIOD_DAYS = 7

    @extend_schema(
        summary="Получить путевой лист по машине",
        description="Проверяет текущий платёж по машине: если оплачен — лист действует до "
                    "следующего платежа; если не оплачен — даётся льготный период в 7 дней "
                    "с даты платежа, после чего выдача блокируется (статус 402).",
        tags=["Путевой лист"],
    )
    def get(self, request, id=None):
        if not id:
            raise ValidationError({"error": "Не передан id машины"})

        try:
            car = ClientCar.objects.get(id=id, client=request.user.client)
        except ClientCar.DoesNotExist:
            raise ValidationError({"error": "Машина не найдена или не принадлежит клиенту"})

        today = now().date()
        payments = car.repayment_schedules.order_by("paid_date")

        current_payment = None  # последний платёж с датой <= сегодня
        next_payment = None     # первый платёж с датой > сегодня

        for payment in payments:
            if payment.paid_date <= today:
                current_payment = payment
            else:
                next_payment = payment
                break

        if not current_payment and not next_payment:
            raise ValidationError({"error": "График платежей не найден, путевой лист недоступен"})

        # Первый платёж ещё не наступил (машина только выдана)
        if not current_payment:
            return self._issue_waybill(car, start_date=today, end_date=next_payment.paid_date)

        # Текущий платёж оплачен — лист действует до следующего платежа
        if current_payment.is_paid == "is_paid":
            end_date = next_payment.paid_date if next_payment else current_payment.paid_date
            return self._issue_waybill(car, start_date=current_payment.paid_date, end_date=end_date)

        # Не оплачен — грейс-период 7 дней от даты платежа
        days_overdue = (today - current_payment.paid_date).days
        grace_end = current_payment.paid_date + timedelta(days=self.GRACE_PERIOD_DAYS)

        if today <= grace_end:
            return self._issue_waybill(
                car,
                start_date=current_payment.paid_date,
                end_date=grace_end,
                extra={"grace_period": True, "days_overdue": days_overdue},
            )

        # Грейс-период истёк
        return Response({
            "status": "unpaid",
            "message": f"Просрочка платежа с {current_payment.paid_date}. "
                       f"Льготный период 7 дней истёк {grace_end}.",
            "next_payment_date": current_payment.paid_date,
            "days_overdue": days_overdue,
        }, status=402)

    def _issue_waybill(self, car, start_date, end_date, extra=None):
        """Собирает тело путевого листа: ФИО (+ доп. имена), машина, период действия."""
        extra_names = car.extra_waybill_names.all()

        if extra_names.exists():
            fio_for_waybill = f"{car.client.fio}\n" + "\n".join([e.fio for e in extra_names])
        else:
            fio_for_waybill = car.client.fio

        data = {
            "fio": fio_for_waybill,
            "car_name": car.car_model,
            "car_number": car.car_number,
            "waybill_valid_from": start_date,
            "waybill_valid_to": end_date,
            "status": "ok",
        }
        if extra:
            data.update(extra)
        return Response(data)


class AddExtraWaybillNameView(RetrieveAPIView):
    """Добавить доп. ФИО в путевой лист машины (максимум 2 дополнительных)."""
    queryset = ClientCar.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = WaybillExtraNameSerializer  # формально не используется для POST

    @extend_schema(
        summary="Добавить доп. ФИО для путевого листа",
        request=WaybillExtraNameSerializer,
        responses=WaybillExtraNameSerializer,
        description="Лимит — максимум 2 дополнительных ФИО на одну машину. Добавлять может "
                    "только владелец машины.",
        tags=["Путевой лист"],
    )
    def post(self, request, *args, **kwargs):
        client_car = self.get_object()  # Берём машину по URL /<id>/

        if client_car.client != request.user.client:
            return Response({"error": "Вы не можете добавлять имена к чужому авто."},
                             status=status.HTTP_403_FORBIDDEN)

        fio = request.data.get("fio")

        if not fio:
            return Response(
                {"error": "Поле 'fio' обязательно."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Лимит 2
        if client_car.extra_waybill_names.count() >= 2:
            return Response(
                {"error": "Можно добавить максимум 2 дополнительных имени."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Создаём запись
        extra = WaybillExtraName.objects.create(
            client_car=client_car,
            fio=fio,
        )

        return Response(
            WaybillExtraNameSerializer(extra).data,
            status=status.HTTP_201_CREATED,
        )


class DeleteExtraWaybillNameView(RetrieveAPIView):
    """Удалить ранее добавленное доп. ФИО из путевого листа."""
    queryset = WaybillExtraName.objects.all()
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Удалить доп. ФИО из путевого листа",
        description="Удалять может только владелец машины, к которой привязано это имя.",
        tags=["Путевой лист"],
    )
    def delete(self, request, *args, **kwargs):
        extra_name = self.get_object()

        if extra_name.client_car.client != request.user.client:
            return Response({"error": "Вы не можете удалять имена к чужому авто."},
                             status=status.HTTP_403_FORBIDDEN)

        extra_name.delete()
        return Response({"status": "deleted"}, status=status.HTTP_204_NO_CONTENT)


# ==========================================================
# ВЕРСИИ ПРИЛОЖЕНИЯ (для форс-апдейта)
# ==========================================================

@extend_schema_view(
    get=extend_schema(
        summary="Текущая версия приложения (iOS)",
        description="Возвращает последнюю добавленную версию — используется для проверки "
                    "обязательного обновления на клиенте.",
        tags=["Версии приложения"],
    )
)
class AppVersionRetrieveView(generics.RetrieveAPIView):
    """GET /api/app-version/ → возвращает текущую версию приложения (iOS)."""
    queryset = AppVersion.objects.all()
    serializer_class = AppVersionSerializer

    def get_object(self):
        # Берём последнюю добавленную версию
        return self.queryset.latest("id")


@extend_schema_view(
    get=extend_schema(
        summary="Текущая версия приложения (Android)",
        description="Возвращает последнюю добавленную версию — используется для проверки "
                    "обязательного обновления на клиенте.",
        tags=["Версии приложения"],
    )
)
class AppAndroidVersionRetrieveView(generics.RetrieveAPIView):
    """GET /api/app-android-version/ → возвращает текущую версию приложения (Android)."""
    queryset = AppAndroidVersion.objects.all()
    serializer_class = AppAndroidVersionSerializer

    def get_object(self):
        # Берём последнюю добавленную версию
        return self.queryset.latest("id")