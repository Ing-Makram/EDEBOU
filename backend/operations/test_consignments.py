import uuid
from datetime import datetime, timedelta

from django.db.models import Sum
from django.utils import timezone
from rest_framework.test import APIClient

from catalog.models import Client

from . import consign_services, services
from .models import ConsignMovement
from .testbase import SaleTestCase


def at(day):
    """Jour N du scénario (jour 1 = 1er janvier 2026, 9 h)."""
    return timezone.make_aware(datetime(2026, 1, 1, 9, 0)) + timedelta(days=day - 1)


class ConsignTestCase(SaleTestCase):
    def move(self, client, direction, quantity, consign_type='crate', user=None, expect=201, day=None, **extra):
        body = {'request_id': str(uuid.uuid4()), 'client_id': client.pk, 'consign_type': consign_type,
                'direction': direction, 'quantity': quantity, **extra}
        r = self.api(user or self.cashier).post('/api/consignments/', body, format='json')
        self.assertEqual(r.status_code, expect, r.data)
        if day is not None and expect == 201:
            ConsignMovement.objects.filter(pk=r.data['id']).update(created_at=at(day))
        return r

    def held(self, client):
        return services.consign_holdings(client)


class ManualMovementTests(ConsignTestCase):
    def test_manual_out_increases_holdings(self):
        r = self.move(self.cafe, 'out', 5)
        self.assertEqual(self.held(self.cafe), {'crate': 5, 'glass_bottle': 0})
        self.assertEqual((r.data['direction'], r.data['quantity'], r.data['qty_out'], r.data['qty_in']),
                         ('out', 5, 5, 0))
        self.assertIsNone(r.data['sale'])
        row = ConsignMovement.objects.get()
        self.assertEqual((row.client_id, row.consign_type, row.user_id), (self.cafe.pk, 'crate', self.cashier.pk))

    def test_manual_out_for_glass_bottles_is_a_separate_balance(self):
        self.move(self.cafe, 'out', 3, 'glass_bottle')
        self.move(self.cafe, 'out', 2, 'crate')
        self.assertEqual(self.held(self.cafe), {'crate': 2, 'glass_bottle': 3})

    def test_manual_return_reduces_holdings(self):
        self.move(self.cafe, 'out', 5)
        r = self.move(self.cafe, 'in', 2)
        self.assertEqual((r.data['direction'], r.data['qty_in'], r.data['qty_out']), ('in', 2, 0))
        self.assertEqual(self.held(self.cafe)['crate'], 3)

    def test_return_of_everything_is_allowed(self):
        self.move(self.cafe, 'out', 5)
        self.move(self.cafe, 'in', 5)
        self.assertEqual(self.held(self.cafe)['crate'], 0)

    def test_return_above_holdings_is_rejected_and_leaves_nothing(self):
        self.move(self.cafe, 'out', 5)
        rows = ConsignMovement.objects.count()
        r = self.move(self.cafe, 'in', 6, expect=400)
        self.assertEqual((r.data['code'], r.data['held'], r.data['returned']), ('consign_return_exceeds_holdings', 5, 6))
        self.assertEqual(ConsignMovement.objects.count(), rows)
        self.assertEqual(self.held(self.cafe)['crate'], 5)

    def test_return_when_nothing_held_or_other_type_is_rejected(self):
        self.move(self.cafe, 'in', 1, expect=400)
        self.move(self.cafe, 'out', 5, 'crate')
        self.move(self.cafe, 'in', 1, 'glass_bottle', expect=400)

    def test_return_counts_what_a_sale_gave_out(self):
        self.sell([('Eau', 'pack', 3)], self.cafe)  # 3 caisses via la vente
        self.move(self.cafe, 'in', 3)
        self.move(self.cafe, 'in', 1, expect=400)
        self.assertEqual(self.held(self.cafe)['crate'], 0)

    def test_holdings_are_per_client(self):
        self.move(self.cafe, 'out', 5)
        self.move(self.retailer, 'in', 1, expect=400)
        self.assertEqual(self.held(self.retailer)['crate'], 0)

    def test_manual_movement_does_not_touch_stock_debt_or_payments(self):
        from .models import Payment, Sale, StockMovement
        counts = (StockMovement.objects.count(), Sale.objects.count(), Payment.objects.count())
        self.move(self.cafe, 'out', 5)
        self.move(self.cafe, 'in', 2)
        self.assertEqual((StockMovement.objects.count(), Sale.objects.count(), Payment.objects.count()), counts)
        self.assertEqual(services.client_debt(self.cafe), 0)

    def test_validation(self):
        rows = ConsignMovement.objects.count()
        good = {'request_id': str(uuid.uuid4()), 'client_id': self.cafe.pk, 'consign_type': 'crate',
                'direction': 'out', 'quantity': 1}
        cases = {'qty 0': {'quantity': 0}, 'qty negative': {'quantity': -1}, 'qty float': {'quantity': 1.5},
                 'qty text': {'quantity': 'x'}, 'qty huge': {'quantity': 10 ** 7}, 'bad direction': {'direction': 'sideways'},
                 'no direction': {'direction': None}, 'bad type': {'consign_type': 'barrel'},
                 'no client': {'client_id': None}, 'unknown client': {'client_id': 99999},
                 'no request id': {'request_id': None}, 'bad request id': {'request_id': 'nope'}}
        for label, patch in cases.items():
            with self.subTest(label):
                r = self.api(self.cashier).post('/api/consignments/', {**good, **patch}, format='json')
                self.assertEqual(r.status_code, 400)
        Client.objects.filter(pk=self.cafe.pk).update(is_active=False)
        self.assertEqual(self.api(self.cashier).post('/api/consignments/', good, format='json').status_code, 400)
        self.assertEqual(ConsignMovement.objects.count(), rows)

    def test_same_request_id_twice_creates_one_movement(self):
        body = {'request_id': str(uuid.uuid4()), 'client_id': self.cafe.pk, 'consign_type': 'crate',
                'direction': 'out', 'quantity': 4}
        a = self.api(self.cashier)
        first, second = a.post('/api/consignments/', body, format='json'), a.post('/api/consignments/', body, format='json')
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(ConsignMovement.objects.count(), 1)
        self.assertEqual(self.held(self.cafe)['crate'], 4)

    def test_replayed_return_is_not_applied_twice(self):
        self.move(self.cafe, 'out', 4)
        body = {'request_id': str(uuid.uuid4()), 'client_id': self.cafe.pk, 'consign_type': 'crate',
                'direction': 'in', 'quantity': 3}
        a = self.api(self.cashier)
        a.post('/api/consignments/', body, format='json')
        again = a.post('/api/consignments/', body, format='json')  # aurait dépassé (3 > 1) sans l'idempotence
        self.assertEqual(again.status_code, 200)
        self.assertEqual(self.held(self.cafe)['crate'], 1)

    def test_replay_returns_original_even_if_payload_differs(self):
        body = {'request_id': str(uuid.uuid4()), 'client_id': self.cafe.pk, 'consign_type': 'crate',
                'direction': 'out', 'quantity': 4}
        a = self.api(self.cashier)
        a.post('/api/consignments/', body, format='json')
        again = a.post('/api/consignments/', {**body, 'quantity': 99}, format='json')
        self.assertEqual(again.data['quantity'], 4)
        self.assertEqual(ConsignMovement.objects.count(), 1)

    def test_request_id_unique_in_database(self):
        from django.db import IntegrityError, transaction
        rid = uuid.uuid4()
        ConsignMovement.objects.create(client=self.cafe, consign_type='crate', qty_out=1, user=self.manager, request_id=rid)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConsignMovement.objects.create(client=self.cafe, consign_type='crate', qty_out=1, user=self.manager,
                                           request_id=rid)

    def test_movements_are_append_only_through_the_api(self):
        m = self.move(self.cafe, 'out', 4).data
        for method in ('put', 'patch', 'delete'):
            r = getattr(self.api(self.manager), method)(f'/api/consignments/{m["id"]}/', {}, format='json')
            self.assertIn(r.status_code, (404, 405))
        self.assertEqual(ConsignMovement.objects.get(pk=m['id']).qty_out, 4)

    def test_a_wrong_manual_out_is_corrected_with_a_return_never_by_editing(self):
        self.move(self.cafe, 'out', 5)
        self.move(self.cafe, 'in', 5)
        self.assertEqual(ConsignMovement.objects.count(), 2)
        self.assertEqual(self.held(self.cafe)['crate'], 0)


