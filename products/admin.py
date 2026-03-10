from django.contrib import admin
from purchases.models import SuggestedRetailPrice
from .models import Product, Category, UnitOfMeasure, ProductReference

admin.site.register([Product, SuggestedRetailPrice, Category, UnitOfMeasure, ProductReference])
