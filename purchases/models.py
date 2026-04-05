import random
import string
from datetime import datetime
import uuid
from django.db import models

from products.models import Product, UnitOfMeasure
from orders.models import Order


class Purchase(models.Model):
    id = models.CharField(max_length=50, primary_key=True)
    purchased_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_admin",
    )
    additional_costs = models.FloatField(default=0)  # freight, taxes, etc
    purchase_date = models.DateTimeField(auto_now_add=False, blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True)
    total_amount = models.FloatField(default=0)  # Total purchase amount
    global_sell_percentage = models.FloatField(default=10)  # Global sell percentage
    estimated_profit = models.FloatField(default=0)  # Estimated profit

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = generate_unique_id("000", purchase="True")
        super().save(*args, **kwargs)

    def update_totals(self):
        """Recalculates the total purchase amount and the estimated profit."""
        total_cost = sum(item.subtotal() for item in self.purchase_items.all())
        self.total_amount = total_cost + self.additional_costs
        self.estimated_profit = sum(
            item.estimated_profit() for item in self.purchase_items.all()
        )
        self.save()

    # NUEVOS MÉTODOS - No afectan lógica existente
    def get_total_cost_without_expenses(self):
        """Total purchase cost without additional costs."""
        return sum(item.subtotal() for item in self.purchase_items.all())
    
    def get_total_weight_kg(self):
        """Total weight in kg for all items in purchase."""
        total = 0
        for item in self.purchase_items.all():
            total += item.get_total_weight_kg()
        return total
    
    def get_total_weight_lbs(self):
        """Total weight in pounds for all items."""
        return self.get_total_weight_kg() * 2.20462

    def __str__(self):
        return f"Purchase {self.id} | Total: ${self.total_amount} | Profit: ${self.estimated_profit}"

    class Meta:
        ordering = ['-purchase_date']


class SuggestedRetailPrice(models.Model):
    purchase_item = models.ForeignKey(
        "PurchaseItem",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="related_product",
    )
    suggested_price = models.DecimalField(default=0, max_digits=12, decimal_places=2)
    
    price_type = models.CharField(
        max_length=20,
        choices=[
            ('unit', 'Por unidad'),
            ('kg', 'Por kilogramo'),
            ('lb', 'Por libra'),
        ],
        default='unit',
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):
        """Auto-calculate suggested price based on type if price_type is set."""
        if self.purchase_item and self.price_type:
            if self.price_type == 'unit':
                self.suggested_price = self.purchase_item.sale_price_per_unit()
            elif self.price_type == 'kg':
                self.suggested_price = self.purchase_item.sale_price_per_kg()
            elif self.price_type == 'lb':
                self.suggested_price = self.purchase_item.sale_price_per_lb()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        if self.purchase_item.product is None:
            return f"Uknown product name - {self.suggested_price}"
        type_display = f" ({self.get_price_type_display()})" if self.price_type else ""
        return f"{self.purchase_item.product.name} - ${self.suggested_price}{type_display}"

