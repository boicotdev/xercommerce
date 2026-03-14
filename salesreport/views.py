from datetime import datetime, timedelta
from calendar import month_abbr
from django.db.models import Sum, Count, F
from django.utils.timesince import timesince

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from salesreport.serializers.serializers import (
    CustomerSegmentsAnalyticsSerializer,
    RecentActivityAnalyticsSerializer,
    SalesDataReportSerializer,
    TopProductsAnalyticsSerializer,
)
from .serializers.report_params import ReportParamsSerializer
from .services.sales_report import SalesReportService
from .services.stock_report import StockReportService
from users.models import User
from payments.models import Payment
from orders.models import OrderProduct, Order


class BaseReportHandler:
    def __init__(self, serializer, service) -> None:
        self.serializer = serializer
        self.service = service
        self.__data = self.serializer.validated_data
        self.result = self.service.generate(
            self.__data["start_date"],
            self.__data["end_date"],
        )


class ReportsAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        report_type = request.query_params.get("type")
        serializer = ReportParamsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        result = None
        data = serializer.validated_data

        # TODO: Save the report data inside of database.
        if report_type == "sales":
            service = SalesReportService(group_by=data["group_by"])
            report = BaseReportHandler(serializer, service)
            result = report.result
            return Response(result, status=status.HTTP_200_OK)
        else:
            service = StockReportService(group_by=data["group_by"])
            report = BaseReportHandler(serializer, service)
            result = report.result
            return Response(result, status=status.HTTP_200_OK)


class AnalyticsSalesReportsAPIView(APIView):
    # permission_classes = [IsAdminUser]

    def get(self, request):
        now = datetime.now()
        year = now.year
        current_month = now.month
        prev_month = current_month - 1 or 12

        # ===============================
        # 📊 SALES DATA
        # ===============================
        payments = (
            Payment.objects.filter(payment_date__year=year)
            .values("payment_date__month")
            .annotate(revenue=Sum("payment_amount"), orders=Count("id"))
        )

        customers = (
            User.objects.filter(date_joined__year=year)
            .values("date_joined__month")
            .annotate(customers=Count("dni"))
        )

        payments_map = {p["payment_date__month"]: p for p in payments}
        customers_map = {c["date_joined__month"]: c["customers"] for c in customers}

        sales_data = []
        for month in range(1, 13):
            sales_data.append(
                {
                    "month": month_abbr[month],
                    "revenue": payments_map.get(month, {}).get("revenue", 0),
                    "orders": payments_map.get(month, {}).get("orders", 0),
                    "customers": customers_map.get(month, 0),
                }
            )

        # ===============================
        # 🔥 TOP PRODUCTS
        # ===============================
        top_products = (
            OrderProduct.objects.filter(order__status="PROCESSING")
            .values("product__sku", "product__name")
            .annotate(sales=Sum("quantity"), revenue=Sum(F("quantity") * F("price")))
            .order_by("-sales")[:5]
        )

        prev_sales = (
            OrderProduct.objects.filter(order__created_at__month=prev_month)
            .values("product__sku")
            .annotate(prev_sales=Sum("quantity"))
        )

        prev_sales_map = {p["product__sku"]: p["prev_sales"] for p in prev_sales}

        top_products_data = []
        for p in top_products:
            growth = p["sales"] - prev_sales_map.get(p["product__sku"], 0)

            top_products_data.append(
                {
                    "name": p["product__name"],
                    "sales": p["sales"],
                    "revenue": p["revenue"],
                    "growth": growth,
                }
            )

        # ===============================
        # 👥 CUSTOMER SEGMENTS
        # ===============================
        total_customers = User.objects.count()
        last_30_days = now - timedelta(days=30)

        new_customers = User.objects.filter(date_joined__gte=last_30_days).count()

        recurrent_customers = (
            User.objects.annotate(orders_count=Count("order"))
            .filter(orders_count__gt=1)
            .count()
        )

        vip_customers = (
            Payment.objects.values("order__user__dni")
            .annotate(total_spent=Sum("payment_amount"))
            .order_by("-total_spent")[: max(1, total_customers // 5)]
            .count()
        )

        def percent(value):
            return int((value / total_customers) * 100) if total_customers else 0

        customer_segments_data = [
            {
                "name": "New Customer",
                "value": new_customers,
                "percentage": percent(new_customers),
                "color": "#3B82F6",
            },
            {
                "name": "Recurrent Customers",
                "value": recurrent_customers,
                "percentage": percent(recurrent_customers),
                "color": "#10B981",
            },
            {
                "name": "VIP Customers",
                "value": vip_customers,
                "percentage": percent(vip_customers),
                "color": "#8B5CF6",
            },
        ]

        # ===============================
        # 🕒 RECENT ACTIVITY
        # ===============================
        recent_activity = []

        recent_orders = Order.objects.order_by("-created_at")[:3]
        for order in recent_orders:
            recent_activity.append(
                {
                    "action": "New Order",
                    "customer": str(order.user),
                    "amount": order.total,
                    "time": timesince(order.created_at) + " ago",
                }
            )

        recent_payments = Payment.objects.order_by("-payment_date")[:2]
        for payment in recent_payments:
            recent_activity.append(
                {
                    "action": "New Payment",
                    "customer": str(payment.order.user),
                    "amount": payment.payment_amount,
                    "time": timesince(payment.payment_date) + " ago",
                }
            )

        recent_customers = User.objects.order_by("-date_joined")[:2]
        for user in recent_customers:
            recent_activity.append(
                {
                    "action": "New Customer",
                    "customer": user.username if user.username else user.first_name,
                    "amount": 0,
                    "time": timesince(user.date_joined) + " ago",
                }
            )

        return Response(
            {
                "sales_data": SalesDataReportSerializer(sales_data, many=True).data,
                "top_products": TopProductsAnalyticsSerializer(
                    top_products_data, many=True
                ).data,
                "customer_segments": CustomerSegmentsAnalyticsSerializer(
                    customer_segments_data, many=True
                ).data,
                "recent_activity": RecentActivityAnalyticsSerializer(
                    recent_activity, many=True
                ).data,
            },
            status=status.HTTP_200_OK,
        )
