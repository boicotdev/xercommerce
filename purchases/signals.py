from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order, OrderProduct, StockMovement
from .models import Purchase, MissingItems, PurchaseItem


@receiver(post_save, sender=PurchaseItem)
def update_purchase_totals(sender, instance, created, **kwargs):

    if created:
        purchase = instance.purchase
        purchase.update_totals()


@receiver(post_save, sender=PurchaseItem)
def create_stock_movement_record(sender, instance, created, **kwargs):
    """
    Create a `StockMovement` record a record must be are these options
    ['IN', 'OUT', 'ADJUST']
    in this case we only are working with IN value because this signal is only for purchases pourpouses
    """
    try:
        if created:
            product = instance.product
            product.stock += (
                instance.quantity
            )  # Update the stock of the product generally.
            product.save()
            stock_movement = StockMovement(
                product=product,
                movement_type="IN",  # Product is entring to the system
                quantity=instance.quantity,
                reason="SOURCING",
            )
            stock_movement.save()
    except Exception as e:
        pass


@receiver(post_save, sender=Purchase)
def calculate_missing_items(sender, instance, created, **kwargs):
    """
    Al crear una nueva compra (Purchase), recalcula los productos faltantes (MissingItems)
    en base a las órdenes en estado PENDING o PROCESSING.
    """
    try:
        if created:
            # Obtener todas las órdenes pendientes o en proceso
            pending_orders = Order.objects.filter(status__in=["PENDING", "PROCESSING"])

            for order in pending_orders:
                order_products = OrderProduct.objects.filter(order=order)

                for op in order_products:

                    product = op.product
                    requested_qty = op.quantity
                    stock = (
                        product.stock
                    )  # suponiendo que tu modelo Product tiene este campo

                    # Calcular faltantes
                    missing_qty = max(0, requested_qty - stock)

                    # Actualizar o crear registro de MissingItem si hay déficit
                    if missing_qty > 0:
                        mi, created = MissingItems.objects.update_or_create(
                            product=product,
                            order=order,
                            defaults={"missing_quantity": missing_qty, "stock": stock},
                        )
                        if created:
                            print(
                                f"➕ MissingItem creado para '{product.name}' (orden {order.id})"
                            )
                        else:
                            print(
                                f"♻️ MissingItem actualizado para '{product.name}' (orden {order.id})"
                            )
    except Exception as e:
        print(f"❌ Error al calcular productos faltantes: {e}")
