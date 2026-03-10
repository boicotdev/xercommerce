from django.db import transaction
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product, UnitOfMeasure
from purchases.models import Purchase, PurchaseItem, MissingItems
from users.models import User
from purchases.serializers import (
    PurchaseItemSerializer,
    PurchaseSerializer,
    MissingItemSerializer,
)
from purchases.services.bulk_create_stock_movement import (
    RetailSuggestedPriceService,
    StockMoventSignal,
)


class PurchaseDeleteView(APIView):
    """
    Handle purchase deletion
    """

    permission_classes = [IsAdminUser]

    def delete(self, request):
        purchase_id = request.data.get("purchase_id")
        if not purchase_id:
            return Response(
                {"error": "Purchase ID is missing"}, status.HTTP_400_BAD_REQUEST
            )
        try:
            purchase = Purchase.objects.get(id=purchase_id)
            purchase.delete()
            return Response(
                {"message": "Purchase was deleted successfully"},
                status=status.HTTP_204_NO_CONTENT,
            )
        except Purchase.DoesNotExist:
            return Response(
                {"error": f"Purchase with ID not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PurchaseItemAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        serializer = PurchaseItemSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PurchaseListView(ListAPIView):
    """
    List all purchases
    """

    permission_classes = [IsAdminUser]
    queryset = Purchase.objects.all().order_by(
        "-purchase_date"
    )  # Últimas compras primero
    serializer_class = PurchaseSerializer


class PurchaseDetailView(RetrieveAPIView):
    """
    Retrieve details of a specific purchase
    """

    permission_classes = [IsAdminUser]
    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer
    lookup_field = "id"

    def get(self, request, *args, **kwargs):
        try:
            purchase = self.get_object()
            serializer = self.get_serializer(purchase)
            return Response(serializer.data)
        except Purchase.DoesNotExist:
            return Response(
                {"error": "Purchase not found"}, status=status.HTTP_404_NOT_FOUND
            )


class RetrieveMissingItemsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            queryset = MissingItems.objects.all()
            paginator = LimitOffsetPagination()
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            serializer = MissingItemSerializer(paginated_queryset, many=True)
            return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PurchaseCreateUpdateView(APIView):
    """
    Handle purchases creation and updates
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        print(request.data)
        required_fields = {"purchase_date", "global_sell_percentage"}
        missing_fields = required_fields - request.data.keys()
        if missing_fields:
            return Response(
                {"error": f"Missing fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        global_sell_percentage = request.data.get(
            "global_sell_percentage", 10
        )  # Default 10%
        if global_sell_percentage < 10:
            return Response(
                {"error": "Global sell percentage must be at least 10%"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        items_data = request.data.get("items", [])
        purchase_date = request.data.get("purchase_date")
        additional_costs = request.data.get('additional_costs', 0)
        #
        if not items_data:
            return Response(
                {"error": "At least one purchase item is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(items_data) > 0:

            try:
                with transaction.atomic():
                    # Crear la compra
                    purchase = Purchase.objects.create(
                        purchased_by_id=request.user,
                        global_sell_percentage=global_sell_percentage,
                        purchase_date=purchase_date,
                        additional_costs = additional_costs,
                    )
                    print('printed before save purchase.')
                    purchase.save()

                    print('printed after save purchase.')

                    purchase_items = []
                    for item in items_data:
                        product_sku = item.get("product")
                        quantity = item.get("quantity")
                        purchase_price = item.get("purchase_price")
                        sell_percentage = item.get("sell_percentage")
                        unit_measure = item.get("unity")

                        if not all(
                            [product_sku, quantity, purchase_price, unit_measure]
                        ):  

                            return Response(
                                {
                                    "error": "Each item must have product, quantity, purchase_price, and unit_measure."
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        print('Print debug before get product line 181')
                        product = Product.objects.get(sku=product_sku)
                        unit_measure = UnitOfMeasure.objects.get(pk=unit_measure)

                        purchase_items.append(
                                PurchaseItem(
                                    purchase=purchase,
                                    product=product,
                                    quantity=quantity,
                                    purchase_price=purchase_price,
                                    sell_percentage=sell_percentage,
                                    unit_measure=unit_measure,
                                    )
                                )

                    PurchaseItem.objects.bulk_create(purchase_items)
                    print('Print debug before get product line 197')
                    movements = StockMoventSignal()
                    service = RetailSuggestedPriceService()
                    movements.bulk_create(purchase_items)
                    service.bulk_create(
                        purchase_items
                    )  # We're making a record with suggested prices by product
                    purchase.update_totals()  # Update totals and estimated earnings

                    return Response(
                        PurchaseSerializer(purchase).data,
                        status=status.HTTP_201_CREATED,
                    )

            except Exception as e:
                print('Error printed at line 211', e)
                return Response(
                    {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            except UnitOfMeasure.DoesNotExist:
                print('Unit of measurements not exist')
                return Response(
                    {"error": "One or more unit measures do not exist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    def put(self, request):
        purchase_id = request.data.get("purchase_id")

        if not purchase_id:
            return Response(
                {"error": "purchase_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            purchase = Purchase.objects.get(id=purchase_id)
        except Purchase.DoesNotExist:
            return Response(
                {"error": "Purchase not found"}, status=status.HTTP_404_NOT_FOUND
            )

        global_sell_percentage = request.data.get(
            "global_sell_percentage", purchase.global_sell_percentage
        )
        if global_sell_percentage < 10:
            return Response(
                {"error": "Global sell percentage must be at least 10%"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        items_data = request.data.get("items", [])

        if not items_data:
            return Response(
                {"error": "At least one purchase item is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                # Actualizar la compra
                purchase.global_sell_percentage = global_sell_percentage
                purchase.save()

                # Eliminar los items anteriores y agregar los nuevos
                purchase.purchase_items.all().delete()

                purchase_items = []
                for item in items_data:
                    product_sku = item.get("product")
                    quantity = item.get("quantity")
                    purchase_price = item.get("purchase_price")
                    sell_percentage = item.get(
                        "sell_percentage", purchase.global_sell_percentage
                    )
                    unit_measure = item.get("unity")

                    if not all([product_sku, quantity, purchase_price, unit_measure]):
                        return Response(
                            {
                                "error": "Each item must have product, quantity, purchase_price, and unit_measure."
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    product = Product.objects.get(sku=product_sku)
                    unit_measure = UnitOfMeasure.objects.get(pk=unit_measure)

                    purchase_item = PurchaseItem(
                        purchase=purchase,
                        product=product,
                        quantity=quantity,
                        purchase_price=purchase_price,
                        sell_percentage=sell_percentage,
                        unit_measure=unit_measure,
                    )
                    purchase_items.append(purchase_item)

                PurchaseItem.objects.bulk_create(purchase_items)
                purchase.update_totals()  # Recalcular totales

                return Response(
                    PurchaseSerializer(purchase).data, status=status.HTTP_200_OK
                )

        except Product.DoesNotExist:
            return Response(
                {"error": "One or more products do not exist."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except UnitOfMeasure.DoesNotExist:
            return Response(
                {"error": "One or more unit measures do not exist."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
