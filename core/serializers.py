from rest_framework import serializers
from .models import  (
    Client, RepaymentSchedule, InsuranceClient,
    ContactClient, LocationClient, AdCars, CalculateInfo, ImagesClientCar, ImagesAdCars, ClientCar, Send_Message, Notification
)

class ClientSerializers(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'fio', 'phone', 'email', 'whatsapp']

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
        fields = ['id','client','client_car_full_name', 'insurance_company', 'policy_number', 'start_date', 'end_date']
    
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
        request = self.context.get('request')  # получаем объект запроса
        first_img = obj.images_ad_cars.first()
        if first_img and first_img.image:
            return request.build_absolute_uri(first_img.image.url)
        return None


class AdCarsDetailSerializers(serializers.ModelSerializer):
    images = ImagesAdCarsSerializer(many=True, source='images_ad_cars')

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

class ContactClientBulkCreateSerializer(serializers.Serializer):
    contacts = ContactClientSerializers(many=True)

    def create(self, validated_data):
        client = self.context['request'].user.client
        contacts_data = validated_data['contacts']
        contact_objs = [
            ContactClient(client=client, **contact) for contact in contacts_data
        ]
        return ContactClient.objects.bulk_create(contact_objs)


class LocationClientSerializers(serializers.ModelSerializer):
    fio = serializers.CharField(source='client.fio', read_only=True)
    client_id = serializers.IntegerField(source='client.id', read_only=True)
    class Meta:
        model = LocationClient
        fields = ['id', 'client_id','fio' ,'latitude', 'longitude']

class LocationClientDetailSerializers(serializers.ModelSerializer):

    class Meta:
        model = LocationClient
        fields = ['id', 'latitude', 'longitude']

class SendMessageSerializer(serializers.ModelSerializer):
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()

    class Meta:
        model = Send_Message
        fields = ['id', 'message', 'created_at', 'updated_at']

    def get_created_at(self, obj):
        return obj.created_at.strftime('%d %B %Y, %H:%M')

    def get_updated_at(self, obj):
        return obj.updated_at.strftime('%d %B %Y, %H:%M')
 
class NotificationSerializer(serializers.ModelSerializer):
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'message', 'created_at']
        read_only_fields = ['created_at']

    def get_created_at(self, obj):
        return obj.created_at.strftime('%d %B %Y, %H:%M')
    

class LeasingCalcInputSerializer(serializers.Serializer):
    car_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    down_payment = serializers.DecimalField(max_digits=12, decimal_places=2)
    leasing_term_months = serializers.IntegerField(min_value=1)
    interest_rate_annual = serializers.DecimalField(max_digits=5, decimal_places=2)

class LeasingResultSerializer(serializers.Serializer):
    car_total_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    monthly_payment = serializers.DecimalField(max_digits=12, decimal_places=2)
    initial_payment_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    details = serializers.DictField(child=serializers.DecimalField(max_digits=12, decimal_places=2))
