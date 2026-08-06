
import logging
from datetime import date
 
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
 
from .models import ClientCar, OsagoApplication
from .osago_service import OsagoClient, OsagoError, build_create_payload, confirm_and_save
from .osago_serializers import OsagoCreateSerializer, OsagoApplicationSerializer
 
logger = logging.getLogger(__name__)
 
REFERENCE_NAMES = [
    'country',
    'insurance_territory',
    'transport_type',
    'car_of_use',
    'type_document',
]
 
 
class OsagoReferencesView(APIView):
    """Все справочники одним запросом — для формы."""
    permission_classes = [IsAuthenticated]
 
    @extend_schema(
        summary="Справочники ОСАГО",
        description="Возвращает все списки для выпадающих полей формы: "
                    "country, insurance_territory, transport_type, car_of_use, "
                    "type_document. В форме показываем nameid, отправляем codeid.",
        tags=["ОСАГО"],
    )
    def get(self, request):
        client = OsagoClient()
        result = {}
        for name in REFERENCE_NAMES:
            try:
                result[name] = client.get_reference(name)
            except OsagoError as e:
                logger.warning("ОСАГО: справочник %s недоступен: %s", name, e)
                result[name] = []
        return Response(result)
 
 
class OsagoReferenceView(APIView):
    """Один справочник по имени."""
    permission_classes = [IsAuthenticated]
 
    @extend_schema(summary="Один справочник ОСАГО", tags=["ОСАГО"])
    def get(self, request, name):
        if name not in REFERENCE_NAMES:
            raise ValidationError({"error": f"Неизвестный справочник", "available": REFERENCE_NAMES})
        try:
            return Response(OsagoClient().get_reference(name))
        except OsagoError as e:
            return Response({"detail": e.detail}, status=502)
 
 
class OsagoPrefillView(APIView):
    """Что уже известно о клиенте и машине — для предзаполнения формы."""
    permission_classes = [IsAuthenticated]
 
    @extend_schema(
        summary="Предзаполнение формы ОСАГО",
        description="Данные из нашей базы (пришли из 1С), чтобы клиент "
                    "не вводил их заново. Поля должны остаться редактируемыми.",
        tags=["ОСАГО"],
    )
    def get(self, request, car_id):
        client = getattr(request.user, 'client', None)
        if not client:
            return Response({"detail": "У пользователя нет привязанного клиента"}, status=404)
 
        car = get_object_or_404(ClientCar, id=car_id, client=client)
 
        return Response({
            "fio": client.fio or "",
            "phone": client.phone or "",
            "address_street_house_flat": client.residence or "",
            "car_sp_marka": car.car_model or "",
            "car_sp_model": car.car_model or "",
            "car_year_issue": car.car_year,
            "car_vin": car.car_vin or "",
            "car_license_number": car.car_number or "",
        })
 
 
class OsagoByCarView(APIView):
    """Есть ли действующий полис на эту машину."""
    permission_classes = [IsAuthenticated]
 
    @extend_schema(
        summary="Действующий полис по машине",
        description="Показывает полисы, оформленные через приложение. "
                    "Полисы, купленные напрямую в страховой, здесь не видны — "
                    "у нас нет их guid.",
        tags=["ОСАГО"],
    )
    def get(self, request, car_id):
        client = getattr(request.user, 'client', None)
        if not client:
            return Response({"detail": "У пользователя нет привязанного клиента"}, status=404)
 
        car = get_object_or_404(ClientCar, id=car_id, client=client)
 
        policy = OsagoApplication.objects.filter(
            client_car=car,
            status=OsagoApplication.STATUS_CONFIRMED,
            period_do__gte=date.today(),
        ).exclude(
            policy_status__in=['CANCELED', 'EXPIRED']
        ).order_by('-period_do').first()
 
        if not policy:
            return Response({"has_policy": False, "policy": None})
 
        return Response({
            "has_policy": True,
            "policy": OsagoApplicationSerializer(policy).data,
        })
 
 
