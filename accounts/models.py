from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from accounts.managers import *
from core.models import Client


class User(AbstractBaseUser, PermissionsMixin):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name='Клиент', null=True, blank=True ,related_name='users')
    phone = models.CharField('Номер телефона', max_length=50, blank=True, unique=True ,db_index=True)
    is_staff = models.BooleanField('Сотрудник', default=False)
    is_superuser = models.BooleanField('Суперпользователь', default=False)
    is_active = models.BooleanField('Активен', default=False)
    is_delete = models.BooleanField('Удален', default=False)
    expo_push_token = models.CharField('Expo Push Token', max_length=255, blank=True, null=True)
    registered_at = models.DateTimeField('Дата регистрации', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.phone

    def save(self, *args, **kwargs):
        if not self.phone:
            raise ValueError('User must have an phone')
        super(User, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not self.is_superuser:
            self.is_delete = True
            self.save()
        else:
            super().delete(*args, **kwargs)

    class Meta:
        verbose_name = ('Пользователь')
        verbose_name_plural = ('Пользователи')
