import datetime
import uuid

import mercadopago
from decouple import config
from django.db.transaction import atomic
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView, Response

from carts.models import Cart, ProductCart
from orders.models import Order, OrderProduct
from payments.models import Payment, Coupon
from products.models import Product
from products.permissions import AdminPermissions
from shipments.models import Shipment, DeliveryAddress
from users.models import ReferralDiscount
from utils.utils import send_email, update_bestseller_status, is_first_purchase
from .serializers import PaymentSerializer, CouponSerializer

MP_ACCESS_TOKEN = config("MERCADO_PAGO_ACCESS_TOKEN")
SHIPPING_COST = config("SHIPPING_COST", cast=int, default=5000)


class CreatePaymentPreference(APIView):
    def post(self, request):
        sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
        user = request.user
        items = request.data.get("items", [])
        shipping_info = request.data.pop("shipping_info", None)
        notification_url = request.data.get("notification_url")

        order, _ = Order.objects.get_or_create(user=user, status="PENDING")
        cart, _ = Cart.objects.get_or_create(user=user)

        subtotal = 0
        discount_value = 0
        discount_applied = False
        discount_type = "NONE"
        shipping_cost = 0 if is_first_purchase(user) else SHIPPING_COST

        processed_items = []

        for item in items:
            product = Product.objects.get(sku=item["id"])

            unit_price = float(item["unit_price"])
            quantity = int(item["quantity"])
            item_total = unit_price * quantity
            subtotal += item_total

            # OrderProduct
            order_product, created = OrderProduct.objects.get_or_create(
                order=order,
                product=product,
                defaults={"price": unit_price, "quantity": quantity},
            )
            if not created:
                order_product.quantity = quantity
                order_product.save()

            # ProductCart
            product_cart, created = ProductCart.objects.get_or_create(
                cart=cart, product=product, defaults={"quantity": quantity}
            )
            if not created:
                product_cart.quantity = quantity
                product_cart.save()

            processed_items.append(
                {
                    "id": item["id"],
                    "title": product.name,
                    "quantity": quantity,
                    "currency_id": "COP",
                    "unit_price": unit_price,
                }
            )

        # Verificamos y aplicamos descuento si existe
        try:
            discount = ReferralDiscount.objects.get(user=user)
            if discount.is_valid():
                discount_applied = True
                discount_type = (
                    "FIRST_PURCHASE" if is_first_purchase(user) else "REFERRAL"
                )
                discount_value = round(subtotal * 0.10, 2)

                # Ajustar los precios unitarios proporcionalmente
                descuento_unitario = (subtotal - discount_value) / subtotal
                for item in processed_items:
                    item["unit_price"] = round(
                        item["unit_price"] * descuento_unitario, 2
                    )

                # Marcar el descuento como usado
                discount.has_discount = False
                discount.expires_at = None
                discount.save()

        except ReferralDiscount.DoesNotExist:
            pass  # No discount

        total = round(subtotal - discount_value, 2)

        order.subtotal = subtotal
        order.discount_applied = discount_applied
        order.discount_value = discount_value
        order.discount_type = discount_type
        order.total = total
        order.shipping_cost = shipping_cost
        order.save()

        preference_data = {
            "items": processed_items,
            "payer": {
                "name": f"{user.first_name} {user.last_name}",
                "surname": user.last_name,
                "email": user.email,
                "phone": {"area_code": "57", "number": shipping_info["phone"]},
                "identification": {"type": "CC", "number": user.dni},
                "address": {
                    "zip_code": shipping_info["postalCode"],
                    "street_name": shipping_info["street"],
                    "street_number": shipping_info["id"],
                },
            },
            "shipments": {"cost": SHIPPING_COST, "mode": "not_specified"},
            "back_urls": {
                "success": "https://avoberry.vercel.app/checkout/success/",
                "failure": "https://avoberry.vercel.app/checkout/failure/",
                "pending": "https://avoberry.vercel.app/checkout/pending/",
            },
            "auto_return": "approved",
            "notification_url": notification_url
            or str(config("DEFAULT_NOTIFICATION_URL")),
            "statement_descriptor": "AVOBERRY",
            "external_reference": str(order.id),
            "expires": False,
            "payment_methods": {
                "excluded_payment_methods": [],
                "excluded_payment_types": [],
                "installments": 1,
                "default_installments": 1,
            },
            "currency_id": "COP",
        }

        try:
            preference_response = sdk.preference().create(preference_data)
            if preference_response["status"] != 201:
                return Response(
                    {"error": preference_response["response"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            preference = preference_response["response"]
            return Response(
                {"preference_id": preference.get("id"), "order": order.id},
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            import traceback

            traceback_str = traceback.format_exc()
            return Response(
                {
                    "detail": "Error interno en el servidor",
                    "error": str(e),
                    "trace": traceback_str,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MercadoPagoWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            event_type = request.data.get("type")
            if event_type != "payment":
                return Response({"message": "Event ignored"}, status=status.HTTP_200_OK)

            payment_id = request.data.get("data", {}).get("id")
            if not payment_id:
                return Response(
                    {"error": "Payment ID not provided"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
                payment = sdk.payment().get(payment_id)
                payment_data = payment.get("response", {})
                if not payment_data:
                    raise ValueError("Empty payment data")
            except Exception as e:
                return Response(
                    {"error": f"Error getting payment data: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            info = self.extract_payment_data(payment_data)
            order = Order.objects.filter(id=info["external_reference"]).first()
            if not order:
                return Response(
                    {"error": "Command not found"}, status=status.HTTP_404_NOT_FOUND
                )

            # Create or update the Payment
            payment_obj, created = Payment.objects.update_or_create(
                order=order,
                defaults={
                    "payment_id": info.get("payment_id"),
                    "mercado_pago_order_id": info.get("order_id") or "None",
                    "external_reference": info.get("external_reference") or "None",
                    "payment_status": (info.get("status") or "APPROVED").upper(),
                    "status_detail": info.get("status_detail") or "APPROVED",
                    "payment_amount": round(
                        float(info.get("total_paid_amount") or 0), 2
                    ),
                    "net_received_amount": round(
                        float(info.get("net_received_amount") or 0), 2
                    ),
                    "taxes_amount": round(
                        (
                            float(info.get("total_paid_amount") or 0)
                            - float(info.get("net_received_amount") or 0)
                        ),
                        2,
                    ),
                    "currency_id": info.get("currency_id") or "COP",
                    "payment_method": (
                        info.get("payment_method_id") or "ACCOUNT_MONEY"
                    ).upper(),
                    "payment_type": (info.get("payment_type_id") or "CASH").upper(),
                    "payment_date": info.get("date_approved") or timezone.now(),
                    "payer_email": info.get("payer_email") or "None",
                    "payer_id": str(info.get("payer_id") or "None"),
                    "payer_identification_type": info.get("payer_identification_type")
                    or "None",
                    "payer_identification_number": info.get(
                        "payer_identification_number"
                    )
                    or "None",
                    "payer_street_name": info.get("payer_street_name") or "None",
                    "payer_street_number": str(
                        info.get("payer_street_number") or "None"
                    ),
                    "payer_zip_code": info.get("payer_zip_code") or "None",
                },
            )
            subtotal = order.subtotal
            shipping_cost = order.shipping_cost
            total = round(subtotal + shipping_cost, 2)
            order.status = "PROCESSING"
            order.total = total
            order.save()

            # Create shipment
            try:
                shipment_address = DeliveryAddress.objects.get(
                    pk=int(info.get("payer_street_number"))
                )
            except DeliveryAddress.DoesNotExist:
                return Response(
                    {"error": "Not address related with the user"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            shipping_address = Shipment.objects.create(
                customer=order.user,
                order=order,
                shipment_address=shipment_address.street,
                shipment_city=shipment_address.city,
                zip_code=shipment_address.zip_code,
            )

            with atomic():
                for item in info.get("items", []):
                    sku = item.get("id")
                    quantity = int(item.get("quantity", 0))
                    try:
                        product = Product.objects.select_for_update().get(sku=sku)
                        update_bestseller_status(product, 1)

                        # Only what is available is discounted
                        deducted_quantity = min(product.stock, quantity)

                        if deducted_quantity > 0:
                            product.stock -= deducted_quantity
                            product.save()

                    except Product.DoesNotExist:
                        raise ValueError(f"Producto con SKU {sku} no encontrado")

            # prepare data to send email when payment is success
            items = OrderProduct.objects.filter(order=order)
            context = {
                "user": request.data.get("first_name"),
                "subscriber_name": request.data.get("email"),
                "site_url": "https://avoberry.vercel.app/",
                "year": datetime.datetime.now().year,
                "order_date": order.created_at,
                "customer_name": f"{order.user.first_name} {order.user.last_name}",
                "payment_method": info["payment_method_id"],
                "delivery_date": "Pending",
                "subtotal": payment_obj.payment_amount,
                "shipping_cost": info["shipping_amount"],
                "discount": order.discount_value,
                "total": info["total_paid_amount"],
                "shipping_address": shipping_address,
                "phone": order.user.phone,
                "tracking_number": shipping_address.id,
                "order_url": "https://avoberry.vercel.app/",
                "faq_url": "https://avoberry.vercel.app/contact",
                "contact_url": "https://avoberry.vercel.app/contact",
                "order_items": items,
                "image_url": "https://ecommerce-api-v2-production.up.railway.app",
            }
            send_email(
                "Gracias por tu compra",
                f"{order.user.email}",
                [],
                context,
                "email/order-confirmation.html",
                success_message="Your purchase was created successfully",
            )

            return Response(
                {
                    "message": "Payment successfully received",
                    "payment_id": payment_id,
                    "status": info.get("status"),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            print("Error general:", e)
            return Response(
                {"error": f"Error general: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def extract_payment_data(self, payment_data: dict) -> dict:
        payer_info = payment_data.get("payer", {})
        additional_info = payment_data.get("additional_info", {})
        shipping_info = additional_info.get("payer", {}).get("address", {})
        transaction_details = payment_data.get("transaction_details", {})

        return {
            "payment_id": payment_data.get("id"),
            "order_id": payment_data.get("order", {}).get("id"),
            "external_reference": payment_data.get("external_reference"),
            "status": payment_data.get("status"),
            "status_detail": payment_data.get("status_detail"),
            "date_approved": payment_data.get("date_approved"),
            # Totales
            "transaction_amount": payment_data.get(
                "transaction_amount"
            ),  # Solo productos
            "shipping_amount": payment_data.get("shipping_amount"),  # Solo envío
            "total_paid_amount": transaction_details.get(
                "total_paid_amount"
            ),  # Total con envío
            "net_received_amount": transaction_details.get("net_received_amount"),
            "currency_id": payment_data.get("currency_id"),
            # Métodos de pago
            "payment_type_id": payment_data.get("payment_type_id"),
            "payment_method_id": payment_data.get("payment_method_id"),
            # Info del comprador
            "payer_email": payer_info.get("email"),
            "payer_id": payer_info.get("id"),
            "payer_identification_type": payer_info.get("identification", {}).get(
                "type"
            ),
            "payer_identification_number": payer_info.get("identification", {}).get(
                "number"
            ),
            # Dirección del comprador
            "payer_street_name": shipping_info.get("street_name"),
            "payer_street_number": shipping_info.get("street_number"),
            "payer_zip_code": shipping_info.get("zip_code"),
            # Productos comprados
            "items": additional_info.get("items", []),
        }


class MercadoPagoPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
        request_options = mercadopago.config.RequestOptions()
        request_options.custom_headers = {
            "x-idempotency-key": self.get_idempotency_key(request)
        }

        try:
            user = request.user
            payment_data = self.build_payment_data(request)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        try:

            response = sdk.payment().create(payment_data, request_options)
            payment = response.get("response", {})

            if payment.get("status") != "approved":
                return Response(
                    {"error": "Payment not approved", "details": response},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order = Order.objects.filter(user=user, status="PENDING").first()
            if not order:
                return Response(
                    {"error": "An order associated with the user was not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(payment, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": "Error processing payment", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get_idempotency_key(self, request):
        return request.data.get("idempotency_key", str(uuid.uuid4()))

    def build_payment_data(self, request):
        try:
            payer_data = request.data.get("payer", {})
            identification = payer_data.get("identification", {})

            return {
                "transaction_amount": float(request.data.get("transaction_amount")),
                "token": request.data.get("token"),
                "description": "Products Purchase",
                "installments": int(request.data.get("installments")),
                "payment_method_id": request.data.get("payment_method_id"),
                "issuer_id": request.data.get("issuer_id"),
                "payer": {
                    "email": payer_data.get("email"),
                    "identification": {
                        "type": identification.get("type"),
                        "number": identification.get("number"),
                    },
                },
                "external_reference": str(uuid.uuid4()),
            }

        except (TypeError, ValueError, KeyError) as e:
            raise ValueError(f"Invalid data: {e}")


# class GenerateSalesReportAPIView(APIView):
#     permission_classes = [IsAuthenticated]
#
#     def get(self, request, order_id):
#         """Genera un reporte PDF para una venta específica."""
#         try:
#             Order.objects.get(id=order_id, user=request.user)
#         except Order.DoesNotExist:
#             return Response({'You dont have permission to perform this action'}, status=status.HTTP_403_FORBIDDEN)
#         try:
#             sale = Payment.objects.select_related("order").get(order__id=order_id)
#             order = sale.order  # Ya se obtuvo con select_related
#             order_products = order.orderproduct_set.all()
#             total = sum([item.price * item.quantity for item in order_products])
#             total += 5000
#             # Formatear el total con separación cada 3 cifras (estilo colombiano)
#             total_formatted = "{:,.0f}".format(sale.payment_amount).replace(",", ".")
#         except Payment.DoesNotExist:
#             return HttpResponse("Pago no encontrado", status=404)
#         except Order.DoesNotExist:
#             return HttpResponse("Orden no encontrada", status=404)
#
#         # Renderizar la plantilla HTML con datos
#         html_string = render_to_string("payments/sales-report.html", {"sale": sale,
#                                                                                 "items": order_products,
#                                                                                 "total": total_formatted})
#
#         # Generar PDF
#         pdf_file = BytesIO()
#         HTML(string=html_string).write_pdf(pdf_file)
#
#         # Responder con el PDF
#         pdf_file.seek(0)
#         response = HttpResponse(pdf_file, content_type="application/pdf")
#         response["Content-Disposition"] = f'attachment; filename="Factura_{order.id}.pdf"'
#         return response


# cart details
class PaymentDetailsViewView(APIView):
    def get(self, request):
        order_id = request.query_params.get("order", None)
        if not order_id:
            return Response(
                {"message": "Payment ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            payment = Payment.objects.get(order=order_id)
            serializer = PaymentSerializer(payment, many=False)
            return Response(data=serializer.data, status=status.HTTP_200_OK)
        except Payment.DoesNotExist:
            return Response(
                {"message": "Payment not found"}, status=status.HTTP_404_NOT_FOUND
            )

        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CouponsCreateView(APIView):
    permission_classes = [AdminPermissions]

    def post(self, request):
        coupon_code = request.data.get("coupon_code", None)
        discount = request.data.get("discount", None)
        discount_type = request.data.get("discount_type", None)
        expiration_date = request.data.get("expiration_date", None)

        if not coupon_code or not discount or not discount_type or not expiration_date:
            return Response(
                {"message": "All fields are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            serializer = CouponSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CouponsAdminRetrieveView(APIView):
    """
    Only admin user can access
    - Retrieve all coupons available
    """

    permission_classes = [AdminPermissions]

    def get(self, request):
        try:
            coupons = Coupon.objects.all()
            coupons_serializer = CouponSerializer(coupons, many=True)
            return Response(coupons_serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CouponUpdateView(APIView):
    permission_classes = [AdminPermissions]

    def put(self, request):
        coupon_id = request.data.get("id", None)
        if not coupon_id:
            return Response(
                {"message": "Coupon ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            coupon = Coupon.objects.get(pk=coupon_id)
            serializer = CouponSerializer(coupon, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Coupon.DoesNotExist:
            return Response({"message": f"Coupon ID {coupon_id} not found!"})
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CouponDeleteView(APIView):
    permission_classes = [AdminPermissions]

    def post(self, request):
        coupon_code = request.data.get("coupon_code", None)

        if not coupon_code:
            return Response(
                {"message": "Coupon code is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            coupon = Coupon.objects.get(coupon_code=coupon_code)
            coupon.delete()
            return Response(
                {"message": f"Coupon deleted successfully."},
                status=status.HTTP_204_NO_CONTENT,
            )

        except Coupon.DoesNotExist:
            return Response(
                {"message": f"Coupon code {coupon_code} not found!"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CouponCodeCheckView(APIView):
    """
    Validates a given discount coupon and returns the applicable discount.

    If the discount type is "FIXED", the function returns the total discount amount.
    If the discount type is "PERCENTAGE", it returns the percentage discount.

    Returns:
        dict: A dictionary containing:
            - 'discount' (str): The discount value (amount or percentage).
            - 'valid' (bool): Indicates whether the coupon is valid.
            - 'type' (str): Indicates the discount type
    """

    def post(self, request):
        coupon_code = request.data.get("coupon_code", None)
        if not coupon_code:
            return Response(
                {"message": "Coupon code is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            coupon = Coupon.objects.get(coupon_code=coupon_code)
            if coupon.is_valid():
                return Response(
                    {
                        "valid": True,
                        "type": coupon.discount_type,
                        "discount": coupon.discount,
                    },
                    status=status.HTTP_200_OK,
                )
            return Response(
                {"valid": False, "error": "Cupón expirado o inactivo"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Coupon.DoesNotExist:
            return Response(
                {"message": f"Coupon code {coupon_code} not found!"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
