from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from operations.models import Sale, SaleLine

from .models import Category, Client, Product, ProductPrice, ProductUnit

ROLES = [Role.MANAGER, Role.CASHIER, Role.DELIVERY]


def product_payload(**over):
    data = {
        'name': 'Eau 1.5L', 'brand': 'Safia', 'category': 'water', 'consignable': True, 'min_threshold': 20,
        'units': [
            {'name': 'unit', 'factor': 1, 'prices': [{'client_type': 'retail', 'price': 800},
                                                      {'client_type': 'wholesale', 'price': 650}]},
            {'name': 'pack', 'factor': 6, 'consign_type': 'crate', 'consign_qty': 1,
             'prices': [{'client_type': 'retail', 'price': 4500}]},
        ],
    }
    data.update(over)
    return data


class ApiTestCase(TestCase):
    def setUp(self):
        self.users = {r: User.objects.create_user(r, '1234', r) for r in ROLES}

    def api(self, role):
        c = APIClient()
        c.force_authenticate(self.users[role])
        return c

    def make_product(self):
        r = self.api(Role.MANAGER).post('/api/products/', product_payload(), format='json')
        assert r.status_code == 201, r.data
        return r.data

    def make_client(self, **kw):
        return Client.objects.create(**{'name': 'Café Central', 'phone': '20111222', **kw})


class AuthTests(ApiTestCase):
    def test_all_endpoints_require_token(self):
        anon = APIClient()
        for url in ('/api/products/', '/api/products/1/', '/api/clients/', '/api/clients/1/'):
            self.assertEqual(anon.get(url).status_code, 401, url)
        self.assertEqual(anon.post('/api/products/', {}, format='json').status_code, 401)
        self.assertEqual(anon.post('/api/clients/1/deactivate/').status_code, 401)

    def test_real_login_token_works(self):
        a = APIClient()
        token = a.post('/api/auth/login/', {'name': 'manager', 'pin': '1234'}, format='json').data['token']
        a.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(a.get('/api/products/').status_code, 200)


