from django.urls import path
from .views import (
    ProductFilterAPIView,
    ProductImportView,
    ProductListView,
    ProductDetailsView,
    RetrieveLatestProducts,
    AdminProductAPIView,
    AdminProductReferenceAPIView,
    AdminProductsPricesBulkUpdate,
    SuggestedRetailPricesAPIView,
)

from products.categories.views import AdminCategoriesAPIView

urlpatterns = [
    # list all categories
    path("products/categories/", AdminCategoriesAPIView.as_view()),
    path("dashboard/products/retail-prices/", SuggestedRetailPricesAPIView.as_view()),
    path("products/categories/<int:pk>/", AdminCategoriesAPIView.as_view()),
    path("dashboard/products/import/", ProductImportView.as_view()),
    path("products/list/", ProductListView.as_view()),  # retrieve all products
    path("products/latest/", RetrieveLatestProducts.as_view()),
    path("products/filter/", ProductFilterAPIView.as_view()),
    path("products/product/details/", ProductDetailsView.as_view()),
    path("dashboard/products/", AdminProductAPIView.as_view()),
    path("dashboard/products/update-prices/", AdminProductReferenceAPIView.as_view()),
    path("dashboard/products/bulk-update-prices/", AdminProductsPricesBulkUpdate.as_view()),
    path("dashboard/products/<str:sku>/", AdminProductAPIView.as_view()),
]
