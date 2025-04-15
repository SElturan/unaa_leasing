from django.shortcuts import render
from django.contrib.auth import authenticate
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny
from accounts.models import User
from accounts.serializers import UserLoginSerializer

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
                'email': user.phone,
                'role': user.is_staff,
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid phone or password"}, status=status.HTTP_401_UNAUTHORIZED)
