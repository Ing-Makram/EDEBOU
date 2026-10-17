import uuid
from datetime import datetime

from django.db.models import Sum
from django.utils import timezone
from rest_framework.test import APIClient

from catalog.models import Client

from . import services
from .models import ConsignMovement, Payment, Sale
from .testbase import SaleTestCase


class PaymentTestCase(SaleTestCase):
    def pay(self, client, amount, user=None, expect=201, **extra):
        body = {'request_id': str(uuid.uuid4()), 'client_id': client.pk, 'amount': amount, **extra}
        r = self.api(user or self.cashier).post('/api/payments/', body, format='json')
        self.assertEqual(r.status_code, expect, r.data)
        return r

    def debt(self, client):
        return services.client_debt(client)

    def owe(self, client, packs=2):
        """Vente à crédit de `packs` unités de jus : dette = quantité × prix du type de client."""
        return self.sell([('Jus', 'unit', packs)], client, mode='credit').data


class PaymentCreateTests(PaymentTestCase):
    def test_payment_decreases_debt(self):
        self.owe(self.cafe, 10)  # 9000
        r = self.pay(self.cafe, 4000)
        self.assertEqual(self.debt(self.cafe), 5000)
        self.assertEqual(r.data['amount'], 4000)
        self.assertEqual(r.data['client'], self.cafe.pk)
        self.assertIsNone(r.data['warning'])
        self.pay(self.cafe, 5000)
        self.assertEqual(self.debt(self.cafe), 0)

    def test_payment_does_not_touch_stock_or_consignments(self):
        self.owe(self.cafe)
        stock, holdings, rows = self.stock('Jus'), services.consign_holdings(self.cafe), ConsignMovement.objects.count()
        self.pay(self.cafe, 100)
        self.assertEqual((self.stock('Jus'), services.consign_holdings(self.cafe), ConsignMovement.objects.count()),
                         (stock, holdings, rows))

    def test_payment_linked_to_a_credit_sale(self):
        sale = self.owe(self.cafe, 4)
        r = self.pay(self.cafe, 1000, sale_id=sale['id'])
        self.assertEqual(r.data['sale'], sale['id'])
        self.assertEqual(self.debt(self.cafe), 3600 - 1000)
        self.assertEqual(self.api(self.manager).get(f'/api/sales/{sale["id"]}/').data['paid_amount'], 1000)

    def test_payment_exceeding_debt_becomes_credit_and_warns(self):
        self.owe(self.cafe, 2)  # 1800
        r = self.pay(self.cafe, 2500)
        self.assertEqual(self.debt(self.cafe), -700)
        self.assertEqual(r.data['warning'], {'code': 'exceeds_debt', 'debt_before': 1800, 'credit_after': 700})
        self.assertEqual(self.api(self.manager).get(f'/api/clients/{self.cafe.pk}/').data['debt'], -700)

    def test_payment_exactly_equal_to_debt_has_no_warning(self):
        self.owe(self.cafe, 2)
        self.assertIsNone(self.pay(self.cafe, 1800).data['warning'])
        self.assertEqual(self.debt(self.cafe), 0)

    def test_payment_with_no_debt_warns_and_credit_accumulates(self):
        r = self.pay(self.cafe, 500)
        self.assertEqual(r.data['warning'], {'code': 'exceeds_debt', 'debt_before': 0, 'credit_after': 500})
        r = self.pay(self.cafe, 300)
        self.assertEqual(r.data['warning']['debt_before'], -500)
        self.assertEqual(r.data['warning']['credit_after'], 800)  # solde créditeur total après paiement
        self.assertEqual(self.debt(self.cafe), -800)

    def test_credit_balance_is_used_by_next_credit_sale_and_limit_check(self):
        Client.objects.filter(pk=self.cafe.pk).update(credit_limit=1000)
        self.pay(self.cafe, 5000)  # avance
        self.sell([('Jus', 'unit', 5)], self.cafe, mode='credit')  # 4500 : dette -5000+4500 = -500
        self.assertEqual(self.debt(self.cafe), -500)

    def test_amount_validation(self):
        before = Payment.objects.count()
        for bad in (0, -1, 1.5, 'abc', None, 10 ** 13):
            with self.subTest(amount=bad):
                self.pay(self.cafe, bad, expect=400)
        self.assertEqual(Payment.objects.count(), before)

    def test_client_and_request_id_validation(self):
        a = self.api(self.cashier)
        ok = {'request_id': str(uuid.uuid4()), 'client_id': self.cafe.pk, 'amount': 100}
        for label, patch in {'no client': {'client_id': None}, 'unknown client': {'client_id': 99999},
                             'no request id': {'request_id': None}, 'bad request id': {'request_id': 'x'}}.items():
            with self.subTest(label):
                self.assertEqual(a.post('/api/payments/', {**ok, **patch}, format='json').status_code, 400)
        Client.objects.filter(pk=self.cafe.pk).update(is_active=False)
        self.assertEqual(a.post('/api/payments/', ok, format='json').status_code, 400)
        self.assertEqual(Payment.objects.count(), 0)

    def test_linked_sale_validation(self):
        other = self.owe(self.retailer)
        cash = self.sell([('Jus', 'unit', 1)], self.cafe, mode='cash').data
        cancelled = self.owe(self.cafe)
        self.api(self.manager).post(f'/api/sales/{cancelled["id"]}/cancel/')
        reversal_id = Sale.objects.get(reverses_id=cancelled['id']).pk
        cases = {'unknown sale': (99999, 'sale_not_found'), "other client's sale": (other['id'], 'sale_client_mismatch'),
                 'cash sale': (cash['id'], 'sale_not_credit'), 'cancelled sale': (cancelled['id'], 'sale_cancelled'),
                 'reversal sale': (reversal_id, 'sale_cancelled')}
        for label, (sale_id, code) in cases.items():
            with self.subTest(label):
                r = self.pay(self.cafe, 100, expect=400, sale_id=sale_id)
                self.assertEqual(r.data['code'], code)
        self.assertEqual(Payment.objects.count(), 0)

    def test_same_request_id_twice_creates_one_payment(self):
        self.owe(self.cafe, 10)
        body = {'request_id': str(uuid.uuid4()), 'client_id': self.cafe.pk, 'amount': 4000}
        a = self.api(self.cashier)
        first, second = a.post('/api/payments/', body, format='json'), a.post('/api/payments/', body, format='json')
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.debt(self.cafe), 5000)

    def test_replay_returns_original_even_if_amount_differs(self):
        body = {'request_id': str(uuid.uuid4()), 'client_id': self.cafe.pk, 'amount': 4000}
        a = self.api(self.cashier)
        first = a.post('/api/payments/', body, format='json')
        second = a.post('/api/payments/', {**body, 'amount': 1}, format='json')
        self.assertEqual(second.data['amount'], first.data['amount'])
        self.assertEqual(Payment.objects.count(), 1)

    def test_payment_request_id_is_unique_in_the_database(self):
        from django.db import IntegrityError, transaction
        rid = uuid.uuid4()
        Payment.objects.create(client=self.cafe, amount=1, user=self.manager, request_id=rid)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(client=self.cafe, amount=1, user=self.manager, request_id=rid)

    def test_payments_cannot_be_edited_or_deleted_through_the_api(self):
        p = self.pay(self.cafe, 100).data
        for method in ('put', 'patch', 'delete'):
            r = getattr(self.api(self.manager), method)(f'/api/payments/{p["id"]}/', {}, format='json')
            self.assertIn(r.status_code, (404, 405))
        self.assertEqual(Payment.objects.get(pk=p['id']).amount, 100)


