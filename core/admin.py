from django.contrib import admin
from .models import (
    Client, RepaymentSchedule, InsuranceClient,
    ContactClient, LocationClient, AdCars, CalculateInfo, ImagesClientCar, ImagesAdCars, ClientCar, Send_Message
)


class ImagesClientCarInline(admin.TabularInline):
    model = ImagesClientCar
    extra = 0

class ImagesAdCarsInline(admin.TabularInline):
    model = ImagesAdCars
    extra = 0

class ClientCarInline(admin.TabularInline):
    model = ClientCar
    extra = 0


class ContactClientInline(admin.TabularInline):
    model = ContactClient
    extra = 0


class LocationClientInline(admin.TabularInline):
    model = LocationClient
    extra = 0


class ClientAdmin(admin.ModelAdmin):
    list_display = ['id','fio', 'phone', 'email', 'whatsapp',]
    search_fields = ['fio', 'phone', 'email',]
    inlines = [ClientCarInline ,ContactClientInline, LocationClientInline]

admin.site.register(Client, ClientAdmin)

class ClientCarAdmin(admin.ModelAdmin):
    list_display = ['id','client', 'car_name', 'car_model', 'car_year', 'car_color', 'car_vin', 'car_number', 'total_amount', 'paid_amount', 'remaining_amount' ,]
    search_fields = ['client__fio', 'car_number']
    inlines = (ImagesClientCarInline,)

admin.site.register(ClientCar, ClientCarAdmin)

class RepaymentScheduleAdmin(admin.ModelAdmin):
    list_display = [
            'id',
            'car_client',
            'total_amount',
            'main_debt',
            'interest',
            'total_payment',
            'paid_date',
            'overdue_amount',
            'is_paid'
        ]
    list_filter = ['is_paid']
    search_fields = ['car_client__client__fio']
    ordering = ['paid_date']

admin.site.register(RepaymentSchedule, RepaymentScheduleAdmin)


class InsuranceClientAdmin(admin.ModelAdmin):
    list_display = ['id','client', 'insurance_company', 'policy_number', 'start_date', 'end_date']
    search_fields = ['client__client__fio', 'policy_number']
    list_filter = ['insurance_company', 'start_date', 'end_date']

admin.site.register(InsuranceClient, InsuranceClientAdmin)


class ContactClientAdmin(admin.ModelAdmin):
    list_display = ['client', 'name', 'phone']
    search_fields = ['client__fio', 'name', 'phone']

admin.site.register(ContactClient, ContactClientAdmin)


class LocationClientAdmin(admin.ModelAdmin):
    list_display = ['client', 'latitude', 'longitude']
    search_fields = ['client__fio']

admin.site.register(LocationClient, LocationClientAdmin)


class AdCarsAdmin(admin.ModelAdmin):
    list_display = ['car_name', 'car_model', 'car_year', 'price', 'is_sold', 'is_active', 'created_at']
    search_fields = ['car_name', 'car_model', 'car_vin']
    list_filter = ['car_year', 'car_color', 'is_sold', 'is_active']
    inlines = [ImagesAdCarsInline]

admin.site.register(AdCars, AdCarsAdmin)


class CalculateInfoAdmin(admin.ModelAdmin):
    list_display = ['down_payment', 'leasing_term', 'interest_rate', 'insurance_cost', 'gps_cost', 'decor_cost']
    list_filter = ['leasing_term', 'interest_rate']

admin.site.register(CalculateInfo, CalculateInfoAdmin)

class SendMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'message', 'created_at']
    search_fields = ['message']
    ordering = ['created_at']

admin.site.register(Send_Message, SendMessageAdmin)