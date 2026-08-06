from django.db import models


class Client(models.Model):
    fio = models.CharField(max_length=255, verbose_name='ФИО')
    client_guid = models.UUIDField(null=True, blank=True,verbose_name='GUID клиента из 1С')
    phone = models.CharField(null=True, blank=True, unique=True, max_length=50, verbose_name='Телефон')
    email = models.EmailField(null=True, blank=True, max_length=255, verbose_name='Email')
    whatsapp = models.CharField(null=True, blank=True, max_length=50, verbose_name='WhatsApp')
    residence = models.CharField(null=True, blank=True, max_length=255, verbose_name='Место жительства')
    registration_address = models.CharField(null=True, blank=True, max_length=255, verbose_name='Регистрация')
    synced_at = models.DateTimeField(null=True, blank=True,verbose_name='Синхронизирован с 1С')

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'

    def __str__(self):
        return self.fio

class ClientCar(models.Model):
    client = models.ForeignKey( Client, on_delete=models.CASCADE, verbose_name='Клиент', related_name='client_car') 
    client_guid = models.UUIDField(null=True, blank=True,verbose_name='GUID клиента из 1С')
    deal_number = models.CharField(null=True, blank=True, max_length=50, verbose_name='Номер сделки')
    car_name = models.CharField(null=True, blank=True,max_length=255, verbose_name='Название автомобиля')
    car_model = models.CharField(null=True, blank=True,max_length=255, verbose_name='Модель автомобиля')
    car_year = models.IntegerField(null=True, blank=True,verbose_name='Год автомобиля')
    car_color = models.CharField(null=True, blank=True, max_length=50, verbose_name='Цвет автомобиля')
    car_vin = models.CharField(null=True, blank=True, max_length=50, verbose_name='VIN номер')
    car_number = models.CharField(null=True, blank=True, max_length=50, verbose_name='Номер автомобиля')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Сумма лизинга / основного долга')
    loan_guid = models.UUIDField(null=True, blank=True, unique=True, verbose_name='GUID кредита из 1С')
    paid_amount = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Погашено')
    remaining_amount = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Остаток к погашению')
    advance_payment_amount = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Авансовый платёж')
    disbursement_date = models.DateField(null=True, blank=True, verbose_name='Дата выдачи лизинга')
    last_payment_date = models.DateField(null=True, blank=True, verbose_name='Дата последнего платежа')
    term = models.PositiveIntegerField(null=True, blank=True, verbose_name='Срок (в месяцах)')

    due_days_principal = models.PositiveIntegerField(null=True, blank=True, verbose_name='Дней просрочки по основному долгу')
    due_days_interest = models.PositiveIntegerField(null=True, blank=True, verbose_name='Дней просрочки по процентам')

    due_amount_principal = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Просроченная сумма по основному долгу')
    due_amount_interest = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Просроченная сумма по процентам')

    principal_balance = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Остаток по основному долгу')
    interest_balance = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Остаток по процентам')
    penalty_balance = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Остаток по пене')
    synced_at = models.DateTimeField(null=True, blank=True, verbose_name='Синхронизирован с 1С')

    class Meta:
        verbose_name = 'Авто клиентов'
        verbose_name_plural = 'Авто клиентов'

    def __str__(self):
        return self.client.fio
    

class ImagesClientCar(models.Model):
    client_car = models.ForeignKey( ClientCar, on_delete=models.CASCADE, verbose_name='Клиент', related_name='images_client_car')
    image = models.ImageField(null=True, blank=True, upload_to='cars/', verbose_name='Изображение')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Изображение автомобиля'
        verbose_name_plural = 'Изображения автомобилей'

    def __str__(self):
        return self.client_car.client.fio
    
