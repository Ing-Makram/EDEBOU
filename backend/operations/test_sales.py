import random
import uuid
from datetime import datetime
from unittest import mock

from django.db.models import Sum
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from catalog.models import Client, Product, ProductPrice

from . import services
from .models import ConsignMovement, Payment, Sale, SaleLine, StockMovement
from .testbase import CATALOG, CONSIGNABLE, SaleTestCase


class PricingTests(SaleTestCase):
    def test_price_per_client_type_applied_and_stored_on_line(self):
        for client, expected in ((self.retailer, 4500), (self.cafe, 4200), (self.wholesaler, 4000)):
            with self.subTest(client=client.name):
                r = self.sell([('Eau', 'pack', 2)], client)
                line = r.data['lines'][0]
                self.assertEqual(line['unit_price'], expected)
                self.assertEqual(r.data['total'], expected * 2)
                self.assertEqual(SaleLine.objects.get(sale_id=r.data['id']).unit_price, expected)

    def test_later_price_change_does_not_alter_history(self):
        r = self.sell([('Eau', 'pack', 1)], self.cafe)
        ProductPrice.objects.filter(unit=self.units[('Eau', 'pack')], client_type='cafe').update(price=9999)
        sale = self.api(self.manager).get(f'/api/sales/{r.data["id"]}/').data
        self.assertEqual(sale['lines'][0]['unit_price'], 4200)
        self.assertEqual(sale['total'], 4200)

    def test_client_cannot_send_prices_or_totals(self):
        b = self.body([('Eau', 'pack', 1)], self.cafe, total=1, paid_amount=None)
        b['lines'][0]['price'] = 1
        b['lines'][0]['unit_price'] = 1
        r = self.api(self.cashier).post('/api/sales/', b, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['total'], 4200)
        self.assertEqual(r.data['lines'][0]['unit_price'], 4200)

    def test_walk_in_cash_sale_at_retail_price(self):
        r = self.sell([('Jus', 'unit', 3)])
        self.assertIsNone(r.data['client'])
        self.assertEqual(r.data['lines'][0]['unit_price'], 1000)
        self.assertEqual(r.data['total'], 3000)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(ConsignMovement.objects.count(), 0)

    def test_total_is_sum_of_lines(self):
        r = self.sell([('Eau', 'unit', 3), ('Jus', 'unit', 2), ('Eau', 'palette', 1)], self.wholesaler)
        self.assertEqual(r.data['total'], 3 * 700 + 2 * 800 + 36000)

    def test_missing_price_rejected(self):
        ProductPrice.objects.filter(unit=self.units[('Jus', 'unit')], client_type='cafe').delete()
        before = self.counts()
        r = self.sell([('Jus', 'unit', 1)], self.cafe, expect=400)
        self.assertEqual(r.data['code'], 'price_missing')
        self.assertEqual(self.counts(), before)


class StockTests(SaleTestCase):
    def test_stock_deducted_in_base_units_for_palette_pack_and_unit(self):
        self.sell([('Eau', 'unit', 3), ('Eau', 'pack', 2), ('Eau', 'palette', 1)], self.cafe)
        self.assertEqual(self.stock('Eau'), self.INITIAL_STOCK - (3 + 2 * 6 + 60))
        self.assertEqual(sorted(StockMovement.objects.filter(reason='sale').values_list('quantity', flat=True)),
                         [-60, -12, -3])

    def test_insufficient_stock_rejects_and_leaves_no_rows(self):
        before = self.counts()
        b = self.body([('Eau', 'pack', 1), ('Jus', 'unit', self.INITIAL_STOCK + 1)], self.cafe, mode='credit',
                      paid_amount=100, returned_consignments=[])
        r = self.api(self.cashier).post('/api/sales/', b, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'insufficient_stock')
        self.assertIn('Jus', r.data['detail'])
        self.assertEqual((r.data['requested'], r.data['available']), (self.INITIAL_STOCK + 1, self.INITIAL_STOCK))
        self.assertEqual(self.counts(), before)
        self.assertFalse(Sale.objects.filter(request_id=b['request_id']).exists())

    def test_insufficient_stock_counts_all_lines_of_same_product(self):
        before = self.counts()
        half = self.INITIAL_STOCK // 2 + 1  # chaque ligne passe seule, pas ensemble
        r = self.sell([('Jus', 'unit', half), ('Jus', 'unit', half)], expect=400)
        self.assertEqual(r.data['code'], 'insufficient_stock')
        self.assertEqual(self.counts(), before)

    def test_exact_remaining_stock_can_be_sold(self):
        self.sell([('Jus', 'unit', self.INITIAL_STOCK)])
        self.assertEqual(self.stock('Jus'), 0)
        self.sell([('Jus', 'unit', 1)], expect=400)


