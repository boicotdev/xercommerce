from rest_framework import serializers
from purchases.models import SuggestedRetailPrice
from reviews.models import ProductReview
from reviews.serializers import ProductReviewSerializer
from users.models import User
from .models import Product, Category, UnitOfMeasure


class BaseImportFile(serializers.Serializer):
    file = serializers.FileField()


class SuggestedRetailPriceSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = SuggestedRetailPrice
        fields = ['id', 'suggested_price', 'purchase_item', 'category']
        depth = 2

    def get_category(self, obj):
        item = obj.purchase_item.product
        return CategorySerializer(Category.objects.filter(product=item).first()).data


class ProductImportSerializer(BaseImportFile):
    pass


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = "__all__"


class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "description",
            "price",
            "discount_price",
            "purchase_price",
            "stock",
            "category",
            "score",
            "recommended",
            "best_seller",
            "tag",
            "quality",
            "weight",
            "slug",
            "unit_of_measurement"
        ]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"
        depth = 2


class ProductSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category"
    )
    category = serializers.SerializerMethodField(read_only=True)
    reviews = serializers.SerializerMethodField(read_only=True)
    weight = serializers.SerializerMethodField(read_only=True)

    def get_category(self, obj):
        return obj.category.name if obj.category else None

    def get_unit_measure(self, obj):
        return obj.measure_unity.unity if obj.measure_unity else None

    def get_reviews(self, obj):
        reviews = ProductReview.objects.filter(product=obj)
        return ProductReviewSerializer(reviews, many=True).data

    def get_weight(self, obj):
        return {"value": obj.weight, "unit": "Gramos"}

    class Meta:
        model = Product
        fields = [
            "name",
            "price",
            "sku",
            "description",
            "stock",
            "category_id",
            "recommended",
            "best_seller",
            "discount_price",
            "main_image",
            "category",
            "score",
            "reviews",
            "tag",
            "quality",
            "weight",
        ]

    def create(self, validated_data):
        sku = validated_data.pop("sku", None)
        if not sku:
            raise serializers.ValidationError({"sku": "This field is required"})
        instance = self.Meta.model(**validated_data)
        instance.sku = sku
        instance.save()
        return instance


class UserDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "dni",
            "email",
            "username",
            "first_name",
            "last_name",
            "phone",
            "avatar",
        ]
