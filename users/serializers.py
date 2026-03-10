from calendar import monthrange
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.hashers import check_password
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from orders.models import Order
from products.models import Product, Category, UnitOfMeasure
from reviews.models import ProductReview
from shipments.models import DeliveryAddress, Shipment
from .models import User, ReferralDiscount, NewsletterSubscription, UserProfileSettings
from purchases.models import Purchase



class UploadUsersFileSerializer(serializers.Serializer):
    file = serializers.FileField()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    We're using rest_framework_simplejwt to handle authentications
    We're using email field to user identificate
      - params: {"email": "user email", "password": "user password"}
      - returns: {"access": "an access token", "refresh": "a refresh access token"}

    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["is_superuser"] = user.is_superuser

        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["dni"] = self.user.dni
        data["role"] = self.user.role
        data["is_superuser"] = self.user.is_superuser

        return data


class BulkCreateUserSerializer(serializers.ModelSerializer):
    referral_code = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = [
            "dni",
            "first_name",
            "last_name",
            "username",
            "phone",
            "email",
            "role",
            "password",
            "referral_code",
        ]


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


class AdminDashboardSerializer(serializers.ModelSerializer):
    orders = serializers.SerializerMethodField(read_only=True)
    revenue = serializers.SerializerMethodField(read_only=True)
    customers = serializers.SerializerMethodField(read_only=True)
    purchases = serializers.SerializerMethodField(read_only=True)
    active_products = serializers.SerializerMethodField(read_only=True)
    categories = serializers.SerializerMethodField(read_only=True)
    measures = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            "dni",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "last_login",
            "orders",
            "revenue",
            "purchases",
            "customers",
            "active_products",
            'categories',
            'measures'
        ]

    def _get_month_range(self, months_ago=0):
        """Devuelve el rango de fechas de un mes anterior"""
        today = timezone.now()
        first_day_this_month = today.replace(day=1)
        for _ in range(months_ago):
            first_day_this_month = (first_day_this_month - timedelta(days=1)).replace(
                day=1
            )
        last_day = first_day_this_month.replace(
            day=monthrange(first_day_this_month.year, first_day_this_month.month)[1]
        )
        return first_day_this_month, last_day

    def _calculate_change(self, current, previous, total):
        """Calcula el cambio porcentual entre valores y añade el total global"""
        epsilon = Decimal("1e-5")
        current = Decimal(current)
        previous = Decimal(previous)

        change = ((current - previous) / (previous + epsilon)) * Decimal(100)
        return {
            "current": int(current),
            "previous": int(previous),
            "percentage_change": float(
                change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            ),
            "total": int(total),
        }
    def get_measures(self, obj):
        data = []
        measures = UnitOfMeasure.objects.all()
        for ms in measures:
            data.append({'id': ms.id, 'name': ms.unity, 'weight': ms.weight, 'value': 'Lbs'})
        return data

    def get_categories(self, obj):
        categories_list = []
        categories = Category.objects.all()
        for ca in categories:
            categories_list.append(
                {'id': ca.id, 'name': ca.name}
            )

        return categories_list

    def get_orders(self, obj):
        current_start, current_end = self._get_month_range(0)
        previous_start, previous_end = self._get_month_range(1)

        current_count = Order.objects.filter(
            created_at__range=(current_start, current_end)
        ).count()
        previous_count = Order.objects.filter(
            created_at__range=(previous_start, previous_end)
        ).count()
        total = Order.objects.all().count()

        return self._calculate_change(current_count, previous_count, total)

    def get_revenue(self, obj):
        current_start, current_end = self._get_month_range(0)
        previous_start, previous_end = self._get_month_range(1)

        current_total = (
            Order.objects.filter(
                created_at__range=(current_start, current_end)
            ).aggregate(total=Sum("total"))["total"]
            or 0
        )
        previous_total = (
            Order.objects.filter(
                created_at__range=(previous_start, previous_end)
            ).aggregate(total=Sum("total"))["total"]
            or 0
        )
        total = Order.objects.aggregate(total=Sum("total"))["total"] or 0

        return self._calculate_change(current_total, previous_total, total)

    def get_customers(self, obj):
        current_start, current_end = self._get_month_range(0)
        previous_start, previous_end = self._get_month_range(1)

        current = User.objects.filter(
            role="customer", date_joined__range=(current_start, current_end)
        ).count()
        previous = User.objects.filter(
            role="customer", date_joined__range=(previous_start, previous_end)
        ).count()
        total = User.objects.filter(role="customer").count()

        return self._calculate_change(current, previous, total)

    def get_purchases(self, obj):
        return Purchase.objects.all().count()

    def get_active_products(self, obj):
        return Product.objects.filter(stock__gt=25).count()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not check_password(value, user.password):
            raise serializers.ValidationError("Passwords don't match")
        return value

    def validate(self, data):
        if data["new_password"] != data["new_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Las contraseñas no coinciden"}
            )
        return data

    def update_password(self, user):
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class UserProfileSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfileSettings
        fields = "__all__"


class NewsletterSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscription
        fields = "__all__"
