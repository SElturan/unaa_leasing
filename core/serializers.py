from rest_framework import serializers
from .models import  (
    Client, RepaymentSchedule, InsuranceClient,
    ContactClient, LocationClient, AdCars, CalculateInfo, ImagesClientCar, ImagesAdCars, ClientCar
)

class ClientSerializers(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'fio', 'email', 'whatsapp']

class ClientCarSerializers(serializers.ModelSerializer):
    class Meta:
        model = ClientCar
        fields = ['id','client', 'car_name', 'car_model', 'car_number',]

class ImagesClientCarSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagesClientCar
        fields = ['id', 'image']

class RepaymentScheduleSerializers(serializers.ModelSerializer):
    class Meta:
        model = RepaymentSchedule
        fields = ['id', 'total_amount', 'total_payment', 'paid_date', 'is_paid']

class RepaymentDetailScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepaymentSchedule
        fields = [
            'id',
            'total_amount',
            'main_debt',
            'interest',
            'total_payment',
            'paid_date',
            'overdue_amount',
            'is_paid'
        ]

class ClientCarDetailSerializers(serializers.ModelSerializer):
    images = ImagesClientCarSerializer(many=True, source='images_client_car')

    class Meta:
        model = ClientCar
        fields = [
            'id', 'client', 'car_name', 'car_model', 'car_year',
            'car_color', 'car_vin', 'car_number', 'total_amount', 'paid_amount', 'remaining_amount', 'images'
        ]

class InsuranceClientSerializers(serializers.ModelSerializer):
    client_car_full_name = serializers.SerializerMethodField()

    class Meta:
        model = InsuranceClient
        fields = ['id','client_car_full_name', 'insurance_company', 'policy_number', 'start_date', 'end_date']
    
    def get_client_car_full_name(self, obj):
        return f"{obj.client.car_name} {obj.client.car_model} {obj.client.car_year}"

class ImagesAdCarsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagesAdCars
        fields = ['id', 'image']

class AdCarsSerializers(serializers.ModelSerializer):
    first_image = serializers.SerializerMethodField()

    class Meta:
        model = AdCars
        fields = ['id', 'car_name', 'car_model', 'car_year', 'car_color', 'price', 'first_image']

    def get_first_image(self, obj):
        first_img = obj.images_ad_car.first()
        if first_img and first_img.image:
            return first_img.image.url
        return None


class AdCarsDetailSerializers(serializers.ModelSerializer):
    images = ImagesAdCarsSerializer(many=True, source='images_ad_car')

    class Meta:
        model = AdCars
        fields = ['id','images','car_name', 'car_model', 'car_year', 'car_color', 'car_vin', 'description', 'price', 'is_sold', 'is_active', 'created_at']

class CreditCalculationSerializer(serializers.Serializer):
    car_id = serializers.IntegerField()
    down_payment = serializers.DecimalField(max_digits=12, decimal_places=2)

class ContactClientSerializers(serializers.ModelSerializer):
    class Meta:
        model = ContactClient
        fields = ['id', 'name', 'phone']

class LocationClientSerializers(serializers.ModelSerializer):
    class Meta:
        model = LocationClient
        fields = ['id', 'latitude', 'longitude']