class ConsignPermissionTests(ConsignTestCase):
    def test_manager_and_cashier_can_create_list_and_summarise(self):
        for user in (self.manager, self.cashier):
            self.move(self.cafe, 'out', 1, user=user)
            a = self.api(user)
            self.assertEqual(a.get('/api/consignments/').status_code, 200)
            self.assertEqual(a.get('/api/consignments/summary/').status_code, 200)

    def test_delivery_has_no_access(self):
        rows = ConsignMovement.objects.count()
        self.move(self.cafe, 'out', 1, user=self.delivery, expect=403)
        a = self.api(self.delivery)
        self.assertEqual(a.get('/api/consignments/').status_code, 403)
        self.assertEqual(a.get('/api/consignments/summary/').status_code, 403)
        self.assertEqual(ConsignMovement.objects.count(), rows)

    def test_anonymous_is_rejected(self):
        a = APIClient()
        self.assertEqual(a.get('/api/consignments/').status_code, 401)
        self.assertEqual(a.get('/api/consignments/summary/').status_code, 401)
        self.assertEqual(a.post('/api/consignments/', {}, format='json').status_code, 401)


class ConsignListTests(ConsignTestCase):
    def test_list_includes_sale_and_manual_movements_newest_first(self):
        self.sell([('Eau', 'pack', 2)], self.cafe)
        manual = self.move(self.cafe, 'in', 1).data
        data = self.api(self.manager).get('/api/consignments/').data
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['id'], manual['id'])
        self.assertIsNotNone(data[1]['sale'])
        self.assertIsNone(data[0]['sale'])

    def test_filters_by_client_type_and_date(self):
        ids = [self.move(self.cafe, 'out', 1, 'crate', day=5).data['id'],
               self.move(self.retailer, 'out', 2, 'glass_bottle', day=10).data['id'],
               self.move(self.cafe, 'out', 3, 'glass_bottle', day=15).data['id']]
        a = self.api(self.manager)
        got = lambda q: sorted(m['id'] for m in a.get('/api/consignments/' + q).data)
        self.assertEqual(got(f'?client={self.cafe.pk}'), sorted([ids[0], ids[2]]))
        self.assertEqual(got('?type=glass_bottle'), sorted(ids[1:]))
        self.assertEqual(got('?type=crate'), [ids[0]])
        self.assertEqual(got(f'?client={self.cafe.pk}&type=glass_bottle'), [ids[2]])
        self.assertEqual(got('?date_from=2026-01-10'), sorted(ids[1:]))
        self.assertEqual(got('?date_to=2026-01-10'), sorted(ids[:2]))
        self.assertEqual(got('?date_from=2026-01-10&date_to=2026-01-10'), [ids[1]])
        self.assertEqual(got('?date_from=2030-01-01'), [])
        for bad in ('?type=barrel', '?client=abc', '?date_from=zz', '?date_to=zz'):
            self.assertEqual(a.get('/api/consignments/' + bad).status_code, 400, bad)


