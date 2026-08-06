# payments/models.py
import uuid
from django.db import models

class Payment(models.Model):
    """
    Платёж через BePay. Может быть двух видов:
      - repayment: платёж по графику погашения (было раньше)
      - osago:     оплата полиса ОСАГО (новое)
 
    Старая логика не сломана: purpose по умолчанию 'repayment',
    существующие платежи остаются платежами по графику.
    """
 
    STATUS_CREATED = 10
    STATUS_IN_PROCESS = 20
    STATUS_ERROR = 30
    STATUS_CANCELED = 40
    STATUS_SUCCESS = 50
 
    STATUS_CHOICES = [
        (STATUS_CREATED, "Created"),
        (STATUS_IN_PROCESS, "In process"),
        (STATUS_ERROR, "Error"),
        (STATUS_CANCELED, "Canceled"),
        (STATUS_SUCCESS, "Success"),
    ]
 
    PURPOSE_REPAYMENT = 'repayment'
    PURPOSE_OSAGO = 'osago'
 
    PURPOSE_CHOICES = [
        (PURPOSE_REPAYMENT, 'Платёж по графику'),
        (PURPOSE_OSAGO, 'Оплата полиса ОСАГО'),
    ]
 
    purpose = models.CharField(
        max_length=20, choices=PURPOSE_CHOICES, default=PURPOSE_REPAYMENT,
        verbose_name='Назначение платежа'
    )
 
    # Клиент напрямую — раньше владельца искали через
    # repayment_schedule → car_client → client. Для ОСАГО этой цепочки нет.
    client = models.ForeignKey(
        'core.Client', on_delete=models.CASCADE,
        related_name='payments', null=True, blank=True,
        verbose_name='Клиент'
    )
 
    # Заполнено ровно одно из двух, в зависимости от purpose
    repayment_schedule = models.ForeignKey(
        'core.RepaymentSchedule', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='bepay_payments',
        verbose_name='Платёж из графика'
    )
    osago_application = models.ForeignKey(
        'core.OsagoApplication', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payments',
        verbose_name='Заявка ОСАГО'
    )
 
    # --- поля BePay ---
    user_guid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    bepay_uuid = models.UUIDField(null=True, blank=True, unique=True)
 
    description = models.CharField(max_length=99, verbose_name='Описание')
    amount = models.PositiveIntegerField(verbose_name='Сумма в тыйынах')
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=STATUS_CREATED)
 
    qr_code_url = models.URLField(blank=True, max_length=500)
    qr_base64 = models.TextField(blank=True)
    providers = models.JSONField(default=list, blank=True)
 
    expires_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        verbose_name = 'Платёж'
        verbose_name_plural = 'Платежи'
        ordering = ['-created_at']
 
    def is_final(self) -> bool:
        return self.status in (self.STATUS_ERROR, self.STATUS_CANCELED, self.STATUS_SUCCESS)
 
    def __str__(self):
        return f"{self.get_purpose_display()} {self.user_guid} ({self.get_status_display()})"
 