class ProductPermissionTests(ApiTestCase):
    def test_read_allowed_for_all_roles(self):
        p = self.make_product()
        for role in ROLES:
            with self.subTest(role=role):
                self.assertEqual(self.api(role).get('/api/products/').status_code, 200)
                self.assertEqual(self.api(role).get(f'/api/products/{p["id"]}/').status_code, 200)

    def test_write_only_for_manager(self):
        p = self.make_product()
        for role in (Role.CASHIER, Role.DELIVERY):
            a = self.api(role)
            with self.subTest(role=role):
                self.assertEqual(a.post('/api/products/', product_payload(), format='json').status_code, 403)
                self.assertEqual(a.patch(f'/api/products/{p["id"]}/', {'name': 'X'}, format='json').status_code, 403)
                self.assertEqual(a.put(f'/api/products/{p["id"]}/', product_payload(), format='json').status_code, 403)
                self.assertEqual(a.post(f'/api/products/{p["id"]}/deactivate/').status_code, 403)
        self.assertEqual(Product.objects.get(pk=p['id']).name, 'Eau 1.5L')
        self.assertTrue(Product.objects.get(pk=p['id']).is_active)

    def test_manager_can_create_update_deactivate(self):
        a = self.api(Role.MANAGER)
        p = self.make_product()
        self.assertEqual(a.patch(f'/api/products/{p["id"]}/', {'name': 'Eau 2L'}, format='json').status_code, 200)
        r = a.post(f'/api/products/{p["id"]}/deactivate/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['is_active'])

    def test_no_hard_delete_for_anyone(self):
        p = self.make_product()
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn(self.api(role).delete(f'/api/products/{p["id"]}/').status_code, (403, 405))
        self.assertTrue(Product.objects.filter(pk=p['id']).exists())


class ProductDataTests(ApiTestCase):
    def test_nested_units_and_prices_created_and_returned(self):
        p = self.make_product()
        self.assertEqual(len(p['units']), 2)
        pack = next(u for u in p['units'] if u['name'] == 'pack')
        self.assertEqual((pack['factor'], pack['consign_type'], pack['consign_qty']), (6, 'crate', 1))
        self.assertEqual(pack['prices'], [{'client_type': 'retail', 'price': 4500}])
        self.assertEqual(ProductPrice.objects.count(), 3)

    def test_update_replaces_prices_and_units(self):
        a = self.api(Role.MANAGER)
        p = self.make_product()
        body = {'units': [{'name': 'unit', 'factor': 1, 'prices': [{'client_type': 'retail', 'price': 900}]}]}
        r = a.patch(f'/api/products/{p["id"]}/', body, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([u['name'] for u in r.data['units']], ['unit'])
        self.assertEqual(r.data['units'][0]['prices'], [{'client_type': 'retail', 'price': 900}])

    def test_update_without_units_keeps_units(self):
        p = self.make_product()
        r = self.api(Role.MANAGER).patch(f'/api/products/{p["id"]}/', {'brand': 'Melliti'}, format='json')
        self.assertEqual(len(r.data['units']), 2)

    def test_cannot_remove_unit_used_by_a_sale(self):
        a = self.api(Role.MANAGER)
        p = self.make_product()
        unit = ProductUnit.objects.get(product_id=p['id'], name='pack')
        sale = Sale.objects.create(client=self.make_client(), mode='cash', total=4500, user=self.users[Role.MANAGER])
        SaleLine.objects.create(sale=sale, product_id=p['id'], unit=unit, quantity=1, unit_price=4500)
        body = {'units': [{'name': 'unit', 'factor': 1}]}
        self.assertEqual(a.patch(f'/api/products/{p["id"]}/', body, format='json').status_code, 400)
        self.assertTrue(ProductUnit.objects.filter(pk=unit.pk).exists())

    def test_price_validation(self):
        a = self.api(Role.MANAGER)
        for bad in (-1, 1.5, 'abc', 10 ** 13, None):
            units = [{'name': 'unit', 'factor': 1, 'prices': [{'client_type': 'retail', 'price': bad}]}]
            with self.subTest(price=bad):
                r = a.post('/api/products/', product_payload(units=units), format='json')
                self.assertEqual(r.status_code, 400)
        self.assertEqual(Product.objects.count(), 0)

    def test_price_zero_is_allowed(self):
        units = [{'name': 'unit', 'factor': 1, 'prices': [{'client_type': 'retail', 'price': 0}]}]
        r = self.api(Role.MANAGER).post('/api/products/', product_payload(units=units), format='json')
        self.assertEqual(r.status_code, 201)

    def test_unknown_client_type_rejected(self):
        units = [{'name': 'unit', 'factor': 1, 'prices': [{'client_type': 'vip', 'price': 1}]}]
        r = self.api(Role.MANAGER).post('/api/products/', product_payload(units=units), format='json')
        self.assertEqual(r.status_code, 400)

    def test_unit_factor_must_be_at_least_1(self):
        for f in (0, -2):
            r = self.api(Role.MANAGER).post('/api/products/', product_payload(units=[{'name': 'u', 'factor': f}]),
                                            format='json')
            self.assertEqual(r.status_code, 400)

    def test_duplicate_unit_name_rejected(self):
        units = [{'name': 'pack', 'factor': 6}, {'name': 'pack', 'factor': 12}]
        r = self.api(Role.MANAGER).post('/api/products/', product_payload(units=units), format='json')
        self.assertEqual(r.status_code, 400)

    def test_duplicate_price_for_same_client_type_rejected(self):
        prices = [{'client_type': 'cafe', 'price': 1}, {'client_type': 'cafe', 'price': 2}]
        r = self.api(Role.MANAGER).post('/api/products/', product_payload(units=[{'name': 'u', 'factor': 1, 'prices': prices}]),
                                        format='json')
        self.assertEqual(r.status_code, 400)

    def test_consign_qty_needs_type_and_consignable_product(self):
        a = self.api(Role.MANAGER)
        no_type = [{'name': 'pack', 'factor': 6, 'consign_qty': 1}]
        self.assertEqual(a.post('/api/products/', product_payload(units=no_type), format='json').status_code, 400)
        with_type = [{'name': 'pack', 'factor': 6, 'consign_type': 'crate', 'consign_qty': 1}]
        r = a.post('/api/products/', product_payload(units=with_type, consignable=False), format='json')
        self.assertEqual(r.status_code, 400)

    def test_db_unique_constraints(self):
        p = Product.objects.create(name='Coca', category=Category.SODA)
        u = ProductUnit.objects.create(product=p, name='pack', factor=6)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductUnit.objects.create(product=p, name='pack', factor=12)
        ProductPrice.objects.create(unit=u, client_type='retail', price=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductPrice.objects.create(unit=u, client_type='retail', price=2)

    def test_is_active_filter_and_not_writable(self):
        a = self.api(Role.MANAGER)
        p = self.make_product()
        a.patch(f'/api/products/{p["id"]}/', {'is_active': False}, format='json')
        self.assertTrue(Product.objects.get(pk=p['id']).is_active)
        a.post(f'/api/products/{p["id"]}/deactivate/')
        self.assertEqual(len(a.get('/api/products/?is_active=true').data), 0)
        self.assertEqual(len(a.get('/api/products/?is_active=false').data), 1)


class ClientPermissionTests(ApiTestCase):
    def test_delivery_has_no_access_to_clients(self):
        c = self.make_client()
        a = self.api(Role.DELIVERY)
        self.assertEqual(a.get('/api/clients/').status_code, 403)
        self.assertEqual(a.get(f'/api/clients/{c.pk}/').status_code, 403)
        self.assertEqual(a.post('/api/clients/', {'name': 'X', 'type': 'retail'}, format='json').status_code, 403)
        self.assertEqual(a.patch(f'/api/clients/{c.pk}/', {'name': 'X'}, format='json').status_code, 403)
        self.assertEqual(a.post(f'/api/clients/{c.pk}/deactivate/').status_code, 403)

    def test_manager_full_access_including_credit_limit(self):
        a = self.api(Role.MANAGER)
        r = a.post('/api/clients/', {'name': 'Hôtel', 'type': 'wholesale', 'credit_limit': 500000}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['credit_limit'], 500000)
        r = a.patch(f'/api/clients/{r.data["id"]}/', {'credit_limit': 800000}, format='json')
        self.assertEqual(r.data['credit_limit'], 800000)
        self.assertEqual(a.get('/api/clients/').status_code, 200)
        self.assertFalse(a.post(f'/api/clients/{r.data["id"]}/deactivate/').data['is_active'])

    def test_cashier_can_read_create_edit(self):
        a = self.api(Role.CASHIER)
        c = self.make_client()
        self.assertEqual(a.get('/api/clients/').status_code, 200)
        self.assertEqual(a.get(f'/api/clients/{c.pk}/').status_code, 200)
        r = a.post('/api/clients/', {'name': 'Ali', 'type': 'cafe'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['credit_limit'], 0)
        r = a.patch(f'/api/clients/{c.pk}/', {'phone': '99888777'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Client.objects.get(pk=c.pk).phone, '99888777')

    def test_cashier_cannot_set_or_change_credit_limit(self):
        a = self.api(Role.CASHIER)
        c = self.make_client(credit_limit=100000)
        self.assertEqual(a.post('/api/clients/', {'name': 'N', 'type': 'cafe', 'credit_limit': 5000}, format='json').status_code, 403)
        self.assertEqual(a.patch(f'/api/clients/{c.pk}/', {'credit_limit': 999999}, format='json').status_code, 403)
        self.assertEqual(Client.objects.get(pk=c.pk).credit_limit, 100000)
        # renvoyer la même valeur (formulaire complet) reste permis
        r = a.put(f'/api/clients/{c.pk}/', {'name': 'Nouveau', 'type': 'cafe', 'credit_limit': 100000}, format='json')
        self.assertEqual(r.status_code, 200)

    def test_cashier_cannot_deactivate_or_delete(self):
        c = self.make_client()
        a = self.api(Role.CASHIER)
        self.assertEqual(a.post(f'/api/clients/{c.pk}/deactivate/').status_code, 403)
        self.assertIn(a.delete(f'/api/clients/{c.pk}/').status_code, (403, 405))
        self.assertEqual(self.api(Role.MANAGER).delete(f'/api/clients/{c.pk}/').status_code, 405)
        self.assertTrue(Client.objects.get(pk=c.pk).is_active)

    def test_cashier_cannot_reactivate_via_patch(self):
        c = self.make_client(is_active=False)
        self.api(Role.CASHIER).patch(f'/api/clients/{c.pk}/', {'is_active': True}, format='json')
        self.assertFalse(Client.objects.get(pk=c.pk).is_active)


class ClientDataTests(ApiTestCase):
    def test_credit_limit_validation(self):
        a = self.api(Role.MANAGER)
        for bad in (-1, 2.5, 'x', 10 ** 13):
            with self.subTest(limit=bad):
                r = a.post('/api/clients/', {'name': 'N', 'type': 'retail', 'credit_limit': bad}, format='json')
                self.assertEqual(r.status_code, 400)

    def test_invalid_type_and_missing_name_rejected(self):
        a = self.api(Role.MANAGER)
        self.assertEqual(a.post('/api/clients/', {'name': 'N', 'type': 'vip'}, format='json').status_code, 400)
        self.assertEqual(a.post('/api/clients/', {'type': 'retail'}, format='json').status_code, 400)

    def test_search_by_name_and_phone(self):
        self.make_client(name='Café Central', phone='20111222')
        self.make_client(name='Hôtel Plaza', phone='71333444')
        self.make_client(name='Épicerie Ali', phone='98111000')
        for role in (Role.MANAGER, Role.CASHIER):
            a = self.api(role)
            names = lambda q: sorted(c['name'] for c in a.get('/api/clients/', {'search': q}).data)
            with self.subTest(role=role):
                self.assertEqual(names('plaza'), ['Hôtel Plaza'])
                self.assertEqual(names('111'), ['Café Central', 'Épicerie Ali'])
                self.assertEqual(names('zzz'), [])
                self.assertEqual(len(names('')), 3)

    def test_is_active_filter(self):
        self.make_client(name='A')
        self.make_client(name='B', is_active=False)
        a = self.api(Role.MANAGER)
        self.assertEqual([c['name'] for c in a.get('/api/clients/?is_active=true').data], ['A'])


class CreateManagerCommandTests(TestCase):
    def test_creates_manager_who_can_log_in(self):
        call_command('createmanager', 'Papa', '--pin', '2468')
        u = User.objects.get(name='Papa')
        self.assertEqual(u.role, Role.MANAGER)
        self.assertTrue(u.check_password('2468'))

    def test_rejects_bad_pin_and_duplicate(self):
        with self.assertRaises(CommandError):
            call_command('createmanager', 'Papa', '--pin', '12')
        self.assertFalse(User.objects.filter(name='Papa').exists())
        call_command('createmanager', 'Papa', '--pin', '2468')
        with self.assertRaises(CommandError):
            call_command('createmanager', 'Papa', '--pin', '2468')
