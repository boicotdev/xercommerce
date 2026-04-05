from django.db import transaction
from orders.models import StockMovement
from products.models import Product
from purchases.models import SuggestedRetailPrice

class StockMoventSignal:
    def __init__(self, type: str = "IN") -> None:
        self.movement_type = type

    def bulk_create(self, items):
        parsed_items = []
        for prod in items:
            if not isinstance(prod.product, Product):
                raise TypeError("prod must be an Product instance")
            product = prod.product
            parsed_items.append(
                StockMovement(
                    product=product,
                    movement_type=self.movement_type,
                    quantity=prod.quantity,
                    reason="SOURCING",
                )
            )
        with transaction.atomic():
            StockMovement.objects.bulk_create(parsed_items)


class RetailSuggestedPriceService:

    def __init__(self) -> None:
        pass

    def bulk_create(self, purchase_items, price_types=['unit', 'kg', 'lb']):
        """
        Crea precios sugeridos para los items de compra.
        
        Args:
            purchase_items: QuerySet o lista de PurchaseItem
            price_types: Lista de tipos de precio a generar ('unit', 'kg', 'lb')
                        Por defecto genera los tres tipos.
        """
        items = []
        seen_keys = set()  # Cambiado para permitir múltiples tipos por producto
        
        for purchase_item in purchase_items:
            if not hasattr(purchase_item, 'product') or not purchase_item.product:
                continue
                
            # Verificar que sea instancia de PurchaseItem
            if purchase_item.__class__.__name__ != 'PurchaseItem':
                raise TypeError("purchase_items must contain PurchaseItem instances")
            
            for price_type in price_types:
                # Crear clave única por producto + tipo de precio
                key = f"{purchase_item.product.sku}_{price_type}"
                
                if key not in seen_keys:
                    seen_keys.add(key)
                    
                    # Calcular precio según el tipo
                    suggested_price = self._calculate_price_by_type(purchase_item, price_type)
                    
                    if suggested_price > 0:  # Solo guardar si el precio es válido
                        items.append(
                            SuggestedRetailPrice(
                                purchase_item=purchase_item,
                                suggested_price=suggested_price,
                                price_type=price_type,
                            )
                        )
        
        # Guardar en transacción atómica
        with transaction.atomic():
            if items:
                SuggestedRetailPrice.objects.bulk_create(items)
        
        return len(items)  # Retornar cantidad de precios creados

    def _calculate_price_by_type(self, purchase_item, price_type):
        """
        Calcula el precio según el tipo solicitado.
        """
        if price_type == 'unit':
            # Precio por unidad de medida (bulto, caja, etc.)
            return purchase_item.sale_price_per_unit()
        elif price_type == 'kg':
            # Precio por kilogramo
            return purchase_item.sale_price_per_kg()
        elif price_type == 'lb':
            # Precio por libra
            return purchase_item.sale_price_per_lb()
        else:
            raise ValueError(f"Invalid price_type: {price_type}. Use 'unit', 'kg', or 'lb'")

    def create_for_purchase(self, purchase, price_types=['unit', 'kg', 'lb']):
        """
        Crea precios sugeridos para todos los items de una compra.
        
        Args:
            purchase: Instancia de Purchase
            price_types: Lista de tipos de precio a generar
        """
        purchase_items = purchase.purchase_items.select_related('product', 'unit_measure').all()
        return self.bulk_create(purchase_items, price_types)

    def update_or_create(self, purchase_item, price_types=['unit', 'kg', 'lb']):
        """
        Actualiza o crea precios sugeridos para un purchase_item específico.
        
        Args:
            purchase_item: Instancia de PurchaseItem
            price_types: Lista de tipos de precio a generar/actualizar
        """
        created_count = 0
        updated_count = 0
        
        for price_type in price_types:
            suggested_price = self._calculate_price_by_type(purchase_item, price_type)
            
            if suggested_price <= 0:
                continue
            
            _, created = SuggestedRetailPrice.objects.update_or_create(
                purchase_item=purchase_item,
                price_type=price_type,
                defaults={'suggested_price': suggested_price}
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        return {
            'created': created_count,
            'updated': updated_count,
            'total': created_count + updated_count
        }

    def delete_for_purchase_item(self, purchase_item, price_types=None):
        """
        Elimina precios sugeridos para un purchase_item.
        
        Args:
            purchase_item: Instancia de PurchaseItem
            price_types: Lista de tipos a eliminar (None = todos)
        """
        queryset = SuggestedRetailPrice.objects.filter(purchase_item=purchase_item)
        
        if price_types:
            queryset = queryset.filter(price_type__in=price_types)
        
        deleted_count, _ = queryset.delete()
        return deleted_count

    def get_prices_for_item(self, purchase_item):
        """
        Obtiene todos los precios sugeridos para un purchase_item.
        
        Returns:
            Dict con precios por tipo
        """
        prices = SuggestedRetailPrice.objects.filter(purchase_item=purchase_item)
        
        result = {
            'unit': None,
            'kg': None,
            'lb': None,
            'calculated': {
                'unit': purchase_item.sale_price_per_unit(),
                'kg': purchase_item.sale_price_per_kg(),
                'lb': purchase_item.sale_price_per_lb(),
            }
        }
        
        for price in prices:
            if price.price_type:
                result[price.price_type] = float(price.suggested_price)
        
        return result