class AtomicityTests(SaleTestCase):
    def full_body(self):
        # Une vente qui touche tout : lignes, stock, consignes sortantes et retournées, paiement.
        self.sell([('Eau', 'pack', 3)], self.cafe, mode='credit')
        return self.body([('Eau', 'pack', 2), ('Jus', 'unit', 4)], self.cafe, mode='credit', paid_amount=500,
                         returned_consignments=[{'consign_type': 'crate', 'quantity': 1}])

    def test_failure_at_the_payment_step_rolls_back_everything(self):
        b = self.full_body()
        before = self.counts()
        with mock.patch('operations.services._record_payment', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.api(self.cashier).post('/api/sales/', b, format='json')
        self.assertEqual(self.counts(), before)
        self.assertFalse(Sale.objects.filter(request_id=b['request_id']).exists())

    def test_failure_at_the_consignment_step_rolls_back_sale_lines_and_stock(self):
        b = self.full_body()
        before, stock_before = self.counts(), self.stock('Eau')
        with mock.patch('operations.services._record_consign', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.api(self.cashier).post('/api/sales/', b, format='json')
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.stock('Eau'), stock_before)

    def test_failure_at_the_stock_step_rolls_back_sale_and_lines(self):
        b = self.full_body()
        before = self.counts()
        with mock.patch('operations.services._record_stock', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.api(self.cashier).post('/api/sales/', b, format='json')
        self.assertEqual(self.counts(), before)

    def test_retry_after_a_failed_attempt_succeeds_once(self):
        b = self.full_body()
        with mock.patch('operations.services._record_payment', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.api(self.cashier).post('/api/sales/', b, format='json')
        r = self.api(self.cashier).post('/api/sales/', b, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Sale.objects.filter(request_id=b['request_id']).count(), 1)


class DebtTests(SaleTestCase):
    def debt(self, client):
        return services.client_debt(client)

    def test_credit_sale_creates_debt(self):
        self.sell([('Eau', 'pack', 2)], self.cafe, mode='credit')
        self.assertEqual(self.debt(self.cafe), 8400)
        self.assertEqual(Payment.objects.count(), 0)

    def test_partial_payment_reduces_debt_and_creates_payment_row(self):
        r = self.sell([('Eau', 'pack', 2)], self.cafe, mode='credit', paid_amount=3000)
        self.assertEqual(self.debt(self.cafe), 5400)
        self.assertEqual(r.data['paid_amount'], 3000)
        p = Payment.objects.get()
        self.assertEqual((p.amount, p.client_id, p.sale_id), (3000, self.cafe.pk, r.data['id']))

    def test_fully_paid_credit_sale_leaves_no_debt(self):
        self.sell([('Eau', 'pack', 2)], self.cafe, mode='credit', paid_amount=8400)
        self.assertEqual(self.debt(self.cafe), 0)

    def test_cash_sale_creates_no_debt_even_with_a_client(self):
        self.sell([('Eau', 'pack', 2)], self.cafe, mode='cash')
        self.assertEqual(self.debt(self.cafe), 0)
        self.assertEqual(Payment.objects.count(), 0)

    def test_debts_accumulate_and_are_per_client(self):
        self.sell([('Jus', 'unit', 1)], self.cafe, mode='credit')
        self.sell([('Jus', 'unit', 2)], self.cafe, mode='credit')
        self.sell([('Jus', 'unit', 1)], self.retailer, mode='credit')
        self.assertEqual((self.debt(self.cafe), self.debt(self.retailer)), (900 * 3, 1000))

    def test_credit_requires_client(self):
        before = self.counts()
        r = self.sell([('Jus', 'unit', 1)], None, mode='credit', expect=400)
        self.assertEqual(r.data['code'], 'credit_needs_client')
        self.assertEqual(self.counts(), before)

    def test_paid_amount_validation(self):
        before = self.counts()
        self.assertEqual(self.sell([('Jus', 'unit', 1)], self.cafe, 'credit', paid_amount=901, expect=400).data['code'], 'overpaid')
        self.assertEqual(self.sell([('Jus', 'unit', 1)], self.cafe, 'cash', paid_amount=100, expect=400).data['code'],
                         'paid_amount_not_allowed')
        for bad in (-5, 1.5, 'x'):
            self.sell([('Jus', 'unit', 1)], self.cafe, 'credit', paid_amount=bad, expect=400)
        self.assertEqual(self.counts(), before)

    def test_credit_limit_exceeded_rejected_without_rows(self):
        Client.objects.filter(pk=self.cafe.pk).update(credit_limit=10000)
        self.sell([('Eau', 'pack', 1)], self.cafe, mode='credit')  # dette 4200
        before = self.counts()
        r = self.sell([('Eau', 'pack', 2)], self.cafe, mode='credit', expect=400)  # 4200 + 8400 > 10000
        self.assertEqual(r.data['code'], 'credit_limit_exceeded')
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.debt(self.cafe), 4200)

    def test_credit_limit_boundary_and_partial_payment(self):
        Client.objects.filter(pk=self.cafe.pk).update(credit_limit=9000)
        self.sell([('Jus', 'unit', 10)], self.cafe, mode='credit')  # dette 9000 = plafond : accepté
        self.assertEqual(self.debt(self.cafe), 9000)
        r = self.sell([('Jus', 'unit', 1)], self.cafe, mode='credit', expect=400)  # 9900 > 9000
        self.assertEqual(r.data['code'], 'credit_limit_exceeded')
        # Payer le total de la nouvelle vente : aucune nouvelle dette, donc accepté.
        self.sell([('Jus', 'unit', 1)], self.cafe, mode='credit', paid_amount=900)
        self.assertEqual(self.debt(self.cafe), 9000)

    def test_credit_limit_zero_means_no_limit(self):
        self.assertEqual(self.cafe.credit_limit, 0)
        self.sell([('Eau', 'palette', 10)], self.cafe, mode='credit')
        self.assertEqual(self.debt(self.cafe), 380000)

    def test_cash_sale_ignores_credit_limit(self):
        Client.objects.filter(pk=self.cafe.pk).update(credit_limit=100)
        self.sell([('Eau', 'pack', 5)], self.cafe, mode='cash')


class ConsignmentTests(SaleTestCase):
    def holdings(self, client):
        return services.consign_holdings(client)

    def test_consignment_out_on_sale(self):
        r = self.sell([('Eau', 'pack', 2), ('Eau', 'palette', 1), ('Verre', 'unit', 12), ('Jus', 'unit', 1)], self.cafe)
        self.assertEqual(self.holdings(self.cafe), {'crate': 2 + 10, 'glass_bottle': 12})
        self.assertEqual({(c['consign_type'], c['qty_out']) for c in r.data['consignments']},
                         {('crate', 12), ('glass_bottle', 12)})

    def test_non_consignable_lines_create_no_movement(self):
        self.sell([('Jus', 'unit', 5), ('Eau', 'unit', 5)], self.cafe)
        self.assertEqual(ConsignMovement.objects.count(), 0)

    def test_returned_consignments_reduce_holdings(self):
        self.sell([('Eau', 'pack', 5), ('Verre', 'unit', 10)], self.cafe)
        r = self.sell([('Jus', 'unit', 1)], self.cafe, returned_consignments=[
            {'consign_type': 'crate', 'quantity': 3}, {'consign_type': 'glass_bottle', 'quantity': 4}])
        self.assertEqual(self.holdings(self.cafe), {'crate': 2, 'glass_bottle': 6})
        self.assertEqual({(c['consign_type'], c['qty_in']) for c in r.data['consignments']},
                         {('crate', 3), ('glass_bottle', 4)})

    def test_return_in_the_same_sale_as_a_purchase(self):
        self.sell([('Eau', 'pack', 2)], self.cafe)
        self.sell([('Eau', 'pack', 1)], self.cafe, returned_consignments=[{'consign_type': 'crate', 'quantity': 2}])
        self.assertEqual(self.holdings(self.cafe)['crate'], 1)

    def test_returning_more_than_held_is_rejected(self):
        self.sell([('Eau', 'pack', 2)], self.cafe)
        before = self.counts()
        r = self.sell([('Jus', 'unit', 1)], self.cafe, expect=400,
                      returned_consignments=[{'consign_type': 'crate', 'quantity': 3}])
        self.assertEqual(r.data['code'], 'consign_return_exceeds_holdings')
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.holdings(self.cafe)['crate'], 2)

    def test_return_cannot_count_the_crates_of_the_same_sale(self):
        before = self.counts()
        self.sell([('Eau', 'pack', 2)], self.cafe, expect=400,
                  returned_consignments=[{'consign_type': 'crate', 'quantity': 1}])
        self.assertEqual(self.counts(), before)

    def test_split_returns_of_same_type_are_summed_for_the_check(self):
        self.sell([('Eau', 'pack', 2)], self.cafe)
        self.sell([('Jus', 'unit', 1)], self.cafe, expect=400, returned_consignments=[
            {'consign_type': 'crate', 'quantity': 1}, {'consign_type': 'crate', 'quantity': 2}])

    def test_return_of_a_type_never_held_is_rejected(self):
        self.sell([('Eau', 'pack', 2)], self.cafe)
        self.sell([('Jus', 'unit', 1)], self.cafe, expect=400,
                  returned_consignments=[{'consign_type': 'glass_bottle', 'quantity': 1}])

    def test_walk_in_with_consignable_product_is_rejected(self):
        before = self.counts()
        r = self.sell([('Jus', 'unit', 1), ('Eau', 'unit', 1)], None, expect=400)
        self.assertEqual(r.data['code'], 'consignable_needs_client')
        self.assertEqual(self.counts(), before)

    def test_walk_in_cannot_return_consignments(self):
        self.sell([('Jus', 'unit', 1)], None, expect=400,
                  returned_consignments=[{'consign_type': 'crate', 'quantity': 1}])

    def test_holdings_are_per_client(self):
        self.sell([('Eau', 'pack', 2)], self.cafe)
        self.assertEqual(self.holdings(self.retailer), {'crate': 0, 'glass_bottle': 0})


class IdempotencyTests(SaleTestCase):
    def test_same_request_id_twice_creates_one_sale(self):
        b = self.body([('Eau', 'pack', 2)], self.cafe, mode='credit', paid_amount=1000)
        a = self.api(self.cashier)
        first = a.post('/api/sales/', b, format='json')
        second = a.post('/api/sales/', b, format='json')
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(self.stock('Eau'), self.INITIAL_STOCK - 12)
        self.assertEqual(services.client_debt(self.cafe), 7400)
        self.assertEqual(services.consign_holdings(self.cafe)['crate'], 2)
        self.assertEqual(Payment.objects.count(), 1)

    def test_replay_returns_original_even_if_payload_differs(self):
        b = self.body([('Eau', 'pack', 2)], self.cafe)
        first = self.api(self.cashier).post('/api/sales/', b, format='json')
        b['lines'][0]['quantity'] = 5
        second = self.api(self.cashier).post('/api/sales/', b, format='json')
        self.assertEqual(second.data['id'], first.data['id'])
        self.assertEqual(second.data['total'], first.data['total'])
        self.assertEqual(Sale.objects.count(), 1)

    def test_different_request_ids_create_two_sales(self):
        self.sell([('Jus', 'unit', 1)])
        self.sell([('Jus', 'unit', 1)])
        self.assertEqual(Sale.objects.count(), 2)

    def test_request_id_is_required_and_must_be_a_uuid(self):
        b = self.body([('Jus', 'unit', 1)])
        del b['request_id']
        self.assertEqual(self.api(self.cashier).post('/api/sales/', b, format='json').status_code, 400)
        b['request_id'] = 'abc'
        self.assertEqual(self.api(self.cashier).post('/api/sales/', b, format='json').status_code, 400)
        self.assertEqual(Sale.objects.count(), 0)

    def test_request_id_unique_in_database(self):
        from django.db import IntegrityError, transaction
        rid = uuid.uuid4()
        Sale.objects.create(mode='cash', total=1, user=self.manager, request_id=rid)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Sale.objects.create(mode='cash', total=1, user=self.manager, request_id=rid)


class InputValidationTests(SaleTestCase):
    def test_invalid_inputs_are_rejected_and_leave_nothing(self):
        before = self.counts()
        bad_bodies = {
            'no lines': self.body([], self.cafe),
            'zero qty': self.body([('Jus', 'unit', 0)], self.cafe),
            'negative qty': self.body([('Jus', 'unit', -1)], self.cafe),
            'float qty': self.body([('Jus', 'unit', 1.5)], self.cafe),
            'bad mode': self.body([('Jus', 'unit', 1)], self.cafe, mode='cheque'),
            'unknown client': {**self.body([('Jus', 'unit', 1)]), 'client_id': 99999},
            'unknown product': {**self.body([('Jus', 'unit', 1)]), 'lines': [{'product_id': 99999, 'unit': 'unit', 'quantity': 1}]},
            'unknown unit': self.body([('Jus', 'carton', 1)], self.cafe),
            'bad return type': self.body([('Jus', 'unit', 1)], self.cafe, returned_consignments=[{'consign_type': 'x', 'quantity': 1}]),
            'zero return': self.body([('Jus', 'unit', 1)], self.cafe, returned_consignments=[{'consign_type': 'crate', 'quantity': 0}]),
        }
        for label, b in bad_bodies.items():
            with self.subTest(label):
                self.assertEqual(self.api(self.cashier).post('/api/sales/', b, format='json').status_code, 400)
        self.assertEqual(self.counts(), before)

    def test_inactive_client_and_product_rejected(self):
        Client.objects.filter(pk=self.cafe.pk).update(is_active=False)
        self.sell([('Jus', 'unit', 1)], self.cafe, expect=400)
        Product.objects.filter(pk=self.products['Jus'].pk).update(is_active=False)
        self.sell([('Jus', 'unit', 1)], expect=400)


class CancelTests(SaleTestCase):
    def snapshot(self, client):
        return (self.stock('Eau'), self.stock('Jus'), services.client_debt(client), services.consign_holdings(client))

    def test_cancel_restores_stock_debt_and_consignments_exactly(self):
        self.sell([('Eau', 'pack', 4)], self.cafe, mode='credit')  # dette + 4 caisses, avant
        start = self.snapshot(self.cafe)
        sale = self.sell([('Eau', 'pack', 2), ('Jus', 'unit', 3), ('Verre', 'unit', 5)], self.cafe, mode='credit',
                         paid_amount=2000, returned_consignments=[{'consign_type': 'crate', 'quantity': 1}]).data
        self.assertNotEqual(self.snapshot(self.cafe), start)
        r = self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.snapshot(self.cafe), start)
        self.assertEqual(self.stock('Verre'), self.INITIAL_STOCK)
        self.assertEqual(r.data['reverses'], sale['id'])
        self.assertEqual(r.data['total'], -sale['total'])
        self.assertEqual(r.data['paid_amount'], -2000)

    def test_cancel_never_edits_or_deletes_the_original(self):
        sale = self.sell([('Eau', 'pack', 2)], self.cafe, mode='credit', paid_amount=500).data
        rows_before = {
            'sale': list(Sale.objects.filter(pk=sale['id']).values()),
            'lines': list(SaleLine.objects.filter(sale_id=sale['id']).values()),
            'stock': list(StockMovement.objects.filter(sale_id=sale['id']).values()),
            'consign': list(ConsignMovement.objects.filter(sale_id=sale['id']).values()),
            'pay': list(Payment.objects.filter(sale_id=sale['id']).values()),
        }
        reversal = self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/').data
        self.assertEqual(rows_before, {
            'sale': list(Sale.objects.filter(pk=sale['id']).values()),
            'lines': list(SaleLine.objects.filter(sale_id=sale['id']).values()),
            'stock': list(StockMovement.objects.filter(sale_id=sale['id']).values()),
            'consign': list(ConsignMovement.objects.filter(sale_id=sale['id']).values()),
            'pay': list(Payment.objects.filter(sale_id=sale['id']).values()),
        })
        # Les écritures inverses sont de nouvelles lignes rattachées à la vente d'annulation.
        self.assertEqual(StockMovement.objects.filter(sale_id=reversal['id']).count(), 1)
        self.assertEqual(Payment.objects.filter(sale_id=reversal['id']).count(), 1)
        self.assertEqual(ConsignMovement.objects.filter(sale_id=reversal['id']).count(), 1)
        self.assertEqual(self.api(self.manager).get(f'/api/sales/{sale["id"]}/').data['reversed_by'], reversal['id'])

    def test_cancel_cash_walk_in_sale(self):
        sale = self.sell([('Jus', 'unit', 3)]).data
        self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/')
        self.assertEqual(self.stock('Jus'), self.INITIAL_STOCK)

    def test_cannot_cancel_twice(self):
        sale = self.sell([('Jus', 'unit', 3)], self.cafe, mode='credit').data
        a = self.api(self.manager)
        self.assertEqual(a.post(f'/api/sales/{sale["id"]}/cancel/').status_code, 201)
        before = self.counts()
        r = a.post(f'/api/sales/{sale["id"]}/cancel/')
        self.assertEqual((r.status_code, r.data['code']), (400, 'already_cancelled'))
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.stock('Jus'), self.INITIAL_STOCK)
        self.assertEqual(services.client_debt(self.cafe), 0)

    def test_a_reversing_sale_cannot_be_cancelled(self):
        sale = self.sell([('Jus', 'unit', 3)]).data
        reversal = self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/').data
        before = self.counts()
        r = self.api(self.manager).post(f'/api/sales/{reversal["id"]}/cancel/')
        self.assertEqual((r.status_code, r.data['code']), (400, 'cannot_cancel_reversal'))
        self.assertEqual(self.counts(), before)

    def test_cancel_refused_if_client_already_returned_the_crates(self):
        sale = self.sell([('Eau', 'pack', 1)], self.cafe).data
        self.sell([('Jus', 'unit', 1)], self.cafe, returned_consignments=[{'consign_type': 'crate', 'quantity': 1}])
        before = self.counts()
        r = self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/')
        self.assertEqual((r.status_code, r.data['code']), (400, 'cancel_consign_conflict'))
        self.assertEqual(self.counts(), before)

    def test_cancel_unknown_sale_is_404(self):
        self.assertEqual(self.api(self.manager).post('/api/sales/99999/cancel/').status_code, 404)

    def test_failure_during_cancel_rolls_back(self):
        sale = self.sell([('Eau', 'pack', 2)], self.cafe, mode='credit', paid_amount=500).data
        before, snap = self.counts(), self.snapshot(self.cafe)
        with mock.patch('operations.services.Payment.objects.create', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/')
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.snapshot(self.cafe), snap)


