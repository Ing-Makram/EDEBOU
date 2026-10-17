from django.conf import settings
from django.db import models

from catalog.models import Client, ConsignType, Product, ProductUnit


class AppendOnlyModel(models.Model):
    """Historique : on ajoute des lignes, on ne modifie ni ne supprime.
    Une correction = une écriture inverse."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError(f'{type(self).__name__} est en ajout seul : créer une écriture inverse.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError(f'{type(self).__name__} est en ajout seul : suppression interdite.')


class PaymentMode(models.TextChoices):
    CASH = 'cash', 'Comptant'
    CREDIT = 'credit', 'Crédit'


class Sale(AppendOnlyModel):
    # client nul = vente comptant au comptoir (client de passage)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.PROTECT, related_name='sales')
    # UUID généré par l'appli : empêche les doublons (double clic, nouvel essai réseau)
    request_id = models.UUIDField(unique=True, null=True, blank=True)
    mode = models.CharField(max_length=6, choices=PaymentMode.choices)
    total = models.BigIntegerField(help_text='millimes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    reverses = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT,
                                    related_name='reversed_by', help_text='Vente annulée par cette écriture')


class SaleLine(AppendOnlyModel):
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    unit = models.ForeignKey(ProductUnit, on_delete=models.PROTECT)
    quantity = models.BigIntegerField()
    unit_price = models.BigIntegerField(help_text='prix appliqué, millimes')


class Payment(AppendOnlyModel):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='payments')
    amount = models.BigIntegerField(help_text='millimes; négatif = annulation')
    sale = models.ForeignKey(Sale, null=True, blank=True, on_delete=models.PROTECT, related_name='payments')
    # True = versé au moment de la vente (annulé avec elle) ; False = paiement ultérieur, indépendant.
    at_sale = models.BooleanField(default=False)
    request_id = models.UUIDField(unique=True, null=True, blank=True)
    reverses = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT,
                                    related_name='reversed_by', help_text='Paiement annulé par cette écriture')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ConsignMovement(AppendOnlyModel):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='consign_movements')
    consign_type = models.CharField(max_length=15, choices=ConsignType.choices)
    qty_out = models.PositiveIntegerField(default=0)
    qty_in = models.PositiveIntegerField(default=0)
    sale = models.ForeignKey(Sale, null=True, blank=True, on_delete=models.PROTECT, related_name='consign_movements')
    request_id = models.UUIDField(unique=True, null=True, blank=True)  # mouvements manuels seulement
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class StockReason(models.TextChoices):
    SALE = 'sale', 'Vente'
    PURCHASE = 'purchase', 'Achat'
    INVENTORY = 'inventory', 'Inventaire'
    LOSS = 'loss', 'Perte'


class StockMovement(AppendOnlyModel):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_movements')
    quantity = models.BigIntegerField(help_text='unités de base; positif ou négatif')
    reason = models.CharField(max_length=10, choices=StockReason.choices)
    sale = models.ForeignKey(Sale, null=True, blank=True, on_delete=models.PROTECT, related_name='stock_movements')
    request_id = models.UUIDField(unique=True, null=True, blank=True)  # entrées et ajustements manuels
    # Entrées : unité saisie et coût par cette unité (millimes) ; coût par unité de base = unit_cost / unit.factor.
    unit = models.ForeignKey(ProductUnit, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    unit_cost = models.PositiveBigIntegerField(null=True, blank=True, help_text='millimes par `unit`')
    note = models.CharField(max_length=200, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
