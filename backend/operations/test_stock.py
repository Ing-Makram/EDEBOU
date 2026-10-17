import uuid

from django.db import IntegrityError, transaction
from django.db.models import Sum
from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductUnit

from . import services
from .models import StockMovement
from .testbase import SaleTestCase


class StockTestCase(SaleTestCase):
    def entry(self, product='Eau', unit='unit', quantity=1, user=None, expect=201, **extra):
        body = {'request_id': str(uuid.uuid4()), 'product_id': self.products[product].pk, 'unit': unit,
                'quantity': quantity, **extra}
        r = self.api(user or self.manager).post('/api/stock/entries/', body, format='json')
        self.assertEqual(r.status_code, expect, r.data)
        return r

    def adjust(self, product='Eau', user=None, expect=201, **extra):
        body = {'request_id': str(uuid.uuid4()), 'product_id': self.products[product].pk, **extra}
        r = self.api(user or self.manager).post('/api/stock/adjustments/', body, format='json')
        self.assertEqual(r.status_code, expect, r.data)
        return r

    def overview(self, user=None):
        r = self.api(user or self.manager).get('/api/stock/')
        self.assertEqual(r.status_code, 200)
        return {row['name']: row for row in r.data}

    def raw(self, name):
        return StockMovement.objects.filter(product=self.products[name]).aggregate(s=Sum('quantity'))['s'] or 0


