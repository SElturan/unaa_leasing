# payments/models.py
import uuid
from django.db import models


class Payment(models.Model):
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

    # внутренний идентификатор — используем как user_guid при запросе QR
    user_guid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # то, что вернул BePay
    bepay_uuid = models.UUIDField(null=True, blank=True, unique=True)

    description = models.CharField(max_length=99)
    amount = models.PositiveIntegerField(help_text="Сумма в тыйынах")
    status = models.PositiveSmallIntegerField(
        choices=STATUS_CHOICES, default=STATUS_CREATED
    )

    qr_code_url = models.URLField(blank=True)
    providers = models.JSONField(default=list, blank=True)

    repayment_schedule = models.ForeignKey(
        'core.RepaymentSchedule',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='bepay_payments',
        verbose_name='Платёж из графика'
    )

    expires_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_final(self) -> bool:
        return self.status in (
            self.STATUS_ERROR,
            self.STATUS_CANCELED,
            self.STATUS_SUCCESS,
        )

    def __str__(self):
        return f"Payment {self.user_guid} ({self.get_status_display()})"