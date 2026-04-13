from django.contrib import admin
from purchases.models import SuggestedRetailPrice
from .models import Product, Category, ProductImage, UnitOfMeasure, ProductReference, ProductImage

admin.site.register([Product, SuggestedRetailPrice, Category, UnitOfMeasure, ProductReference, ProductImage])