class PaymentPermissionTests(PaymentTestCase):
    def test_manager_and_cashier_can_create_and_list(self):
        for user in (self.manager, self.cashier):
            self.pay(self.cafe, 100, user=user)
            self.assertEqual(self.api(user).get('/api/payments/').status_code, 200)

    def test_delivery_has_no_access(self):
        p = self.pay(self.cafe, 100).data
        a = self.api(self.delivery)
        before = Payment.objects.count()
        self.pay(self.cafe, 100, user=self.delivery, expect=403)
        self.assertEqual(a.get('/api/payments/').status_code, 403)
        self.assertEqual(a.post(f'/api/payments/{p["id"]}/cancel/').status_code, 403)
        self.assertEqual(Payment.objects.count(), before)

    def test_only_manager_can_cancel(self):
        p = self.pay(self.cafe, 100).data
        self.assertEqual(self.api(self.cashier).post(f'/api/payments/{p["id"]}/cancel/').status_code, 403)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.api(self.manager).post(f'/api/payments/{p["id"]}/cancel/').status_code, 201)

    def test_anonymous_is_rejected(self):
        a = APIClient()
        self.assertEqual(a.get('/api/payments/').status_code, 401)
        self.assertEqual(a.post('/api/payments/', {}, format='json').status_code, 401)
        self.assertEqual(a.post('/api/payments/1/cancel/').status_code, 401)
        self.assertEqual(a.get(f'/api/clients/{self.cafe.pk}/statement/').status_code, 401)