class PermissionTests(SaleTestCase):
    def test_delivery_is_forbidden_everywhere(self):
        sale = self.sell([('Jus', 'unit', 1)]).data
        a = self.api(self.delivery)
        before = self.counts()
        self.assertEqual(a.post('/api/sales/', self.body([('Jus', 'unit', 1)]), format='json').status_code, 403)
        self.assertEqual(a.get('/api/sales/').status_code, 403)
        self.assertEqual(a.get(f'/api/sales/{sale["id"]}/').status_code, 403)
        self.assertEqual(a.post(f'/api/sales/{sale["id"]}/cancel/').status_code, 403)
        self.assertEqual(self.counts(), before)

    def test_manager_and_cashier_can_create(self):
        for user in (self.manager, self.cashier):
            r = self.sell([('Jus', 'unit', 1)], user=user)
            self.assertEqual(r.data['user_name'], user.name)

    def test_only_manager_can_cancel(self):
        sale = self.sell([('Jus', 'unit', 1)]).data
        before = self.counts()
        self.assertEqual(self.api(self.cashier).post(f'/api/sales/{sale["id"]}/cancel/').status_code, 403)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/').status_code, 201)

    def test_manager_and_cashier_can_list_and_retrieve(self):
        sale = self.sell([('Jus', 'unit', 1)]).data
        for user in (self.manager, self.cashier):
            a = self.api(user)
            self.assertEqual(len(a.get('/api/sales/').data), 1)
            self.assertEqual(a.get(f'/api/sales/{sale["id"]}/').status_code, 200)

    def test_anonymous_is_rejected(self):
        a = APIClient()
        self.assertEqual(a.get('/api/sales/').status_code, 401)
        self.assertEqual(a.post('/api/sales/', self.body([('Jus', 'unit', 1)]), format='json').status_code, 401)
        self.assertEqual(a.post('/api/sales/1/cancel/').status_code, 401)

    def test_sales_cannot_be_edited_or_deleted_through_the_api(self):
        sale = self.sell([('Jus', 'unit', 1)]).data
        for method in ('put', 'patch', 'delete'):
            r = getattr(self.api(self.manager), method)(f'/api/sales/{sale["id"]}/', {}, format='json')
            self.assertEqual(r.status_code, 405)