class EntryTests(StockTestCase):
    def test_entry_converts_each_unit_to_base_units(self):
        for unit, factor in (('unit', 1), ('pack', 6), ('palette', 60)):
            with self.subTest(unit=unit):
                before = self.stock('Eau')
                r = self.entry('Eau', unit, 3)
                self.assertEqual(r.data['quantity'], 3 * factor)
                self.assertEqual(r.data['stock'], before + 3 * factor)
                self.assertEqual(self.stock('Eau'), before + 3 * factor)
                m = StockMovement.objects.get(pk=r.data['id'])
                self.assertEqual((m.quantity, m.reason, m.unit.name, m.user_id), (3 * factor, 'purchase', unit, self.manager.pk))

    def test_entry_stores_unit_cost_and_note(self):
        r = self.entry('Eau', 'pack', 10, unit_cost=4200, note='Livraison Safia')
        self.assertEqual((r.data['unit_cost'], r.data['unit'], r.data['note']), (4200, 'pack', 'Livraison Safia'))
        m = StockMovement.objects.get(pk=r.data['id'])
        self.assertEqual((m.unit_cost, m.note), (4200, 'Livraison Safia'))

    def test_entry_without_cost_stores_none(self):
        r = self.entry('Jus', 'unit', 5)
        self.assertIsNone(r.data['unit_cost'])
        self.assertEqual(r.data['note'], '')
        self.entry('Jus', 'unit', 5, unit_cost=None)

    def test_entry_validation(self):
        rows = StockMovement.objects.count()
        cases = {'qty 0': {'quantity': 0}, 'qty negative': {'quantity': -3}, 'qty float': {'quantity': 1.5},
                 'qty huge': {'quantity': 10 ** 7}, 'unknown unit': {'unit': 'carton'},
                 'unknown product': {'product_id': 99999}, 'negative cost': {'unit_cost': -1},
                 'float cost': {'unit_cost': 1.5}, 'huge cost': {'unit_cost': 10 ** 13},
                 'no request id': {'request_id': None}, 'bad request id': {'request_id': 'x'},
                 'note too long': {'note': 'x' * 201}}
        for label, patch in cases.items():
            with self.subTest(label):
                body = {'request_id': str(uuid.uuid4()), 'product_id': self.products['Eau'].pk, 'unit': 'pack',
                        'quantity': 1, **patch}
                r = self.api(self.manager).post('/api/stock/entries/', body, format='json')
                self.assertEqual(r.status_code, 400)
        self.assertEqual(StockMovement.objects.count(), rows)

    def test_inactive_product_rejected(self):
        Product.objects.filter(pk=self.products['Jus'].pk).update(is_active=False)
        self.entry('Jus', 'unit', 1, expect=400)

    def test_same_request_id_twice_adds_stock_once(self):
        body = {'request_id': str(uuid.uuid4()), 'product_id': self.products['Eau'].pk, 'unit': 'pack', 'quantity': 5}
        a = self.api(self.manager)
        first, second = a.post('/api/stock/entries/', body, format='json'), a.post('/api/stock/entries/', body, format='json')
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(self.stock('Eau'), self.INITIAL_STOCK + 30)
        self.assertEqual(StockMovement.objects.filter(request_id=body['request_id']).count(), 1)
        self.assertEqual(second.data['stock'], self.INITIAL_STOCK + 30)

    def test_replay_returns_original_even_if_payload_differs(self):
        body = {'request_id': str(uuid.uuid4()), 'product_id': self.products['Eau'].pk, 'unit': 'pack', 'quantity': 5}
        a = self.api(self.manager)
        a.post('/api/stock/entries/', body, format='json')
        again = a.post('/api/stock/entries/', {**body, 'quantity': 500}, format='json')
        self.assertEqual(again.data['quantity'], 30)
        self.assertEqual(self.stock('Eau'), self.INITIAL_STOCK + 30)

    def test_request_id_unique_in_database(self):
        rid = uuid.uuid4()
        StockMovement.objects.create(product=self.products['Eau'], quantity=1, reason='purchase', user=self.manager,
                                     request_id=rid)
        with self.assertRaises(IntegrityError), transaction.atomic():
            StockMovement.objects.create(product=self.products['Eau'], quantity=1, reason='purchase',
                                         user=self.manager, request_id=rid)

    def test_entry_is_manager_only(self):
        rows = StockMovement.objects.count()
        for user in (self.cashier, self.delivery):
            self.entry('Eau', 'pack', 1, user=user, expect=403)
        self.assertEqual(APIClient().post('/api/stock/entries/', {}, format='json').status_code, 401)
        self.assertEqual(StockMovement.objects.count(), rows)

    def test_a_unit_used_by_an_entry_cannot_be_removed_from_the_product(self):
        self.entry('Eau', 'palette', 1)
        r = self.api(self.manager).patch(f'/api/products/{self.products["Eau"].pk}/',
                                         {'units': [{'name': 'unit', 'factor': 1}]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertTrue(ProductUnit.objects.filter(product=self.products['Eau'], name='palette').exists())


class AdjustmentTests(StockTestCase):
    def test_counted_quantity_below_current_creates_negative_difference(self):
        r = self.adjust('Jus', reason='inventory', counted_quantity=950)
        self.assertEqual((r.data['quantity'], r.data['stock'], r.data['reason']), (-50, 950, 'inventory'))
        self.assertEqual(self.stock('Jus'), 950)

    def test_counted_quantity_above_current_creates_positive_difference(self):
        r = self.adjust('Jus', reason='inventory', counted_quantity=1010)
        self.assertEqual((r.data['quantity'], r.data['stock']), (10, 1010))

    def test_counted_quantity_equal_to_current_is_rejected_as_no_op(self):
        rows = StockMovement.objects.count()
        r = self.adjust('Jus', reason='inventory', counted_quantity=self.INITIAL_STOCK, expect=400)
        self.assertEqual((r.data['code'], r.data['current']), ('no_change', self.INITIAL_STOCK))
        self.assertEqual(StockMovement.objects.count(), rows)

    def test_counted_quantity_is_relative_to_the_stock_at_that_moment(self):
        self.sell([('Jus', 'unit', 100)])
        r = self.adjust('Jus', reason='inventory', counted_quantity=880)
        self.assertEqual(r.data['quantity'], -20)  # stock actuel 900

    def test_counted_zero_empties_the_stock(self):
        r = self.adjust('Jus', reason='inventory', counted_quantity=0)
        self.assertEqual((r.data['quantity'], r.data['stock']), (-self.INITIAL_STOCK, 0))
        self.adjust('Jus', reason='inventory', counted_quantity=0, expect=400)

    def test_signed_delta_positive_and_negative(self):
        self.assertEqual(self.adjust('Verre', reason='inventory', delta=7).data['stock'], self.INITIAL_STOCK + 7)
        self.assertEqual(self.adjust('Verre', reason='loss', delta=-12).data['stock'], self.INITIAL_STOCK - 5)
        self.assertEqual(self.stock('Verre'), self.INITIAL_STOCK - 5)

    def test_exactly_one_of_counted_quantity_or_delta(self):
        rows = StockMovement.objects.count()
        self.adjust(reason='inventory', expect=400)
        self.adjust(reason='inventory', counted_quantity=5, delta=-3, expect=400)
        self.adjust(reason='inventory', delta=0, expect=400)
        self.adjust(reason='inventory', counted_quantity=-1, expect=400)
        self.adjust(reason='inventory', delta=1.5, expect=400)
        self.assertEqual(StockMovement.objects.count(), rows)

    def test_reason_is_mandatory_and_must_be_valid(self):
        rows = StockMovement.objects.count()
        for bad in (None, '', 'sale', 'purchase', 'because'):
            with self.subTest(reason=bad):
                body = {'request_id': str(uuid.uuid4()), 'product_id': self.products['Eau'].pk, 'delta': -1}
                if bad is not None:
                    body['reason'] = bad
                self.assertEqual(self.api(self.manager).post('/api/stock/adjustments/', body, format='json').status_code, 400)
        self.assertEqual(StockMovement.objects.count(), rows)

    def test_reason_and_note_are_stored(self):
        r = self.adjust('Eau', reason='loss', delta=-6, note='Un pack tombé au déchargement')
        m = StockMovement.objects.get(pk=r.data['id'])
        self.assertEqual((m.reason, m.note, m.quantity), ('loss', 'Un pack tombé au déchargement', -6))

    def test_a_loss_cannot_increase_stock(self):
        rows = StockMovement.objects.count()
        self.adjust('Eau', reason='loss', delta=5, expect=400)
        r = self.adjust('Eau', reason='loss', counted_quantity=self.INITIAL_STOCK + 1, expect=400)
        self.assertEqual(r.data['code'], 'loss_must_decrease')
        self.assertEqual(StockMovement.objects.count(), rows)

    def test_adjustment_cannot_make_stock_negative(self):
        rows = StockMovement.objects.count()
        r = self.adjust('Eau', reason='loss', delta=-(self.INITIAL_STOCK + 1), expect=400)
        self.assertEqual(r.data['code'], 'adjustment_below_zero')
        self.assertEqual(StockMovement.objects.count(), rows)
        self.adjust('Eau', reason='loss', delta=-self.INITIAL_STOCK)  # jusqu'à zéro : permis
        self.assertEqual(self.stock('Eau'), 0)

    def test_adjustment_appends_and_never_overwrites(self):
        before = list(StockMovement.objects.order_by('id').values())
        self.adjust('Eau', reason='inventory', counted_quantity=500)
        after = list(StockMovement.objects.order_by('id').values())
        self.assertEqual(after[:len(before)], before)
        self.assertEqual(len(after), len(before) + 1)

    def test_idempotency(self):
        body = {'request_id': str(uuid.uuid4()), 'product_id': self.products['Eau'].pk, 'reason': 'loss', 'delta': -10}
        a = self.api(self.manager)
        first, second = a.post('/api/stock/adjustments/', body, format='json'), a.post('/api/stock/adjustments/', body, format='json')
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(self.stock('Eau'), self.INITIAL_STOCK - 10)

    def test_replayed_counted_adjustment_is_not_rejected_as_no_op(self):
        body = {'request_id': str(uuid.uuid4()), 'product_id': self.products['Eau'].pk, 'reason': 'inventory',
                'counted_quantity': 900}
        a = self.api(self.manager)
        a.post('/api/stock/adjustments/', body, format='json')
        again = a.post('/api/stock/adjustments/', body, format='json')  # le stock compté = stock actuel, mais rejeu
        self.assertEqual(again.status_code, 200)
        self.assertEqual(self.stock('Eau'), 900)

    def test_unknown_or_inactive_product(self):
        body = {'request_id': str(uuid.uuid4()), 'product_id': 99999, 'reason': 'inventory', 'delta': 1}
        self.assertEqual(self.api(self.manager).post('/api/stock/adjustments/', body, format='json').status_code, 400)
        Product.objects.filter(pk=self.products['Jus'].pk).update(is_active=False)
        self.adjust('Jus', reason='inventory', delta=1, expect=400)

    def test_adjustment_is_manager_only(self):
        rows = StockMovement.objects.count()
        for user in (self.cashier, self.delivery):
            self.adjust(reason='inventory', delta=-1, user=user, expect=403)
        self.assertEqual(APIClient().post('/api/stock/adjustments/', {}, format='json').status_code, 401)
        self.assertEqual(StockMovement.objects.count(), rows)


class OverviewTests(StockTestCase):
    def set_threshold(self, name, value):
        Product.objects.filter(pk=self.products[name].pk).update(min_threshold=value)

    def test_overview_returns_base_units_breakdown_threshold_and_flag(self):
        row = self.overview()['Eau']
        self.assertEqual(row['quantity'], 1000)
        self.assertEqual(row['breakdown'], [{'unit': 'palette', 'factor': 60, 'count': 16},
                                            {'unit': 'pack', 'factor': 6, 'count': 6},
                                            {'unit': 'unit', 'factor': 1, 'count': 4}])
        self.assertEqual((row['remainder'], row['min_threshold'], row['low_stock']), (0, 0, False))
        self.assertEqual(sum(b['factor'] * b['count'] for b in row['breakdown']) + row['remainder'], row['quantity'])

    def test_breakdown_for_a_product_with_a_single_unit(self):
        row = self.overview()['Jus']
        self.assertEqual(row['breakdown'], [{'unit': 'unit', 'factor': 1, 'count': 1000}])

    def test_breakdown_remainder_when_no_unit_of_factor_one(self):
        p = Product.objects.create(name='Pack only', category=Category.WATER)
        ProductUnit.objects.create(product=p, name='pack', factor=6)
        StockMovement.objects.create(product=p, quantity=20, reason='purchase', user=self.manager)
        row = self.overview()['Pack only']
        self.assertEqual((row['breakdown'], row['remainder']), ([{'unit': 'pack', 'factor': 6, 'count': 3}], 2))

    def test_breakdown_for_zero_and_exact_multiples(self):
        self.adjust('Eau', reason='inventory', counted_quantity=0)
        row = self.overview()['Eau']
        self.assertEqual([b['count'] for b in row['breakdown']], [0, 0, 0])
        self.adjust('Eau', reason='inventory', counted_quantity=126)  # 2 palettes + 1 pack
        self.assertEqual([b['count'] for b in self.overview()['Eau']['breakdown']], [2, 1, 0])

    def test_low_stock_flag_below_at_and_above_the_threshold(self):
        self.set_threshold('Jus', 1000)
        self.assertTrue(self.overview()['Jus']['low_stock'])        # égal au seuil
        self.entry('Jus', 'unit', 1)
        self.assertFalse(self.overview()['Jus']['low_stock'])       # au-dessus
        self.set_threshold('Jus', 1500)
        self.assertTrue(self.overview()['Jus']['low_stock'])        # en dessous
        self.set_threshold('Jus', 1000)
        self.adjust('Jus', reason='inventory', counted_quantity=999)
        self.assertTrue(self.overview()['Jus']['low_stock'])
        self.adjust('Jus', reason='inventory', counted_quantity=1001)
        self.assertFalse(self.overview()['Jus']['low_stock'])

    def test_threshold_zero_never_flags_even_at_zero_stock(self):
        self.adjust('Jus', reason='inventory', counted_quantity=0)
        row = self.overview()['Jus']
        self.assertEqual((row['quantity'], row['min_threshold'], row['low_stock']), (0, 0, False))

    def test_low_stock_follows_sales(self):
        self.set_threshold('Verre', 990)
        self.assertFalse(self.overview()['Verre']['low_stock'])
        self.sell([('Verre', 'unit', 10)], self.cafe)
        self.assertTrue(self.overview()['Verre']['low_stock'])  # 990 = seuil

    def test_threshold_is_set_through_the_product_api(self):
        r = self.api(self.manager).patch(f'/api/products/{self.products["Jus"].pk}/', {'min_threshold': 2000}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.overview()['Jus']['low_stock'])

    def test_all_three_roles_can_read_but_anonymous_cannot(self):
        for user in (self.manager, self.cashier, self.delivery):
            self.assertEqual(self.overview(user)['Eau']['quantity'], 1000)
        self.assertEqual(APIClient().get('/api/stock/').status_code, 401)

    def test_delivery_is_read_only(self):
        a = self.api(self.delivery)
        for method in ('post', 'put', 'patch', 'delete'):
            self.assertEqual(getattr(a, method)('/api/stock/', {}, format='json').status_code, 403)

    def test_stock_is_computed_from_movements_not_stored(self):
        self.assertFalse(any(f.name in ('stock', 'quantity') for f in Product._meta.get_fields()))
        StockMovement.objects.create(product=self.products['Jus'], quantity=-300, reason='loss', user=self.manager)
        self.assertEqual(self.overview()['Jus']['quantity'], 700)
        StockMovement.objects.create(product=self.products['Jus'], quantity=+5, reason='purchase', user=self.manager)
        self.assertEqual(self.overview()['Jus']['quantity'], 705)

    def test_inactive_products_are_listed_with_their_flag(self):
        Product.objects.filter(pk=self.products['Jus'].pk).update(is_active=False)
        self.assertFalse(self.overview()['Jus']['is_active'])

    def test_overview_matches_the_service(self):
        for name, row in self.overview().items():
            self.assertEqual(row['quantity'], services.stock_levels([self.products[name].pk])[self.products[name].pk])


class HistoryTests(StockTestCase):
    def history(self, name='Eau', user=None, expect=200):
        r = self.api(user or self.manager).get(f'/api/stock/{self.products[name].pk}/movements/')
        self.assertEqual(r.status_code, expect)
        return r.data

    def test_history_newest_first_with_running_balance(self):
        self.entry('Eau', 'pack', 10)
        self.sell([('Eau', 'unit', 5)], self.cafe)
        self.adjust('Eau', reason='loss', delta=-2)
        h = self.history()
        self.assertEqual([m['reason'] for m in h], ['loss', 'sale', 'purchase', 'purchase'])
        self.assertEqual([m['quantity'] for m in h], [-2, -5, 60, 1000])
        self.assertEqual([m['balance_after'] for m in h], [1053, 1055, 1060, 1000])
        self.assertEqual(h[0]['balance_after'], self.stock('Eau'))

    def test_history_row_fields(self):
        r = self.entry('Eau', 'pack', 2, unit_cost=4000, note='BL 12')
        sale = self.sell([('Eau', 'unit', 1)], self.cafe).data
        by_id = {m['id']: m for m in self.history()}
        e = by_id[r.data['id']]
        self.assertEqual((e['unit'], e['unit_cost'], e['note'], e['user_name'], e['sale']), ('pack', 4000, 'BL 12', 'manager', None))
        s = next(m for m in by_id.values() if m['sale'] == sale['id'])
        self.assertEqual((s['quantity'], s['reason'], s['user_name']), (-1, 'sale', 'cashier'))

    def test_history_only_contains_that_product(self):
        self.entry('Jus', 'unit', 5)
        self.assertTrue(all(m['product'] == self.products['Eau'].pk for m in self.history('Eau')))

    def test_history_shows_sale_cancellation_as_a_reversing_row(self):
        sale = self.sell([('Eau', 'pack', 2)], self.cafe).data
        self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/')
        h = self.history()
        self.assertEqual([m['quantity'] for m in h[:2]], [12, -12])
        self.assertEqual(h[0]['balance_after'], 1000)

    def test_history_is_manager_only(self):
        self.history(user=self.cashier, expect=403)
        self.history(user=self.delivery, expect=403)
        self.assertEqual(APIClient().get(f'/api/stock/{self.products["Eau"].pk}/movements/').status_code, 401)

    def test_unknown_product_is_404(self):
        self.assertEqual(self.api(self.manager).get('/api/stock/99999/movements/').status_code, 404)
        self.assertEqual(self.api(self.manager).get('/api/stock/abc/movements/').status_code, 404)

    def test_history_cannot_be_edited_through_the_api(self):
        m = self.entry('Eau', 'unit', 1).data
        for method in ('put', 'patch', 'delete'):
            r = getattr(self.api(self.manager), method)(f'/api/stock/{m["id"]}/', {}, format='json')
            self.assertIn(r.status_code, (404, 405))


class StockConsistencyTests(StockTestCase):
    def test_stock_after_sales_cancellations_entries_and_adjustments_equals_the_raw_sum(self):
        a = self.api(self.manager)
        expected = {'Eau': self.INITIAL_STOCK, 'Jus': self.INITIAL_STOCK, 'Verre': self.INITIAL_STOCK}

        s1 = self.sell([('Eau', 'pack', 3), ('Jus', 'unit', 10)], self.cafe, mode='credit').data
        expected['Eau'] -= 18
        expected['Jus'] -= 10
        s2 = self.sell([('Eau', 'palette', 2), ('Verre', 'unit', 7)], self.wholesaler).data
        expected['Eau'] -= 120
        expected['Verre'] -= 7
        a.post(f'/api/sales/{s1["id"]}/cancel/')
        expected['Eau'] += 18
        expected['Jus'] += 10
        self.entry('Eau', 'palette', 4)
        expected['Eau'] += 240
        self.entry('Jus', 'unit', 25, unit_cost=900)
        expected['Jus'] += 25
        self.adjust('Eau', reason='inventory', counted_quantity=1000)
        expected['Eau'] = 1000
        self.adjust('Verre', reason='loss', delta=-4)
        expected['Verre'] -= 4
        self.sell([('Jus', 'unit', 3)])
        expected['Jus'] -= 3
        a.post(f'/api/sales/{s2["id"]}/cancel/')
        expected['Eau'] += 120
        expected['Verre'] += 7
        self.adjust('Jus', reason='inventory', delta=2)
        expected['Jus'] += 2

        overview = self.overview()
        for name, exp in expected.items():
            self.assertEqual(overview[name]['quantity'], exp, name)
            self.assertEqual(self.raw(name), exp, name)
            self.assertEqual(self.stock(name), exp, name)
            history = a.get(f'/api/stock/{self.products[name].pk}/movements/').data
            self.assertEqual(history[0]['balance_after'], exp, name)
            self.assertEqual(sum(m['quantity'] for m in history), exp, name)
            row = overview[name]
            self.assertEqual(sum(b['factor'] * b['count'] for b in row['breakdown']) + row['remainder'], exp)
        total_rows = StockMovement.objects.aggregate(s=Sum('quantity'))['s']
        self.assertEqual(total_rows, sum(expected.values()))
