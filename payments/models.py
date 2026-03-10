from django.db import models


class Payment(models.Model):
    PAYMENT_METHODS = (
        ("CASH", "CASH"),
        ("DEBIT_CARD", "DEBIT_CARD"),
        ("CREDIT_CARD", "CREDIT_CARD"),
        ("BANK_TRANSFER", "BANK_TRANSFER"),
        ("NEQUI", "NEQUI"),
        ("ACCOUNT_MONEY", "ACCOUNT_MONEY"),
        ("OTHER", "OTHER"),
    )

    PAYMENT_STATUS = (
        ("APPROVED", "APPROVED"),
        ("PENDING", "PENDING"),
        ("IN_PROCESS", "IN_PROCESS"),
        ("REJECTED", "REJECTED"),
        ("CANCELED", "CANCELED"),
        ("REFUNDED", "REFUNDED"),
        ("CHARGED_BACK", "CHARGED_BACK"),
    )

    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE)
    payment_id = models.BigIntegerField(
        unique=True, null=True, blank=True
    )  # ID de pago de MP
    mercado_pago_order_id = models.CharField(
        max_length=50, default="None"
    )  # order_id de MP
    external_reference = models.CharField(max_length=100, default="None")

    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS, default="PENDING"
    )
    status_detail = models.CharField(max_length=50, default="PENDING")

    payment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_received_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    taxes_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    currency_id = models.CharField(max_length=10, default="COP")

    payment_method = models.CharField(
        max_length=30, choices=PAYMENT_METHODS, default="ACCOUNT_MONEY"
    )
    payment_type = models.CharField(max_length=30, default="CASH")

    payment_date = models.DateTimeField()  # date_approved
    last_updated = models.DateTimeField(auto_now=True, blank=True, null=True)

    # Payer information
    payer_email = models.EmailField(default="None")
    payer_id = models.CharField(max_length=50, default="None")
    payer_identification_type = models.CharField(max_length=10, default="None")
    payer_identification_number = models.CharField(max_length=50, default="None")
    payer_street_name = models.CharField(max_length=255, default="None")
    payer_street_number = models.CharField(max_length=10, default="None")
    payer_zip_code = models.CharField(max_length=20, default="None")

    def __str__(self):
        return f"Payment {self.payment_id} | {self.payment_status} | ${self.payment_amount} | Order {self.order.id}"


class Coupon(models.Model):
    created_by = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.CASCADE
    )
    coupon_code = models.CharField(max_length=30)
    discount = models.IntegerField()
    creation_date = models.DateTimeField(auto_now=True)
    expiration_date = models.DateField()
    is_active = models.BooleanField(default=True)
    discount_type = models.CharField(
        choices=(("PERCENTAGE", "PERCENTAGE"), ("FIXED", "FIXED")), max_length=12
    )

    def is_valid(self):
        from django.utils.timezone import now

        current_date = now().date()
        return self.is_active and self.expiration_date > current_date

    def __str__(self):
        if self.discount_type == "FIXED":
            return f"Coupon {self.coupon_code} | {self.discount_type} | ${self.discount} | Expires: {self.expiration_date}"
        else:
            return f"Coupon {self.coupon_code} | {self.discount_type} | {self.discount}% | Expires: {self.expiration_date}"
