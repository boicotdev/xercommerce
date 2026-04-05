from django.db import models

options = (
    ("CANASTILLA", "CANASTILLA"),
    ("MANOJO", "MANOJO"),
    ("BULTO", "BULTO"),
    ("CAJA", "CAJA"),
    ("ATADOS", "ATADOS"),
    ("DOCENA", "DOCENA"),
    ("BOLSAS", "BOLSAS"),
    ("GUACAL", "GUACAL"),
    ("BANDEJA", "BANDEJA"),
    ("ESTUCHE", "ESTUCHE"),
    ("PONY", "PONY"),
    ("TONELADA", "TONELADA"),
    ("KG", "KG"),
)


class Category(models.Model):
    name = models.CharField(max_length=30)
    description = models.CharField(max_length=50)

    def __str__(self):
        return f"Category: {self.name}"

    class Meta:
        ordering = ['name']


class UnitOfMeasure(models.Model):
    """
    Represent a measure unity, a product can be related to `UnitOfMeasure`
    Set all choices are required by your application.
    """

    unity = models.CharField(max_length=30, choices=options)
    weight = models.IntegerField()

    def __str__(self):
        return f"{self.unity} | ID {self.id} | Weight {self.weight} Kgs"
    
    class Meta:
        ordering = ['unity']


class Product(models.Model):
    sku = models.CharField(max_length=30, primary_key=True)
    name = models.CharField(max_length=50)
    description = models.TextField(max_length=1024)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_price = models.DecimalField(max_digits=12,decimal_places=2, blank=True, null=True)
    purchase_price = models.DecimalField(max_digits=12,decimal_places=2, blank=True, null=True)
    stock = models.PositiveIntegerField(default=1)
    category = models.ForeignKey(Category, null=True, on_delete=models.SET_NULL)
    score = models.IntegerField(blank=True, null=True)
    recommended = models.BooleanField(default=False)
    best_seller = models.BooleanField(default=False)
    tag = models.CharField(max_length=60, default="Cultivo tradicional")
    quality = models.CharField(max_length=30, default="segunda")
    weight = models.FloatField(default=0)
    slug = models.SlugField(blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True, blank=True, null=True)
    unit_of_measurement = models.ForeignKey(
        UnitOfMeasure, on_delete=models.SET_NULL, blank=True, null=True
    )
    main_image = models.ImageField(
        upload_to="products/", default="products/dummie_image.jpeg"
    )

    def __str__(self):
        return f"Product: {self.name} (SKU: {self.sku}, Stock: {self.stock}, Price: ${self.price})"

    class Meta:
        ordering = ['name', 'sku']



class ProductReference(models.Model):
    options = (
        ('STABLE', 'Estable'),
        ('WENT_UP', 'Subío'),
        ('WENT_DOWN', 'Bajó')
    )

    name = models.CharField(max_length=100)
    measure = models.ForeignKey(UnitOfMeasure, on_delete=models.SET_NULL, blank=True, null=True)
    quantity = models.IntegerField()
    extra_price_quality = models.DecimalField(max_digits=12, decimal_places=2)
    first_price_quality = models.DecimalField(max_digits=12, decimal_places=2)
    price_per_unity = models.DecimalField(max_digits=12, decimal_places=2)
    variation = models.CharField(max_length=30, choices=options, default='STABLE')
    weight = models.IntegerField(default=1)
    slug = models.SlugField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    image = models.ImageField(
        upload_to="products/",
        null=True,
        blank=True
    )
    
    def __str__(self) -> str:
        return str(self.name)
