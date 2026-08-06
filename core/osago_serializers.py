from datetime import date
 
from rest_framework import serializers
 
from .models import OsagoApplication
 
 
class OsagoDriverSerializer(serializers.Serializer):
    nameid = serializers.CharField(max_length=500)
    inn = serializers.CharField(max_length=50)
    date_birth = serializers.DateField()
    driver_license = serializers.CharField(max_length=500)
    date_issue_license = serializers.DateField()
 
 
class OsagoCreateSerializer(serializers.Serializer):
    """Форма оформления полиса. Поля соответствуют документации Сакбола."""
 
    car_id = serializers.IntegerField(help_text='ID машины из нашей базы')
 
    # --- страхователь ---
    code_sp_type_client = serializers.ChoiceField(choices=[1, 2], default=1)
    inn = serializers.CharField(max_length=50)
    nameid = serializers.CharField(max_length=500, required=False, allow_blank=True)
    date_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=[1, 2], required=False, allow_null=True)
    passport_series = serializers.CharField(max_length=50, required=False, allow_blank=True)
    passport_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    passport_issue = serializers.CharField(max_length=50, required=False, allow_blank=True)
    passport_date_issue = serializers.DateField(required=False, allow_null=True)
 
    address_code_country = serializers.IntegerField()
    address_region = serializers.CharField(max_length=50, required=False, allow_blank=True)
    address_area = serializers.CharField(max_length=50, required=False, allow_blank=True)
    address_locality = serializers.CharField(max_length=50)
    address_street_house_flat = serializers.CharField(max_length=500)
    phone = serializers.CharField(max_length=500, required=False, allow_blank=True)
 
    # --- собственник ---
    car_owner_policyholder_is_owner = serializers.ChoiceField(choices=[0, 1], default=1)
    car_owner_inn = serializers.CharField(max_length=50, required=False, allow_blank=True)
    car_owner_nameid = serializers.CharField(max_length=500, required=False, allow_blank=True)
    car_owner_date_birth = serializers.DateField(required=False, allow_null=True)
    car_owner_gender = serializers.ChoiceField(choices=[1, 2], required=False, allow_null=True)
    car_owner_passport_series = serializers.CharField(max_length=50, required=False, allow_blank=True)
    car_owner_passport_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    car_owner_passport_issue = serializers.CharField(max_length=50, required=False, allow_blank=True)
    car_owner_passport_date_issue = serializers.DateField(required=False, allow_null=True)
    car_owner_address_code_country = serializers.IntegerField(required=False, allow_null=True)
    car_owner_address_region = serializers.CharField(max_length=50, required=False, allow_blank=True)
    car_owner_address_area = serializers.CharField(max_length=50, required=False, allow_blank=True)
    car_owner_address_locality = serializers.CharField(max_length=50, required=False, allow_blank=True)
    car_owner_address_street_house_flat = serializers.CharField(max_length=500, required=False, allow_blank=True)
    car_owner_phone = serializers.CharField(max_length=500, required=False, allow_blank=True)
 
    # --- период ---
    period_ot = serializers.DateField()
    period_do = serializers.DateField()
    code_sp_insurance_territory = serializers.CharField(
        max_length=100, help_text='Одно или несколько значений через запятую: "1,3,2"'
    )
 
    # --- предыдущий полис ---
    old_isset_polis = serializers.ChoiceField(choices=[0, 1], default=0)
    old_insurer = serializers.CharField(max_length=500, required=False, allow_blank=True)
    old_prefix_polis = serializers.CharField(max_length=50, required=False, allow_blank=True)
    old_number_polis = serializers.CharField(max_length=50, required=False, allow_blank=True)
 
    # --- доверенность ---
    car_owner_isset_procuration = serializers.ChoiceField(choices=[0, 1], default=0)
    car_owner_procuration_series = serializers.CharField(max_length=50, required=False, allow_blank=True)
    car_owner_procuration_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    car_owner_procuration_date_issue = serializers.DateField(required=False, allow_null=True)
 
    # --- транспорт ---
    car_is_register_kr = serializers.ChoiceField(choices=[0, 1], default=1)
    car_code_transport_type = serializers.IntegerField()
    car_sp_marka = serializers.CharField(max_length=50, required=False, allow_blank=True)
    car_sp_model = serializers.CharField(max_length=50, required=False, allow_blank=True)
    car_engine_displacement = serializers.FloatField(required=False, allow_null=True)
    car_electro_car = serializers.ChoiceField(choices=[0, 1], default=0)
    car_engine_power = serializers.FloatField(required=False, allow_null=True)
    car_code_steering_position = serializers.ChoiceField(choices=[1, 2])
    car_max_weight = serializers.FloatField(required=False, allow_null=True)
    car_count_passengers = serializers.IntegerField(required=False, allow_null=True)
    car_weight = serializers.FloatField()
    car_is_trailer = serializers.ChoiceField(choices=[0, 1], default=0)
    car_code_car_of_use = serializers.IntegerField()
    car_code_type_document = serializers.IntegerField()
    car_year_issue = serializers.IntegerField(required=False, allow_null=True)
    car_vin = serializers.CharField(max_length=100, required=False, allow_blank=True)
    car_chassis = serializers.CharField(max_length=100, required=False, allow_blank=True)
    car_body = serializers.CharField(max_length=100, required=False, allow_blank=True)
    car_series_number_document = serializers.CharField(max_length=100)
    car_issuing_authority = serializers.CharField(max_length=100, required=False, allow_blank=True)
    car_document_issue_date = serializers.DateField(required=False, allow_null=True)
    car_license_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
 
    # --- техосмотр ---
    car_tech_inspection = serializers.ChoiceField(choices=[0, 1], default=0)
    car_series_tech_inspection = serializers.CharField(max_length=50, required=False, allow_blank=True)
    car_number_tech_inspection = serializers.CharField(max_length=50, required=False, allow_blank=True)
    car_date_tech_inspection = serializers.DateField(required=False, allow_null=True)
    car_expired_date_tech_inspection = serializers.DateField(required=False, allow_null=True)
 
    # --- водители ---
    car_unlimited_driwers = serializers.ChoiceField(choices=[0, 1], default=0)
    driwers = OsagoDriverSerializer(many=True, required=False)
 
    def validate(self, attrs):
        """Условно обязательные поля — по правилам из документации Сакбола."""
        errors = {}
 
        # физлицо → паспортные данные обязательны
        if attrs.get('code_sp_type_client') == 1:
            for field in ('date_birth', 'gender', 'passport_series',
                          'passport_number', 'passport_issue', 'passport_date_issue'):
                if not attrs.get(field):
                    errors[field] = 'Обязательно для физического лица'
 
        transport_type = attrs.get('car_code_transport_type')
        electro = attrs.get('car_electro_car', 0)
 
        if transport_type == 1:  # легковой
            if electro == 0 and not attrs.get('car_engine_displacement'):
                errors['car_engine_displacement'] = 'Обязательно для авто с ДВС'
            if electro == 1 and not attrs.get('car_engine_power'):
                errors['car_engine_power'] = 'Обязательно для электромобиля'
        elif transport_type == 2 and not attrs.get('car_max_weight'):
            errors['car_max_weight'] = 'Обязательно для грузового транспорта'
        elif transport_type == 3 and not attrs.get('car_count_passengers'):
            errors['car_count_passengers'] = 'Обязательно для пассажирского транспорта'
 
        if attrs.get('old_isset_polis') == 1:
            for field in ('old_insurer', 'old_prefix_polis', 'old_number_polis'):
                if not attrs.get(field):
                    errors[field] = 'Обязательно при наличии предыдущего полиса'
 
        if attrs.get('car_owner_isset_procuration') == 1:
            for field in ('car_owner_procuration_series', 'car_owner_procuration_number',
                          'car_owner_procuration_date_issue'):
                if not attrs.get(field):
                    errors[field] = 'Обязательно при наличии доверенности'
 
        if attrs.get('car_tech_inspection') == 1:
            for field in ('car_number_tech_inspection', 'car_date_tech_inspection',
                          'car_expired_date_tech_inspection'):
                if not attrs.get(field):
                    errors[field] = 'Обязательно при наличии диагностической карты'
 
        if attrs.get('car_unlimited_driwers') == 0 and not attrs.get('driwers'):
            errors['driwers'] = 'Укажите водителей или выберите "без ограничений"'
 
        if attrs.get('period_do') and attrs.get('period_ot'):
            if attrs['period_do'] <= attrs['period_ot']:
                errors['period_do'] = 'Дата окончания должна быть позже даты начала'
 
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
 
 
class OsagoApplicationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    car_number = serializers.CharField(source='client_car.car_number', read_only=True)
    car_model = serializers.CharField(source='client_car.car_model', read_only=True)
    premium_tyiyn = serializers.IntegerField(read_only=True)
    is_active_policy = serializers.BooleanField(read_only=True)
    days_left = serializers.SerializerMethodField()
 
    class Meta:
        model = OsagoApplication
        fields = [
            'id', 'status', 'status_display',
            'client_car', 'car_number', 'car_model',
            'summa_insurance', 'premiya_insurance', 'premium_tyiyn',
            'polis_number', 'pdf_url', 'policy_status', 'is_active_policy',
            'period_ot', 'period_do', 'days_left',
            'last_error', 'created_at', 'confirmed_at',
        ]
        read_only_fields = fields
 
    def get_days_left(self, obj):
        if not obj.period_do or obj.status != OsagoApplication.STATUS_CONFIRMED:
            return None
        return (obj.period_do - date.today()).days
 