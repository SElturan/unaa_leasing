from django.db import models


class Client(models.Model):
    fio = models.CharField(max_length=255, verbose_name='ФИО')
    phone = models.CharField(null=True, blank=True, max_length=50, verbose_name='Телефон')
    email = models.EmailField(null=True, blank=True, max_length=255, verbose_name='Email')
    whatsapp = models.CharField(null=True, blank=True, max_length=50, verbose_name='WhatsApp')

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'

    def __str__(self):
        return self.fio

class ClientCar(models.Model):
    client = models.ForeignKey( Client, on_delete=models.CASCADE, verbose_name='Клиент', related_name='client_car')
    car_name = models.CharField(max_length=255, verbose_name='Название автомобиля')
    car_model = models.CharField(max_length=255, verbose_name='Модель автомобиля')
    car_year = models.IntegerField(verbose_name='Год автомобиля')
    car_color = models.CharField(null=True, blank=True, max_length=50, verbose_name='Цвет автомобиля')
    car_vin = models.CharField(null=True, blank=True, max_length=50, verbose_name='VIN номер')
    car_number = models.CharField(null=True, blank=True, max_length=50, verbose_name='Номер автомобиля')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Сумма лизинга / основного долга')
    paid_amount = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Погашено')
    remaining_amount = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Остаток к погашению')

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
    car_client = models.ForeignKey(ClientCar, on_delete=models.CASCADE, verbose_name='Авто клиента', related_name='repayment_schedules')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Сумма лизинга / основного долга')
    main_debt = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Основной долг')
    interest = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Погашение начисл.')
    total_payment = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Итог к погашению')
    paid_date = models.DateField(null=True, blank=True, verbose_name='Дата погашения')
    overdue_amount = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2, verbose_name='Просрочки')
    is_paid = models.BooleanField(default=False, verbose_name='Оплачен')

    class Meta:
        verbose_name = 'График погашения'
        verbose_name_plural = 'Графики погашения'
        ordering = ['paid_date']

    def __str__(self):
        return f"{self.car_client.client.fio} - {self.paid_date}"

class InsuranceClient(models.Model):
    INSURANCE_CHOICES = [
        ('OSAGO', 'ОСАГО'),
        ('KASKO', 'КАСКО'),
    ]

    client = models.ForeignKey(ClientCar, on_delete=models.CASCADE, verbose_name='Клиент', related_name='insurances')
    insurance_company = models.CharField(max_length=255, choices=INSURANCE_CHOICES ,verbose_name='Страховая компания')
    policy_number = models.CharField(max_length=50, verbose_name='Номер полиса')
    start_date = models.DateField(verbose_name='Дата начала')
    end_date = models.DateField(verbose_name='Дата окончания')

    class Meta:
        verbose_name = 'Страхование клиента'
        verbose_name_plural = 'Страхования клиентов'

    def __str__(self):
        return f"{self.client.client.fio} - {self.insurance_company}"


class ContactClient(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name='Клиент', related_name='contacts')
    name = models.CharField(max_length=255, verbose_name='Имя')
    phone = models.CharField(max_length=50, verbose_name='Телефон')

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
    