class RepaymentSchedule(models.Model):
    IS_PAID_CHOICES = [
        ('is_paid', 'Оплачено'),
        ('not_paid', 'Не оплачено'),
        ('in_process', 'В ожидании')
    ]
    car_client = models.ForeignKey(ClientCar, on_delete=models.CASCADE, verbose_name='Авто клиента', related_name='repayment_schedules')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Сумма лизинга / основного долга', null=True, blank=True)
    main_debt = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Основной долг', null=True, blank=True)
    interest = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Погашение начисл.',null=True, blank=True)
    total_payment = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Итог к погашению')
    paid_date = models.DateField(null=True, blank=True, verbose_name='Дата погашения')
    overdue_amount = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Просрочки')
    is_paid = models.CharField( choices=IS_PAID_CHOICES, verbose_name='Оплата',)
    is_paid_1c = models.CharField(max_length=20, null=True, blank=True, verbose_name='Оплата из 1С')
    last_reminder_sent = models.DateField(null=True, blank=True, verbose_name='Дата последнего напоминания')

    class Meta:
        verbose_name = 'График погашения'
        verbose_name_plural = 'Графики погашения'
        ordering = ['paid_date']
        constraints = [
            models.UniqueConstraint(
                fields=['car_client', 'paid_date'],
                name='unique_schedule_per_car_date'
            ),
        ]
 
    def __str__(self):
        return f"{self.car_client.client.fio} - {self.paid_date}"

class OsagoApplication(models.Model):
    """
    Полис ОСАГО: от заявки до выпущенного документа.
 
    Заменяет прежнюю модель InsuranceClient. Данные о страховках
    из 1С больше не импортируются — там эти поля всегда пустые.
 
    Жизненный цикл:
        draft     — черновик собран у нас, в страховую ещё не ушёл
        created   — create_osago прошёл, есть guid и сумма премии, ждём оплату
        paid      — клиент оплатил премию через BePay
        confirmed — confirm_osago прошёл, полис выпущен (есть номер и PDF)
        failed    — подтверждение не прошло, нужен разбор вручную
    """
 
    STATUS_DRAFT = 'draft'
    STATUS_CREATED = 'created'
    STATUS_PAID = 'paid'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_FAILED = 'failed'
 
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Черновик'),
        (STATUS_CREATED, 'Создана в страховой, ждёт оплаты'),
        (STATUS_PAID, 'Оплачена, подтверждается'),
        (STATUS_CONFIRMED, 'Полис выпущен'),
        (STATUS_FAILED, 'Ошибка подтверждения'),
    ]
 
    client = models.ForeignKey(
        'Client', on_delete=models.CASCADE,
        related_name='osago_applications', verbose_name='Клиент'
    )
    client_car = models.ForeignKey(
        'ClientCar', on_delete=models.CASCADE,
        related_name='osago_applications', verbose_name='Автомобиль'
    )
 
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT,
        verbose_name='Статус заявки'
    )
 
    # --- данные от страховой ---
    external_guid = models.UUIDField(
        null=True, blank=True, unique=True,
        verbose_name='GUID полиса в страховой'
    )
    summa_insurance = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Страховая сумма'
    )
    premiya_insurance = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Страховая премия (к оплате)'
    )
 
    polis_number = models.CharField(max_length=100, blank=True, verbose_name='Серия и номер полиса')
    pdf_url = models.URLField(blank=True, max_length=500, verbose_name='Ссылка на PDF полиса')
    policy_status = models.CharField(
        max_length=20, blank=True,
        verbose_name='Статус полиса (ACTIVE/CANCELED/EXPIRED/NOT_ACTIVE)'
    )
 
    period_ot = models.DateField(null=True, blank=True, verbose_name='Период страхования с')
    period_do = models.DateField(null=True, blank=True, verbose_name='Период страхования по')
 
    request_payload = models.JSONField(default=dict, blank=True, verbose_name='Отправленные данные')
    last_error = models.TextField(blank=True, verbose_name='Последняя ошибка')
 
    # для напоминаний об истечении (аналог last_reminder_sent в графике)
    last_reminder_sent = models.DateField(
        null=True, blank=True, verbose_name='Дата последнего напоминания'
    )
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата выпуска полиса')
 
    class Meta:
        verbose_name = 'Полис ОСАГО'
        verbose_name_plural = 'Полисы ОСАГО'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['period_do']),
        ]
 
    def __str__(self):
        return f"ОСАГО {self.client.fio} / {self.client_car.car_number} ({self.get_status_display()})"
 
    @property
    def premium_tyiyn(self) -> int:
        """Премия в тыйынах — в таком виде её принимает BePay."""
        if self.premiya_insurance is None:
            return 0
        return int((self.premiya_insurance * 100).to_integral_value())
 
    @property
    def is_active_policy(self) -> bool:
        """Выпущенный и не отменённый полис."""
        return (
            self.status == self.STATUS_CONFIRMED
            and self.policy_status not in ('CANCELED', 'EXPIRED')
        )
 

