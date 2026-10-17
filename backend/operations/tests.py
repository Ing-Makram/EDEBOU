from django.test import TestCase

from accounts.models import Role, User
from catalog.models import Category, Client, ConsignType, Product, ProductPrice, ProductUnit

from .models import ConsignMovement, Payment, Sale, StockMovement, StockReason


class AppendOnlyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('Ali', '1234', Role.MANAGER)
        self.client_ = Client.objects.create(name='Café Central')
        self.product = Product.objects.create(name='Eau 1.5L', category=Category.WATER)

    def test_stock_movement_cannot_be_edited_or_deleted(self):
        m = StockMovement.objects.create(product=self.product, quantity=10, reason=StockReason.PURCHASE, user=self.user)
        m.quantity = 99
        with self.assertRaises(RuntimeError):
            m.save()
        with self.assertRaises(RuntimeError):
            m.delete()
        m.refresh_from_db()
        self.assertEqual(m.quantity, 10)

    def test_payment_and_sale_are_append_only(self):
        sale = Sale.objects.create(client=self.client_, mode='credit', total=5000, user=self.user)
        p = Payment.objects.create(client=self.client_, amount=1000, user=self.user)
        for obj in (sale, p):
            with self.assertRaises(RuntimeError):
                obj.save()
            with self.assertRaises(RuntimeError):
                obj.delete()

    def test_reversal_is_a_new_row(self):
        user, c = self.user, self.client_
        p = Payment.objects.create(client=c, amount=1000, user=user)
        Payment.objects.create(client=c, amount=-p.amount, user=user)
        self.assertEqual(Payment.objects.filter(client=c).count(), 2)

    def test_consign_movement_append_only(self):
        m = ConsignMovement.objects.create(client=self.client_, consign_type=ConsignType.CRATE, qty_out=3, user=self.user)
        with self.assertRaises(RuntimeError):
            m.delete()


class CatalogModelTests(TestCase):
    def test_price_unique_per_unit_and_client_type(self):
        from django.db import IntegrityError, transaction
        p = Product.objects.create(name='Coca', category=Category.SODA)
        u = ProductUnit.objects.create(product=p, name='pack', factor=6)
        ProductPrice.objects.create(unit=u, client_type='retail', price=7500)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductPrice.objects.create(unit=u, client_type='retail', price=7000)