class PaymentCancelTests(PaymentTestCase):
    def test_cancel_creates_reversing_row_and_restores_debt(self):
        self.owe(self.cafe, 10)
        p = self.pay(self.cafe, 4000).data
        self.assertEqual(self.debt(self.cafe), 5000)
        r = self.api(self.manager).post(f'/api/payments/{p["id"]}/cancel/')
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.data['amount'], r.data['reverses']), (-4000, p['id']))
        self.assertEqual(self.debt(self.cafe), 9000)
        self.assertEqual(Payment.objects.count(), 2)

    def test_cancel_never_edits_the_original(self):
        p = self.pay(self.cafe, 4000).data
        before = list(Payment.objects.filter(pk=p['id']).values())
        self.api(self.manager).post(f'/api/payments/{p["id"]}/cancel/')
        self.assertEqual(list(Payment.objects.filter(pk=p['id']).values()), before)
        listed = next(x for x in self.api(self.manager).get('/api/payments/').data if x['id'] == p['id'])
        self.assertIsNotNone(listed['reversed_by'])

    def test_cancel_only_once(self):
        p = self.pay(self.cafe, 100).data
        a = self.api(self.manager)
        a.post(f'/api/payments/{p["id"]}/cancel/')
        r = a.post(f'/api/payments/{p["id"]}/cancel/')
        self.assertEqual((r.status_code, r.data['code']), (400, 'already_cancelled'))
        self.assertEqual(Payment.objects.count(), 2)
        self.assertEqual(self.debt(self.cafe), 0)

    def test_a_reversing_payment_cannot_be_cancelled(self):
        p = self.pay(self.cafe, 100).data
        rev = self.api(self.manager).post(f'/api/payments/{p["id"]}/cancel/').data
        r = self.api(self.manager).post(f'/api/payments/{rev["id"]}/cancel/')
        self.assertEqual((r.status_code, r.data['code']), (400, 'cannot_cancel_reversal'))
        self.assertEqual(Payment.objects.count(), 2)

    def test_cancel_unknown_payment_is_404(self):
        self.assertEqual(self.api(self.manager).post('/api/payments/99999/cancel/').status_code, 404)

    def test_cancelling_the_payment_made_at_sale_then_the_sale_does_not_reverse_it_twice(self):
        sale = self.sell([('Eau', 'pack', 2)], self.cafe, mode='credit', paid_amount=3000).data
        at_sale = Payment.objects.get(sale_id=sale['id'], at_sale=True)
        self.api(self.manager).post(f'/api/payments/{at_sale.pk}/cancel/')
        self.assertEqual(self.debt(self.cafe), 8400)
        self.assertEqual(self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/').status_code, 201)
        self.assertEqual(self.debt(self.cafe), 0)
        self.assertEqual(Payment.objects.filter(reverses=at_sale).count(), 1)

    def test_cancelling_a_sale_does_not_reverse_a_payment_already_cancelled_and_vice_versa(self):
        sale = self.sell([('Eau', 'pack', 2)], self.cafe, mode='credit', paid_amount=3000).data
        self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/')
        at_sale = Payment.objects.get(sale_id=sale['id'], at_sale=True)
        r = self.api(self.manager).post(f'/api/payments/{at_sale.pk}/cancel/')
        self.assertEqual((r.status_code, r.data['code']), (400, 'already_cancelled'))
        self.assertEqual(self.debt(self.cafe), 0)


class CancelSaleAfterLaterPaymentsTests(PaymentTestCase):
    """Annuler une vente à crédit après des paiements ultérieurs : le client passe en avance, sans erreur."""

    def test_balance_becomes_a_credit_in_the_clients_favour(self):
        sale = self.sell([('Eau', 'pack', 2)], self.cafe, mode='credit').data  # dette 8400
        self.pay(self.cafe, 5000)
        self.assertEqual(self.debt(self.cafe), 3400)
        r = self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.debt(self.cafe), -5000)  # avance de 5000, pas ramenée à 0
        self.assertEqual(self.api(self.manager).get(f'/api/clients/{self.cafe.pk}/').data['debt'], -5000)
        self.assertEqual(self.api(self.cashier).get(f'/api/clients/{self.cafe.pk}/statement/').data['debt'], -5000)

    def test_later_payment_linked_to_the_sale_is_kept_when_the_sale_is_cancelled(self):
        sale = self.sell([('Eau', 'pack', 2)], self.cafe, mode='credit', paid_amount=1000).data
        later = self.pay(self.cafe, 2000, sale_id=sale['id']).data
        self.assertEqual(self.debt(self.cafe), 8400 - 3000)
        self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/')
        # le paiement fait à la vente (1000) est annulé avec elle ; le paiement ultérieur (2000) reste
        self.assertEqual(self.debt(self.cafe), -2000)
        self.assertFalse(Payment.objects.filter(reverses_id=later['id']).exists())

    def test_cancel_after_overpayment_does_not_clamp_or_error(self):
        sale = self.sell([('Jus', 'unit', 1)], self.cafe, mode='credit').data  # 900
        self.pay(self.cafe, 10000)  # avance déjà : -9100
        self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/')
        self.assertEqual(self.debt(self.cafe), -10000)

    def test_credit_balance_then_a_new_payment_cancel_returns_exactly(self):
        sale = self.sell([('Eau', 'pack', 2)], self.cafe, mode='credit').data
        p = self.pay(self.cafe, 5000).data
        self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/')
        self.api(self.manager).post(f'/api/payments/{p["id"]}/cancel/')
        self.assertEqual(self.debt(self.cafe), 0)