class ContactClient(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name='Клиент', related_name='contacts')
    name = models.CharField(max_length=255, verbose_name='Имя')
    phone = models.CharField(max_length=50, verbose_name='Телефон', unique=True)

    class Meta:
        verbose_name = 'Контакт клиента'
        verbose_name_plural = 'Контакты клиентов'

    def __str__(self):
        return self.name

class LocationClient(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name='Клиент', related_name='locations')
    latitude = models.FloatField(verbose_name='Широта')
    longitude = models.FloatField(verbose_name='Долгота')

    class Meta:
        verbose_name = 'Локация клиента'
        verbose_name_plural = 'Локации клиентов'

    def __str__(self):
        return f"{self.client.fio} - {self.latitude}, {self.longitude}"
    

class AdCars(models.Model):
    car_name = models.CharField(max_length=255, verbose_name='Название автомобиля')
    car_model = models.CharField(max_length=255, verbose_name='Модель автомобиля')
    car_year = models.IntegerField(verbose_name='Год автомобиля')
    car_color = models.CharField(max_length=50, verbose_name='Цвет автомобиля')
    car_vin = models.CharField(null=True, blank=True, max_length=50, verbose_name='VIN номер')
    description = models.TextField(null=True, blank=True, verbose_name='Описание')
    price = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Цена')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    is_sold = models.BooleanField(default=False, verbose_name='Продано')
    is_active = models.BooleanField(default=True, verbose_name='Срочно')

    class Meta:
        verbose_name = 'Объявление о продаже'
        verbose_name_plural = 'Объявления о продаже'

    def __str__(self):
        return self.car_name
    
class ImagesAdCars(models.Model):
    ad_cars = models.ForeignKey(AdCars, on_delete=models.CASCADE, verbose_name='Объявление', related_name='images_ad_cars')
    image = models.ImageField(null=True, blank=True, upload_to='ad-cars/', verbose_name='Изображение')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Изображение автомобиля'
        verbose_name_plural = 'Изображения автомобилей'

    def __str__(self):
        return self.ad_cars.car_name


class CalculateInfo(models.Model):
    down_payment = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Первоначальный взнос')
    leasing_term = models.IntegerField(null=True, blank=True, verbose_name='Срок лизинга (в месяцах)')
    interest_rate = models.DecimalField(null=True, blank=True, max_digits=5, decimal_places=2, verbose_name='Процентная ставка')
    insurance_cost = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Стоимость страховки')
    gps_cost = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Стоимость GPS')
    decor_cost = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Стоимость оформления')

    class Meta:
        verbose_name = 'Информация для расчета'
        verbose_name_plural = 'Информация для расчетов'

    def __str__(self):
        return f"Расчет"


class Send_Message(models.Model):
    message = models.TextField(verbose_name='Сообщение')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Рассылка'
        verbose_name_plural = 'Рассылки'

    def __str__(self):
        return self.message
    
class Notification(models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, verbose_name='Пользователь', related_name='notifications')
    message = models.TextField(verbose_name='Сообщение')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'

    def __str__(self):
        return self.user.phone


class WaybillExtraName(models.Model):
    client_car = models.ForeignKey(
        'ClientCar',
        on_delete=models.CASCADE,
        related_name='extra_waybill_names',
        verbose_name='Авто клиента'
    )
    fio = models.CharField(max_length=255, verbose_name='Доп. ФИО для путевого листа')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Дополнительное имя для путевого листа'
        verbose_name_plural = 'Дополнительные имена для путевых листов'

    def __str__(self):
        return f"{self.fio} ({self.client_car.car_name})"


class AppVersion(models.Model):
    version = models.CharField(max_length=20, verbose_name="Версия приложения")

    class Meta:
        verbose_name = "Версия для apple"
        verbose_name_plural = "Версии apple"

    def __str__(self):
        return self.version

class AppAndroidVersion(models.Model):
    version = models.CharField(max_length=20, verbose_name="Версия приложения")

    class Meta:
        verbose_name = "Версия для android"
        verbose_name_plural = "Версии android"

    def __str__(self):
        return self.version


