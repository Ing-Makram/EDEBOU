from django.db import models


class ClientType(models.TextChoices):
    RETAIL = 'retail', 'Détail'
    CAFE = 'cafe', 'Café'
    WHOLESALE = 'wholesale', 'Grossiste'


class Category(models.TextChoices):
    WATER = 'water', 'Eau'
    SODA = 'soda', 'Gazeux'
    JUICE = 'juice', 'Jus'


class ConsignType(models.TextChoices):
    CRATE = 'crate', 'Caisse'
    GLASS_BOTTLE = 'glass_bottle', 'Bouteille verre'


class Product(models.Model):
    name = models.CharField(max_length=150)
    brand = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=10, choices=Category.choices)
    consignable = models.BooleanField(default=False)
    min_threshold = models.PositiveIntegerField(default=0, help_text='Seuil minimum, en unités de base')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ProductUnit(models.Model):
    """Unité de vente (palette, pack, unité). factor = nombre d'unités de base.
    consign_qty = articles consignés par unité vendue, du type consign_type."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='units')
    name = models.CharField(max_length=30)
    factor = models.PositiveIntegerField(default=1)
    consign_type = models.CharField(max_length=15, choices=ConsignType.choices, blank=True)
    consign_qty = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['product', 'name'], name='uniq_unit_per_product'),
            models.CheckConstraint(condition=models.Q(factor__gte=1), name='unit_factor_gte_1'),
        ]

    def __str__(self):
        return f'{self.product} / {self.name}'


class ProductPrice(models.Model):
    """Prix en millimes d'une unité de vente, selon le type de client."""
    unit = models.ForeignKey(ProductUnit, on_delete=models.CASCADE, related_name='prices')
    client_type = models.CharField(max_length=10, choices=ClientType.choices)
    price = models.PositiveBigIntegerField(help_text='millimes')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['unit', 'client_type'], name='uniq_price_per_unit_type')]


class Client(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    type = models.CharField(max_length=10, choices=ClientType.choices, default=ClientType.RETAIL)
    credit_limit = models.PositiveBigIntegerField(default=0, help_text='millimes')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
