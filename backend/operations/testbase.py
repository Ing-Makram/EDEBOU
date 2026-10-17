import random
import uuid
from datetime import datetime
from unittest import mock

from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from catalog.models import Category, Client, Product, ProductPrice, ProductUnit

from . import services
from .models import ConsignMovement, Payment, Sale, SaleLine, StockMovement, StockReason

# (produit, unité) -> (facteur, consigne, {type client: prix})
CATALOG = {
    ('Eau', 'unit'): (1, None, {'retail': 800, 'cafe': 750, 'wholesale': 700}),
    ('Eau', 'pack'): (6, ('crate', 1), {'retail': 4500, 'cafe': 4200, 'wholesale': 4000}),
    ('Eau', 'palette'): (60, ('crate', 10), {'retail': 40000, 'cafe': 38000, 'wholesale': 36000}),
    ('Jus', 'unit'): (1, None, {'retail': 1000, 'cafe': 900, 'wholesale': 800}),
    ('Verre', 'unit'): (1, ('glass_bottle', 1), {'retail': 1200, 'cafe': 1100, 'wholesale': 1000}),
}
CONSIGNABLE = {'Eau': True, 'Jus': False, 'Verre': True}


class SaleTestCase(TestCase):
    INITIAL_STOCK = 1000

    def setUp(self):
        self.manager = User.objects.create_user('manager', '1234', Role.MANAGER)
        self.cashier = User.objects.create_user('cashier', '1234', Role.CASHIER)
        self.delivery = User.objects.create_user('delivery', '1234', Role.DELIVERY)
        self.products = {}
        for name, consignable in CONSIGNABLE.items():
            self.products[name] = Product.objects.create(name=name, category=Category.WATER, consignable=consignable)
        self.units = {}
        for (pname, uname), (factor, consign, prices) in CATALOG.items():
            u = ProductUnit.objects.create(product=self.products[pname], name=uname, factor=factor,
                                           consign_type=consign[0] if consign else '',
                                           consign_qty=consign[1] if consign else 0)
            self.units[(pname, uname)] = u
            for ctype, price in prices.items():
                ProductPrice.objects.create(unit=u, client_type=ctype, price=price)
        self.add_stock(self.INITIAL_STOCK)
        self.cafe = Client.objects.create(name='Café', type='cafe')
        self.wholesaler = Client.objects.create(name='Gros', type='wholesale')
        self.retailer = Client.objects.create(name='Détail', type='retail')

    def add_stock(self, qty):
        for p in self.products.values():
            StockMovement.objects.create(product=p, quantity=qty, reason=StockReason.PURCHASE, user=self.manager)

    def api(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def body(self, lines, client=None, mode='cash', **extra):
        b = {'request_id': str(uuid.uuid4()), 'mode': mode,
             'lines': [{'product_id': self.products[p].pk, 'unit': u, 'quantity': q} for p, u, q in lines]}
        if client is not None:
            b['client_id'] = client.pk
        b.update(extra)
        return b

    def sell(self, lines, client=None, mode='cash', user=None, expect=201, **extra):
        r = self.api(user or self.cashier).post('/api/sales/', self.body(lines, client, mode, **extra), format='json')
        self.assertEqual(r.status_code, expect, r.data)
        return r

    def stock(self, name):
        return services.stock_levels([self.products[name].pk])[self.products[name].pk]

    def counts(self):
        return tuple(m.objects.count() for m in (Sale, SaleLine, StockMovement, ConsignMovement, Payment))