class ListTests(SaleTestCase):
    def test_retrieve_returns_lines(self):
        sale = self.sell([('Eau', 'pack', 2), ('Jus', 'unit', 1)], self.cafe).data
        d = self.api(self.cashier).get(f'/api/sales/{sale["id"]}/').data
        self.assertEqual(len(d['lines']), 2)
        self.assertEqual({(l['product_name'], l['unit'], l['quantity'], l['unit_price'], l['line_total'])
                          for l in d['lines']}, {('Eau', 'pack', 2, 4200, 8400), ('Jus', 'unit', 1, 900, 900)})

    def test_filter_by_client(self):
        self.sell([('Jus', 'unit', 1)], self.cafe)
        self.sell([('Jus', 'unit', 1)], self.retailer)
        self.sell([('Jus', 'unit', 1)])
        a = self.api(self.manager)
        self.assertEqual({s['client'] for s in a.get(f'/api/sales/?client={self.cafe.pk}').data}, {self.cafe.pk})
        self.assertEqual(len(a.get('/api/sales/').data), 3)
        self.assertEqual(a.get('/api/sales/?client=abc').status_code, 400)

    def test_filter_by_date(self):
        ids = [self.sell([('Jus', 'unit', 1)]).data['id'] for _ in range(3)]
        for sale_id, day in zip(ids, (5, 10, 15)):
            Sale.objects.filter(pk=sale_id).update(created_at=timezone.make_aware(datetime(2026, 3, day, 12, 0)))
        a = self.api(self.manager)
        got = lambda q: sorted(s['id'] for s in a.get('/api/sales/' + q).data)
        self.assertEqual(got('?date_from=2026-03-10'), sorted(ids[1:]))
        self.assertEqual(got('?date_to=2026-03-10'), sorted(ids[:2]))
        self.assertEqual(got('?date_from=2026-03-10&date_to=2026-03-10'), [ids[1]])
        self.assertEqual(got('?date_from=2027-01-01'), [])
        self.assertEqual(a.get('/api/sales/?date_from=not-a-date').status_code, 400)

    def test_list_is_newest_first(self):
        first = self.sell([('Jus', 'unit', 1)]).data['id']
        second = self.sell([('Jus', 'unit', 1)]).data['id']
        self.assertEqual([s['id'] for s in self.api(self.manager).get('/api/sales/').data], [second, first])