class PaymentListTests(PaymentTestCase):
    def test_list_newest_first_and_filters(self):
        ids = [self.pay(c, 100 * (i + 1)).data['id'] for i, c in enumerate((self.cafe, self.retailer, self.cafe))]
        a = self.api(self.manager)
        self.assertEqual([p['id'] for p in a.get('/api/payments/').data], ids[::-1])
        self.assertEqual({p['client'] for p in a.get(f'/api/payments/?client={self.cafe.pk}').data}, {self.cafe.pk})
        self.assertEqual(len(a.get(f'/api/payments/?client={self.cafe.pk}').data), 2)
        for pid, day in zip(ids, (5, 10, 15)):
            Payment.objects.filter(pk=pid).update(created_at=timezone.make_aware(datetime(2026, 3, day, 12)))
        got = lambda q: sorted(p['id'] for p in a.get('/api/payments/' + q).data)
        self.assertEqual(got('?date_from=2026-03-10'), sorted(ids[1:]))
        self.assertEqual(got('?date_to=2026-03-10'), sorted(ids[:2]))
        self.assertEqual(got(f'?client={self.cafe.pk}&date_from=2026-03-10'), [ids[2]])
        self.assertEqual(a.get('/api/payments/?date_to=zz').status_code, 400)
        self.assertEqual(a.get('/api/payments/?client=abc').status_code, 400)