class PurchaseItem(models.Model):
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name="purchase_items"
    )
    product = models.ForeignKey(
        Product, blank=True, null=True, on_delete=models.SET_NULL
    )
    quantity = models.IntegerField()
    purchase_price = models.FloatField()  # Purchase price per item
    sell_percentage = models.FloatField(null=True, blank=True)
    unit_measure = models.ForeignKey(
        UnitOfMeasure, blank=True, null=True, on_delete=models.SET_NULL
    )

    def get_sell_percentage(self):
        """
        Gets the sell percentage:
        uses the item percentage if defined, otherwise uses the Purchase global percentage.
        """
        return (
            self.sell_percentage
            if self.sell_percentage is not None
            else self.purchase.global_sell_percentage
        )

    def subtotal(self):
        """Calculates the total purchase cost for this product."""
        return self.quantity * float(self.purchase_price)

    def estimated_profit(self):
        """Calculates the estimated profit based on the sell percentage."""
        sell_percentage = self.get_sell_percentage()
        profit_per_unit = self.purchase_price * (sell_percentage / 100)
        return self.quantity * profit_per_unit

    def sale_price_per_weight(self):
        """
        Calculates the sale price per unit of measure.
        Original tenía error en la fórmula.
        """
        if not self.unit_measure or self.unit_measure.weight == 0:
            return 0

        sell_percentage = self.get_sell_percentage()
        
        # Costo total incluyendo gastos adicionales
        total_cost_with_expenses = self.get_cost_with_additional_expenses()
        
        # Precio de venta total con margen
        total_sale_price = total_cost_with_expenses * (1 + sell_percentage / 100)
        
        # Precio por unidad de medida
        price_per_unit = total_sale_price / self.quantity
        
        return price_per_unit

    def get_total_weight_kg(self):
        """Returns total weight in kg for this purchase item."""
        if not self.unit_measure or self.unit_measure.weight == 0:
            return 0
        return self.unit_measure.weight * self.quantity

    def get_total_weight_lbs(self):
        """Returns total weight in pounds for this purchase item."""
        return self.get_total_weight_kg() * 2.20462

    def get_cost_with_additional_expenses(self):
        """
        Calculates the cost including proportionally assigned additional expenses.
        """
        purchase_total = self.purchase.get_total_cost_without_expenses()
        if purchase_total == 0:
            return self.subtotal()
        
        proportion = self.subtotal() / purchase_total
        additional_expenses_assigned = self.purchase.additional_costs * proportion
        
        return self.subtotal() + additional_expenses_assigned

    def sale_price_total(self):
        """
        Calculates the total sale price for all items of this product,
        including margin and distributed additional expenses.
        """
        cost_with_expenses = self.get_cost_with_additional_expenses()
        sell_percentage = self.get_sell_percentage()
        
        # Apply margin (sell_percentage is the profit margin)
        sale_price_total = cost_with_expenses * (1 + sell_percentage / 100)
        
        return sale_price_total

    def sale_price_per_unit(self):
        """Sale price per unit of measure (per bulto, per caja, etc.)."""
        if self.quantity == 0:
            return 0
        return self.sale_price_total() / self.quantity

    def sale_price_per_kg(self):
        """Sale price per kilogram."""
        total_weight_kg = self.get_total_weight_kg()
        if total_weight_kg == 0:
            return 0
        return self.sale_price_total() / total_weight_kg

    def sale_price_per_lb(self):
        """Sale price per pound."""
        return self.sale_price_per_kg() / 2.20462

    def estimated_profit_with_expenses(self):
        """Calculates estimated profit considering additional expenses."""
        sell_percentage = self.get_sell_percentage()
        cost_with_expenses = self.get_cost_with_additional_expenses()
        profit = cost_with_expenses * (sell_percentage / 100)
        return profit

    def __str__(self):
        if self.product:
            return (
                f"{self.quantity}x {self.product.name} "
                f"@ ${self.purchase_price} (Sell %: {self.get_sell_percentage()}%)"
            )
        return (
            f"{self.quantity}x Unknown "
            f"@ ${self.purchase_price} (Sell %: {self.get_sell_percentage()}%)"
        )

def generate_unique_id(user_dni, purchase=False):
    """
    Generates a unique ID with the following formats:
    - Order:   "ECCXX9YYYYYYYY" (XX = letters, 9 = number, YYYYYYYY = DNI)
    - Purchase: "CMP-ECCXX9YY" (XX = letters, 9 = number, YY = last 2 digits of DNI)
    """

    while True:
        if purchase:
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            rand = uuid.uuid4().hex[:6].upper()
            unique_id = f"CMP-{ts}-{rand}"
            if not Purchase.objects.filter(id=unique_id).exists():
                return unique_id

        else:
            # Prefix for orders: ECCXX9YYYYYYYY
            prefix = (
                f"{random.choice(string.ascii_uppercase)}"
                f"{random.choice(string.ascii_uppercase)}"
                f"{random.randint(0, 9)}"
            )
            unique_id = f"ECC{prefix}{user_dni}"

            if not Order.objects.filter(id=unique_id).exists():
                return unique_id


class MissingItems(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="missing_item"
    )
    last_updated = models.DateTimeField(auto_now_add=True)
    stock = models.IntegerField(default=1)
    missing_quantity = models.IntegerField(default=0)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="pending_order"
    )

    def __str__(self):
        return (
            f"Item {self.product.sku} | "
            f"Order {self.order.id} | "
            f"Missing {self.missing_quantity}"
        )