class ClientBalanceFieldTests(SaleTestCase):
    def test_client_endpoints_expose_computed_debt_and_holdings(self):
        self.sell([('Eau', 'pack', 2), ('Verre', 'unit', 3)], self.cafe, mode='credit', paid_amount=1000)
        for user in (self.manager, self.cashier):
            a = self.api(user)
            one = a.get(f'/api/clients/{self.cafe.pk}/').data
            self.assertEqual(one['debt'], 2 * 4200 + 3 * 1100 - 1000)
            self.assertEqual(one['consign_holdings'], {'crate': 2, 'glass_bottle': 3})
            listed = next(c for c in a.get('/api/clients/').data if c['id'] == self.cafe.pk)
            self.assertEqual(listed['debt'], one['debt'])
        self.assertEqual(self.api(self.manager).get(f'/api/clients/{self.retailer.pk}/').data['debt'], 0)

    def test_balance_fields_are_read_only(self):
        r = self.api(self.manager).patch(f'/api/clients/{self.cafe.pk}/',
                                         {'debt': 99999, 'consign_holdings': {'crate': 9}}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['debt'], 0)
        self.assertEqual(r.data['consign_holdings'], {'crate': 0, 'glass_bottle': 0})

    def test_debt_returns_to_zero_after_cancel(self):
        sale = self.sell([('Eau', 'pack', 2)], self.cafe, mode='credit', paid_amount=1000).data
        self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/')
        self.assertEqual(self.api(self.manager).get(f'/api/clients/{self.cafe.pk}/').data['debt'], 0)


