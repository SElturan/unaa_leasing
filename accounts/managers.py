from django.contrib.auth.base_user import BaseUserManager
from django.core.exceptions import ObjectDoesNotExist


class UserManager(BaseUserManager):
    def create_user(self, phone=None, password=None, **extra_fields):
        if not password:
            raise ValueError('User must have a password.')

        if not phone:
            raise ValueError('User must have a phone.')

        extra_fields.setdefault('is_active', True)  
        extra_fields.setdefault('is_superuser', False)

        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    
    def create_superuser(self, phone=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')

        return self.create_user(phone=phone, password=password, **extra_fields)

    def get_user_by_token(self, token):
        try:
            return self.get(token=token)
        except ObjectDoesNotExist:
            return None
