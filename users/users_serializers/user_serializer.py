from datetime import timedelta
from rest_framework import serializers
from users.models import User
from django.contrib.auth.hashers import check_password
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from users.models import ReferralDiscount
from orders.models import Order
from reviews.models import ProductReview
from shipments.models import DeliveryAddress, Shipment

class UserSerializer(serializers.ModelSerializer):
    dni = serializers.CharField()
    orders = serializers.SerializerMethodField()
    pending_orders_counter = serializers.SerializerMethodField()
    addresses_counter = serializers.SerializerMethodField()
    referrer_code = serializers.CharField(write_only=True, required=False)
    reviews_counter = serializers.SerializerMethodField()
    rewards_counter = serializers.SerializerMethodField()
    total_spend = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            "dni",
            "first_name",
            "last_name",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "avatar",
            "phone",
            "role",
            "date_joined",
            "last_login",
            "is_active",
            "is_superuser",
            "orders",
            "pending_orders_counter",
            "addresses_counter",
            "referred_by",
            "referral_code",
            "referrer_code",
            "reviews_counter",
            "rewards_counter",
            "total_spend",
        ]
        extra_kwargs = {"password": {"write_only": True}}

    def get_orders(self, obj):
        return Order.objects.filter(user=obj).count()

    def get_pending_orders_counter(self, obj):
        return Shipment.objects.filter(customer=obj, status="PENDING").count()

    def get_addresses_counter(self, obj):
        return DeliveryAddress.objects.filter(customer=obj).count()

    def get_reviews_counter(self, obj):
        return ProductReview.objects.filter(user=obj).count()

    def get_rewards_counter(self, obj):
        return sum(
            reward.is_valid() for reward in ReferralDiscount.objects.filter(user=obj)
        )

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        dni = validated_data.pop("dni", None)
        referrer_code = validated_data.pop("referrer_code", None)
        groups_data = validated_data.pop("groups", [])

        if not dni:
            raise serializers.ValidationError({"dni": "Este campo es obligatorio."})

        # Validar código de referido (si lo hay)
        referrer = None
        if referrer_code:
            try:
                referrer = User.objects.get(referral_code=referrer_code)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "referrer_code": f"El código de referido '{referrer_code}' no es válido."
                    }
                )

        # Crear instancia del usuario (aún sin guardar)
        user = self.Meta.model(**validated_data)
        user.dni = dni
        if password:
            user.set_password(password)
        if referrer:
            user.referred_by = referrer

        user.save()

        # Asignar grupos (si aplica)
        for group in groups_data:
            user.groups.add(group)

        # Crear descuentos de referido si aplica
        expiry_date = timezone.now() + timedelta(days=30)

        if referrer:
            ReferralDiscount.objects.update_or_create(
                user=referrer,
                defaults={"has_discount": True, "expires_at": expiry_date},
            )

            ReferralDiscount.objects.update_or_create(
                user=user, defaults={"has_discount": True, "expires_at": expiry_date}
            )
        else:
            # If user isn't referred by someone
            ReferralDiscount.objects.update_or_create(
                user=user, defaults={"has_discount": True, "expires_at": expiry_date}
            )
        return user

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            old_value = getattr(instance, attr, None)
            setattr(instance, attr, value)

        password = validated_data.get("password", None)
        if password:
            instance.set_password(password)

        referrer_code = validated_data.get("referrer_code")
        if referrer_code:
            try:
                referrer = User.objects.get(referral_code=referrer_code)
                instance.referred_by = referrer
            except User.DoesNotExist:
                pass

        instance.save()
        return instance

    def get_total_spend(self, obj):
        total = sum(order.total for order in Order.objects.filter(user=obj))
        return total

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_dni(self, value):
        if User.objects.filter(dni=value).exists():
            raise serializers.ValidationError("DNI already exists.")
        return value

    def validate_referral_code(self, value):
        if value and not User.objects.filter(referral_code=value).exists():
            raise serializers.ValidationError("Invalid referral code.")
        return value
