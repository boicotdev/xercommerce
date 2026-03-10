import uuid

from django.core.validators import RegexValidator
from django.db import models

from orders.models import Order


def set_tracking_number():
    return f'AVB-{str(uuid.uuid4())[:15].replace("-", "")}'.upper()


class Shipment(models.Model):
    id = models.CharField(max_length=100, default=set_tracking_number, primary_key=True)
    customer = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="shipments"
    )
    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name="shipment"
    )
    shipment_date = models.DateTimeField(auto_now_add=True)
    shipment_address = models.CharField(max_length=255)
    shipment_city = models.CharField(max_length=50)
    postal_code_validator = RegexValidator(
        regex=r"^\d{4,10}$",
        message="El código postal debe contener entre 4 y 10 dígitos.",
    )
    zip_code = models.CharField(max_length=10, validators=[postal_code_validator])

    PENDING = "PENDING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

    SHIPMENT_STATUS_CHOICES = [
        (PENDING, PENDING),
        (SHIPPED, SHIPPED),
        (DELIVERED, DELIVERED),
        (CANCELLED, CANCELLED),
    ]

    status = models.CharField(
        max_length=10, choices=SHIPMENT_STATUS_CHOICES, default=PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Shipment {self.id} | {self.get_status_display()} | {self.shipment_address}, {self.shipment_city}"


class DeliveryAddress(models.Model):
    customer = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="delivery_address"
    )
    street = models.CharField(max_length=50, blank=True, null=True)
    country = models.CharField(max_length=30, default="Colombia")
    city = models.CharField(max_length=30, default="Bogotá")
    zip_code = models.CharField(max_length=10)
    quarter = models.CharField(max_length=50)
    recipient = models.CharField(max_length=40)
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.customer.username} - {self.street}"