class ConsignSummaryTests(ConsignTestCase):
    def summary(self, now=None):
        return consign_services.consign_summary(now)

    def test_totals_by_type_across_all_clients(self):
        self.move(self.cafe, 'out', 5)
        self.move(self.retailer, 'out', 4)
        self.move(self.wholesaler, 'out', 7, 'glass_bottle')
        self.move(self.cafe, 'in', 2)
        r = self.api(self.manager).get('/api/consignments/summary/').data
        self.assertEqual(r['totals'], {'crate': 7, 'glass_bottle': 7})
        self.assertEqual(r['overdue_days'], 30)
        self.assertEqual(r['overdue'], [])

    def test_totals_include_sale_movements_and_cancelled_sales(self):
        sale = self.sell([('Eau', 'pack', 3), ('Verre', 'unit', 2)], self.cafe).data
        self.assertEqual(self.summary()['totals'], {'crate': 3, 'glass_bottle': 2})
        self.api(self.manager).post(f'/api/sales/{sale["id"]}/cancel/')
        self.assertEqual(self.summary()['totals'], {'crate': 0, 'glass_bottle': 0})

    def test_totals_equal_raw_sums_and_per_client_holdings(self):
        self.sell([('Eau', 'pack', 3)], self.cafe)
        self.move(self.cafe, 'in', 1)
        self.move(self.retailer, 'out', 6)
        self.move(self.wholesaler, 'out', 2, 'glass_bottle')
        raw = ConsignMovement.objects.aggregate(o=Sum('qty_out'), i=Sum('qty_in'))
        totals = self.summary()['totals']
        self.assertEqual(sum(totals.values()), raw['o'] - raw['i'])
        for t in totals:
            self.assertEqual(totals[t], sum(self.held(c)[t] for c in Client.objects.all()))

    def test_fifo_crates_taken_day_1_part_returned_day_20_rest_still_held_on_day_35(self):
        self.move(self.cafe, 'out', 10, day=1)
        self.move(self.cafe, 'in', 4, day=20)
        s = self.summary(now=at(35))
        self.assertEqual(s['totals']['crate'], 6)
        self.assertEqual(len(s['overdue']), 1)
        row = s['overdue'][0]
        self.assertEqual((row['client'], row['client_name'], row['consign_type']), (self.cafe.pk, 'Café', 'crate'))
        self.assertEqual((row['held'], row['overdue_quantity']), (6, 6))  # les 6 restantes datent du jour 1
        self.assertEqual(row['oldest_since'], at(1))
        self.assertEqual(row['days'], 34)

    def test_fifo_return_settles_the_oldest_outstanding_out_first(self):
        # 5 caisses jour 1, 5 caisses jour 25, 5 rendues jour 30 : FIFO solde le lot du jour 1.
        # Il reste 5 caisses du jour 25 (10 jours à J35) : pas en retard.
        self.move(self.cafe, 'out', 5, day=1)
        self.move(self.cafe, 'out', 5, day=25)
        self.move(self.cafe, 'in', 5, day=30)
        s = self.summary(now=at(35))
        self.assertEqual(s['totals']['crate'], 5)
        self.assertEqual(s['overdue'], [])

    def test_fifo_partial_return_splits_old_and_recent_lots(self):
        # 5 caisses jour 1, 5 caisses jour 25, 3 rendues jour 30 : il reste 2 du jour 1 (en retard)
        # et 5 du jour 25 (non). Puis 4 rendues jour 31 : solde les 2 du jour 1 et 2 du jour 25.
        self.move(self.cafe, 'out', 5, day=1)
        self.move(self.cafe, 'out', 5, day=25)
        self.move(self.cafe, 'in', 3, day=30)
        s = self.summary(now=at(35))
        row = s['overdue'][0]
        self.assertEqual((row['held'], row['overdue_quantity'], row['oldest_since']), (7, 2, at(1)))
        self.move(self.cafe, 'in', 4, day=31)
        s = self.summary(now=at(35))
        self.assertEqual((s['totals']['crate'], s['overdue']), (3, []))

    def test_thirty_days_exactly_is_not_overdue_but_more_is(self):
        self.move(self.cafe, 'out', 5, day=1)
        self.assertEqual(self.summary(now=at(1) + timedelta(days=30))['overdue'], [])
        late = self.summary(now=at(1) + timedelta(days=30, minutes=1))['overdue']
        self.assertEqual([(r['client'], r['overdue_quantity']) for r in late], [(self.cafe.pk, 5)])

    def test_fully_returned_client_is_not_listed(self):
        self.move(self.cafe, 'out', 5, day=1)
        self.move(self.cafe, 'in', 5, day=40)
        self.assertEqual(self.summary(now=at(60))['overdue'], [])

    def test_types_are_matched_separately(self):
        self.move(self.cafe, 'out', 5, 'crate', day=1)
        self.move(self.cafe, 'out', 3, 'glass_bottle', day=2)
        self.move(self.cafe, 'in', 3, 'glass_bottle', day=10)  # ne doit pas solder les caisses
        s = self.summary(now=at(40))
        self.assertEqual([(r['consign_type'], r['overdue_quantity']) for r in s['overdue']], [('crate', 5)])
        self.assertEqual(s['totals'], {'crate': 5, 'glass_bottle': 0})

    def test_clients_are_matched_separately_and_sorted_oldest_first(self):
        self.move(self.cafe, 'out', 5, day=5)
        self.move(self.retailer, 'out', 2, day=1)
        self.move(self.wholesaler, 'out', 9, day=34)  # récent
        self.move(self.retailer, 'in', 1, day=3)  # le retour du détaillant ne touche pas le café
        s = self.summary(now=at(40))
        self.assertEqual([(r['client_name'], r['overdue_quantity']) for r in s['overdue']],
                         [('Détail', 1), ('Café', 5)])

    def test_sale_movements_count_in_the_fifo_queue(self):
        sale = self.sell([('Eau', 'pack', 4)], self.cafe).data
        ConsignMovement.objects.filter(sale_id=sale['id']).update(created_at=at(1))
        self.move(self.cafe, 'in', 1, day=10)
        s = self.summary(now=at(40))
        self.assertEqual((s['overdue'][0]['held'], s['overdue'][0]['overdue_quantity']), (3, 3))

    def test_summary_endpoint_uses_the_real_clock(self):
        m = self.move(self.cafe, 'out', 5).data
        now = timezone.now()
        ConsignMovement.objects.filter(pk=m['id']).update(created_at=now - timedelta(days=31))
        self.move(self.retailer, 'out', 2)  # récent
        r = self.api(self.cashier).get('/api/consignments/summary/').data
        self.assertEqual([(x['client'], x['overdue_quantity'], x['days']) for x in r['overdue']],
                         [(self.cafe.pk, 5, 31)])
        self.assertEqual(r['totals']['crate'], 7)