class StatementTests(PaymentTestCase):
    def statement(self, client, user=None):
        r = self.api(user or self.cashier).get(f'/api/clients/{client.pk}/statement/')
        self.assertEqual(r.status_code, 200)
        return r.data

    def build_history(self):
        s1 = self.sell([('Eau', 'pack', 2), ('Jus', 'unit', 1)], self.cafe, mode='credit', paid_amount=1000).data
        self.pay(self.cafe, 2000)
        self.sell([('Jus', 'unit', 2)], self.cafe, mode='cash')
        self.sell([('Jus', 'unit', 1)], self.cafe, returned_consignments=[{'consign_type': 'crate', 'quantity': 1}])
        p = self.pay(self.cafe, 500).data
        self.api(self.manager).post(f'/api/payments/{p["id"]}/cancel/')
        s2 = self.sell([('Verre', 'unit', 3)], self.cafe, mode='credit').data
        self.api(self.manager).post(f'/api/sales/{s2["id"]}/cancel/')
        return s1

    def test_entries_are_chronological_with_running_balance(self):
        self.build_history()
        st = self.statement(self.cafe)
        dates = [e['date'] for e in st['entries']]
        self.assertEqual(dates, sorted(dates))
        running = 0
        for e in st['entries']:
            running += e['debt_delta']
            self.assertEqual(e['debt_after'], running)
        self.assertEqual({e['type'] for e in st['entries']}, {'sale', 'payment', 'consign'})

    def test_final_balance_equals_the_computed_debt_and_the_raw_sums(self):
        self.build_history()
        st = self.statement(self.cafe)
        raw_credit = Sale.objects.filter(client=self.cafe, mode='credit').aggregate(s=Sum('total'))['s']
        raw_paid = Payment.objects.filter(client=self.cafe).aggregate(s=Sum('amount'))['s']
        self.assertEqual(st['entries'][-1]['debt_after'], raw_credit - raw_paid)
        self.assertEqual(st['debt'], raw_credit - raw_paid)
        self.assertEqual(st['debt'], self.debt(self.cafe))
        self.assertEqual(st['entries'][-1]['consign_after'], services.consign_holdings(self.cafe))
        self.assertEqual(st['consign_holdings'], services.consign_holdings(self.cafe))

    def test_entry_content(self):
        s1 = self.build_history()
        entries = self.statement(self.cafe)['entries']
        first = entries[0]
        self.assertEqual((first['type'], first['id'], first['mode'], first['total'], first['debt_delta'],
                          first['debt_after']), ('sale', s1['id'], 'credit', 9300, 9300, 9300))
        pay_at_sale = entries[next(i for i, e in enumerate(entries) if e['type'] == 'payment')]
        self.assertEqual((pay_at_sale['amount'], pay_at_sale['debt_delta']), (1000, -1000))
        cash = next(e for e in entries if e['type'] == 'sale' and e['mode'] == 'cash')
        self.assertEqual((cash['debt_delta'], cash['total']), (0, 1800))
        crate_out = next(e for e in entries if e['type'] == 'consign' and e['qty_out'] == 2)
        self.assertEqual((crate_out['consign_type'], crate_out['consign_after']['crate']), ('crate', 2))
        self.assertTrue(any(e['type'] == 'sale' and e['reverses'] for e in entries))
        self.assertTrue(any(e['type'] == 'payment' and e['reverses'] for e in entries))

    def test_statement_only_contains_that_clients_movements(self):
        self.build_history()
        self.owe(self.retailer)
        st = self.statement(self.retailer)
        self.assertEqual([e['type'] for e in st['entries']], ['sale'])
        self.assertEqual(st['debt'], 2000)  # 2 × 1000 (tarif détail)

    def test_statement_for_a_client_without_movements(self):
        st = self.statement(self.wholesaler)
        self.assertEqual((st['entries'], st['debt']), ([], 0))

    def test_statement_includes_credit_balance_as_negative(self):
        self.pay(self.cafe, 700)
        st = self.statement(self.cafe)
        self.assertEqual((st['debt'], st['entries'][-1]['debt_after']), (-700, -700))

    def test_roles(self):
        self.build_history()
        for user in (self.manager, self.cashier):
            self.statement(self.cafe, user)
        self.assertEqual(self.api(self.delivery).get(f'/api/clients/{self.cafe.pk}/statement/').status_code, 403)
        self.assertEqual(self.api(self.manager).get('/api/clients/99999/statement/').status_code, 404)

    def test_statement_works_for_a_deactivated_client(self):
        self.owe(self.cafe)
        self.api(self.manager).post(f'/api/clients/{self.cafe.pk}/deactivate/')
        self.assertEqual(self.statement(self.cafe)['debt'], 1800)