class OsagoCreateView(APIView):
    """
    Шаг 1: создать заявку в Сакболе и узнать цену.
    Деньги не списываются, полиса ещё нет.
    """
    permission_classes = [IsAuthenticated]
 
    @extend_schema(
        summary="Создать заявку на ОСАГО (расчёт цены)",
        request=OsagoCreateSerializer,
        responses=OsagoApplicationSerializer,
        description="Отправляет анкету в страховую и возвращает цену полиса "
                    "(premiya_insurance) и покрытие (summa_insurance). "
                    "Далее нужно оплатить премию.",
        tags=["ОСАГО"],
    )
    def post(self, request):
        serializer = OsagoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = serializer.validated_data
 
        client = getattr(request.user, 'client', None)
        if not client:
            return Response({"detail": "У пользователя нет привязанного клиента"}, status=404)
 
        car = get_object_or_404(ClientCar, id=form['car_id'], client=client)
 
        application = OsagoApplication.objects.create(
            client=client,
            client_car=car,
            status=OsagoApplication.STATUS_DRAFT,
            period_ot=form['period_ot'],
            period_do=form['period_do'],
        )
 
        payload = build_create_payload(client, car, form)
        application.request_payload = payload
        application.save(update_fields=['request_payload'])
 
        try:
            result = OsagoClient().create_policy(payload)
        except OsagoError as e:
            application.last_error = str(e)
            application.save(update_fields=['last_error'])
            logger.error("ОСАГО: create_osago не прошёл (заявка %s): %s", application.id, e)
            return Response({"detail": e.detail, "application_id": application.id}, status=400)
 
        application.external_guid = result.get('guid')
        application.summa_insurance = result.get('summa_insurance') or None
        application.premiya_insurance = result.get('premiya_insurance') or None
        application.status = OsagoApplication.STATUS_CREATED
        application.save()
 
        return Response(OsagoApplicationSerializer(application).data, status=201)
 
 
@extend_schema_view(
    get=extend_schema(
        summary="Мои полисы и заявки ОСАГО",
        parameters=[OpenApiParameter('only_active', bool, description='Только действующие полисы')],
        tags=["ОСАГО"],
    )
)
class OsagoListView(ListAPIView):
    serializer_class = OsagoApplicationSerializer
    permission_classes = [IsAuthenticated]
 
    def get_queryset(self):
        client = getattr(self.request.user, 'client', None)
        if not client:
            return OsagoApplication.objects.none()
 
        qs = OsagoApplication.objects.filter(client=client).select_related('client_car')
 
        if self.request.query_params.get('only_active'):
            qs = qs.filter(
                status=OsagoApplication.STATUS_CONFIRMED,
                period_do__gte=date.today(),
            ).exclude(policy_status__in=['CANCELED', 'EXPIRED'])
 
        return qs
 
 
@extend_schema_view(get=extend_schema(summary="Детали заявки ОСАГО", tags=["ОСАГО"]))
class OsagoDetailView(RetrieveAPIView):
    serializer_class = OsagoApplicationSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'application_id'
 
    def get_queryset(self):
        return OsagoApplication.objects.filter(
            client=self.request.user.client
        ).select_related('client_car')
 
 
class OsagoStatusView(APIView):
    """
    Статус полиса. Фронт опрашивает этот эндпоинт после оплаты,
    пока не появится polis_number.
 
    Здесь же повторная попытка подтверждения: если вебхук не смог
    выпустить полис (страховая была недоступна), следующий опрос
    статуса попробует снова.
    """
    permission_classes = [IsAuthenticated]
 
    @extend_schema(
        summary="Статус полиса ОСАГО",
        responses=OsagoApplicationSerializer,
        description="Возвращает актуальный статус. Если полис оплачен, но ещё "
                    "не выпущен — пробует выпустить его повторно.",
        tags=["ОСАГО"],
    )
    def get(self, request, application_id):
        application = get_object_or_404(
            OsagoApplication, id=application_id, client=request.user.client
        )
 
        # Оплачено, но полиса нет — пробуем ещё раз.
        # confirm_osago идемпотентен, деньги повторно не спишутся.
        if application.status == OsagoApplication.STATUS_PAID:
            confirm_and_save(application)
 
        # Спрашиваем актуальный статус у Сакбола
        if application.external_guid:
            try:
                data = OsagoClient().get_status(application.external_guid)
            except OsagoError as e:
                logger.warning("ОСАГО: статус заявки %s недоступен: %s", application.id, e)
                return Response(OsagoApplicationSerializer(application).data)
 
            application.policy_status = data.get('status', '')
            if data.get('polis'):
                application.polis_number = data['polis']
            if data.get('pdf'):
                application.pdf_url = data['pdf']
            if data.get('summa_insurance'):
                application.summa_insurance = data['summa_insurance']
            if data.get('premiya_insurance'):
                application.premiya_insurance = data['premiya_insurance']
 
            if data.get('status') == 'ACTIVE' and application.status != OsagoApplication.STATUS_CONFIRMED:
                application.status = OsagoApplication.STATUS_CONFIRMED
 
            application.save()
 
        return Response(OsagoApplicationSerializer(application).data)