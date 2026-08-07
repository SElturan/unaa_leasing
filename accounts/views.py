from django.shortcuts import render
from django.contrib.auth import authenticate
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.permissions import AllowAny, IsAuthenticated
from accounts.models import User
from accounts.serializers import UserLoginSerializer, UserRegisterSerializer,ExpoPushTokenSerializer
from core.models import Client
from core.sync_1c import normalize_phone, find_client_in_1c, OneCError
import logging

logger = logging.getLogger(__name__)
 

class UserLoginView(generics.GenericAPIView):
    serializer_class = UserLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']
        password = serializer.validated_data['password']
        print(phone)
        print(password)
        
        user = authenticate(request, phone=phone, password=password)
        print(user)
        if user:  
            refresh = RefreshToken.for_user(user)
            return Response({
                
                'id': user.id,
                'phone': user.phone,
                'role': user.is_staff,
                'is_active': user.is_active,
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Неверный номер или пароль"}, status=status.HTTP_401_UNAUTHORIZED)

 
class UserRegisterView(generics.GenericAPIView):
    """
    Регистрация клиента.
 
    Порядок поиска:
      1. Ищем в нашей базе по нормализованному телефону.
      2. Если нет — идём в 1С за последние ONEC_REGISTRATION_DAYS дней
         (клиент мог оформить договор уже после последней синхронизации).
      3. Если и там нет — отказ.
    """
    serializer_class = UserRegisterSerializer
 
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
 
        phone_raw = serializer.validated_data['phone']
        password = serializer.validated_data['password']
        password2 = serializer.validated_data.get('password2')
 
        if password2 and password != password2:
            return Response(
                {"error": "Пароли не совпадают"},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        phone = normalize_phone(phone_raw)
        if not phone:
            return Response(
                {"error": "Некорректный номер телефона"},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        # у пользователя телефон тоже храним нормализованным,
        # иначе логин "996500..." не найдёт юзера "0500..."
        if User.objects.filter(phone=phone).exists():
            return Response(
                {"error": "Пользователь с таким номером уже существует"},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        # 1. локальный поиск
        client = Client.objects.filter(phone=phone).first()
 
        # 2. не нашли — спрашиваем 1С
        if not client:
            try:
                client = find_client_in_1c(phone)
            except OneCError as e:
                logger.error("Регистрация: 1С недоступна (%s)", e)
                return Response(
                    {"error": "Сервис временно недоступен, попробуйте через несколько минут"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
 
        # 3. нигде нет
        if not client:
            return Response(
                {"error": "Ваш номер не найден среди клиентов Унаа Лизинг.\n"
                          "Если вы недавно оформили договор, обратитесь в офис."},
                status=status.HTTP_401_UNAUTHORIZED
            )
 
        user = User.objects.create(phone=phone, client=client, is_active=True)
        user.set_password(password)
        user.save()
 
        refresh = RefreshToken.for_user(user)
        return Response({
            "id": user.id,
            "phone": user.phone,
            "client_id": client.id,
            "is_active": user.is_active,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)
 

class CustomTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            access_token = str(token.access_token)
            new_refresh_token = str(token)

            return Response({
                "access": access_token,
                "refresh": new_refresh_token
            })

        except Exception as e:
            return Response({"detail": "Invalid refresh token"}, status=status.HTTP_401_UNAUTHORIZED)
        
class ExpoPushTokenView(generics.UpdateAPIView):
    serializer_class = ExpoPushTokenSerializer
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

class DeleteAccountView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        request.user.is_active = False
        request.user.save(update_fields=["is_active",])

        return Response(
            {"message": "Аккаунт успешно удален"},
            status=status.HTTP_200_OK,
        )