class ConsignConsistencyTests(ConsignTestCase):
    def test_client_endpoint_statement_and_summary_agree(self):
        self.sell([('Eau', 'pack', 3), ('Verre', 'unit', 4)], self.cafe)
        self.move(self.cafe, 'in', 1)
        self.move(self.cafe, 'out', 2, 'glass_bottle')
        self.move(self.cafe, 'in', 2, 'glass_bottle')
        expected = {'crate': 2, 'glass_bottle': 4}
        a = self.api(self.manager)
        self.assertEqual(a.get(f'/api/clients/{self.cafe.pk}/').data['consign_holdings'], expected)
        st = a.get(f'/api/clients/{self.cafe.pk}/statement/').data
        self.assertEqual((st['consign_holdings'], st['entries'][-1]['consign_after']), (expected, expected))
        self.assertEqual(a.get('/api/consignments/summary/').data['totals'], expected)
        raw = {t: sum(m.qty_out - m.qty_in for m in ConsignMovement.objects.filter(consign_type=t))
               for t in expected}
        self.assertEqual(raw, expected)

    def test_manual_movements_appear_in_the_statement(self):
        self.move(self.cafe, 'out', 4)
        st = self.api(self.cashier).get(f'/api/clients/{self.cafe.pk}/statement/').data
        self.assertEqual([(e['type'], e['qty_out'], e['sale'], e['debt_delta']) for e in st['entries']],
                         [('consign', 4, None, 0)])