class StressTests(SaleTestCase):
    INITIAL_STOCK = 100_000

    def test_fifty_sequential_sales_stay_consistent_with_the_movements(self):
        rng = random.Random(2026)
        clients = {self.cafe.pk: self.cafe, self.wholesaler.pk: self.wholesaler, self.retailer.pk: self.retailer}
        exp_stock = {n: self.INITIAL_STOCK for n in CONSIGNABLE}
        exp_debt = {pk: 0 for pk in clients}
        exp_hold = {pk: {'crate': 0, 'glass_bottle': 0} for pk in clients}
        exp_sales_total = 0
        n_credit = n_payments = 0
        keys = list(CATALOG)
        created = []

        for i in range(50):
            walk_in = rng.random() < 0.15
            client = None if walk_in else rng.choice(list(clients.values()))
            ctype = client.type if client else 'retail'
            picks = [k for k in keys if not (walk_in and CONSIGNABLE[k[0]])]
            lines = [(*rng.choice(picks), rng.randint(1, 3)) for _ in range(rng.randint(1, 3))]
            mode = 'credit' if client and rng.random() < 0.6 else 'cash'
            total = sum(CATALOG[(p, u)][2][ctype] * q for p, u, q in lines)
            extra = {}
            paid = 0
            if mode == 'credit' and rng.random() < 0.5:
                paid = rng.randint(1, total)
                extra['paid_amount'] = paid
            ret = {}
            if client and rng.random() < 0.4:
                held = exp_hold[client.pk]
                for t in ('crate', 'glass_bottle'):
                    if held[t] and rng.random() < 0.7:
                        ret[t] = rng.randint(1, held[t])
                if ret:
                    extra['returned_consignments'] = [{'consign_type': t, 'quantity': q} for t, q in ret.items()]

            r = self.sell(lines, client, mode, **extra)
            created.append(r.data['id'])
            self.assertEqual(r.data['total'], total)

            exp_sales_total += total
            for p, u, q in lines:
                factor, consign, _ = CATALOG[(p, u)]
                exp_stock[p] -= factor * q
                if client and consign:
                    exp_hold[client.pk][consign[0]] += consign[1] * q
            for t, q in ret.items():
                exp_hold[client.pk][t] -= q
            if mode == 'credit':
                n_credit += 1
                exp_debt[client.pk] += total - paid
                n_payments += 1 if paid else 0

        # 1) les soldes calculés par le service = les attentes calculées indépendamment
        for name in CONSIGNABLE:
            self.assertEqual(self.stock(name), exp_stock[name], name)
        for pk, c in clients.items():
            self.assertEqual(services.client_debt(c), exp_debt[pk])
            self.assertEqual(services.consign_holdings(c), exp_hold[pk])

        # 2) les soldes = somme brute des mouvements en base
        for name, p in self.products.items():
            raw = StockMovement.objects.filter(product=p).aggregate(s=Sum('quantity'))['s']
            self.assertEqual(raw, exp_stock[name])
        raw_credit = Sale.objects.filter(mode='credit').aggregate(s=Sum('total'))['s'] or 0
        raw_paid = Payment.objects.aggregate(s=Sum('amount'))['s'] or 0
        self.assertEqual(raw_credit - raw_paid, sum(exp_debt.values()))
        self.assertEqual(Payment.objects.count(), n_payments)
        self.assertEqual(Sale.objects.count(), 50)
        self.assertEqual(Sale.objects.aggregate(s=Sum('total'))['s'], exp_sales_total)

        # 3) chaque vente = somme de ses lignes ; une ligne de stock par ligne de vente
        for sale in Sale.objects.all():
            self.assertEqual(sale.total, sum(l.quantity * l.unit_price for l in sale.lines.all()))
        self.assertEqual(StockMovement.objects.filter(reason='sale').count(), SaleLine.objects.count())

        # 4) annuler toutes les ventes remet tout à l'état initial
        a = self.api(self.manager)
        for sale_id in reversed(created):
            r = a.post(f'/api/sales/{sale_id}/cancel/')
            self.assertEqual(r.status_code, 201, r.data)
        for name in CONSIGNABLE:
            self.assertEqual(self.stock(name), self.INITIAL_STOCK)
        for c in clients.values():
            self.assertEqual(services.client_debt(c), 0)
            self.assertEqual(services.consign_holdings(c), {'crate': 0, 'glass_bottle': 0})
