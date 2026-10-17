from django.core.cache import cache
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Role, User


class UserTestCase(TestCase):
    def setUp(self):
        cache.clear()  # les limiteurs de débit utilisent le cache
        self.manager = User.objects.create_user('Papa', '2468', Role.MANAGER)
        self.cashier = User.objects.create_user('Sami', '1111', Role.CASHIER)
        self.delivery = User.objects.create_user('Karim', '2222', Role.DELIVERY)

    def login(self, name, pin):
        """Vraie connexion : renvoie (client authentifié par jeton, jeton)."""
        c = APIClient()
        r = c.post('/api/auth/login/', {'name': name, 'pin': pin}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        c.credentials(HTTP_AUTHORIZATION='Token ' + r.data['token'])
        return c, r.data['token']

    def api(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def try_login(self, name, pin):
        return APIClient().post('/api/auth/login/', {'name': name, 'pin': pin}, format='json').status_code


class UserPermissionTests(UserTestCase):
    def test_manager_can_list_create_update_and_reset(self):
        a = self.api(self.manager)
        self.assertEqual(a.get('/api/users/').status_code, 200)
        r = a.post('/api/users/', {'name': 'Nour', 'pin': '3333', 'role': 'cashier'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(a.patch(f'/api/users/{r.data["id"]}/', {'name': 'Nour B'}, format='json').status_code, 200)
        self.assertEqual(a.post(f'/api/users/{r.data["id"]}/reset-pin/', {'pin': '4444'}, format='json').status_code, 200)

    def test_cashier_and_delivery_are_forbidden_everywhere(self):
        for user in (self.cashier, self.delivery):
            a = self.api(user)
            target = self.delivery.pk
            before = list(User.objects.order_by('id').values('id', 'name', 'role', 'is_active', 'password'))
            self.assertEqual(a.get('/api/users/').status_code, 403, user.name)
            self.assertEqual(a.post('/api/users/', {'name': 'X', 'pin': '1234', 'role': 'manager'}, format='json').status_code, 403)
            self.assertEqual(a.patch(f'/api/users/{target}/', {'role': 'manager'}, format='json').status_code, 403)
            self.assertEqual(a.patch(f'/api/users/{user.pk}/', {'role': 'manager'}, format='json').status_code, 403)
            self.assertEqual(a.post(f'/api/users/{target}/reset-pin/', {'pin': '9999'}, format='json').status_code, 403)
            self.assertEqual(list(User.objects.order_by('id').values('id', 'name', 'role', 'is_active', 'password')), before)

    def test_anonymous_is_rejected(self):
        a = APIClient()
        self.assertEqual(a.get('/api/users/').status_code, 401)
        self.assertEqual(a.post('/api/users/', {}, format='json').status_code, 401)
        self.assertEqual(a.patch(f'/api/users/{self.cashier.pk}/', {}, format='json').status_code, 401)
        self.assertEqual(a.post(f'/api/users/{self.cashier.pk}/reset-pin/', {}, format='json').status_code, 401)

    def test_no_hard_delete_and_no_put(self):
        for method in ('delete', 'put'):
            r = getattr(self.api(self.manager), method)(f'/api/users/{self.cashier.pk}/', {}, format='json')
            self.assertEqual(r.status_code, 405)
        self.assertTrue(User.objects.filter(pk=self.cashier.pk).exists())

    def test_role_change_applies_to_the_next_request(self):
        c, _ = self.login('Sami', '1111')
        self.assertEqual(c.get('/api/users/').status_code, 403)
        self.api(self.manager).patch(f'/api/users/{self.cashier.pk}/', {'role': 'manager'}, format='json')
        self.assertEqual(c.get('/api/users/').status_code, 200)
        self.assertEqual(c.get('/api/auth/me/').data['role'], 'manager')


class UserListAndCreateTests(UserTestCase):
    def test_list_is_ordered_by_name_includes_inactive_and_hides_secrets(self):
        User.objects.filter(pk=self.delivery.pk).update(is_active=False)
        r = self.api(self.manager).get('/api/users/')
        self.assertEqual([u['name'] for u in r.data], ['Karim', 'Papa', 'Sami'])
        self.assertEqual({tuple(sorted(u)) for u in r.data}, {('id', 'is_active', 'name', 'role')})
        self.assertFalse(next(u for u in r.data if u['name'] == 'Karim')['is_active'])

    def test_create_user_who_can_log_in(self):
        r = self.api(self.manager).post('/api/users/', {'name': 'Nour', 'pin': '3333', 'role': 'delivery'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(set(r.data), {'id', 'name', 'role', 'is_active'})
        self.assertEqual((r.data['name'], r.data['role'], r.data['is_active']), ('Nour', 'delivery', True))
        self.assertEqual(self.try_login('Nour', '3333'), 200)
        u = User.objects.get(name='Nour')
        self.assertNotEqual(u.password, '3333')
        self.assertTrue(u.check_password('3333'))

    def test_create_validation(self):
        a = self.api(self.manager)
        users = User.objects.count()
        ok = {'name': 'Nour', 'pin': '3333', 'role': 'cashier'}
        cases = {'pin too short': {'pin': '123'}, 'pin too long': {'pin': '1234567'}, 'pin letters': {'pin': 'abcd'},
                 'pin spaces': {'pin': '12 34'}, 'pin empty': {'pin': ''}, 'pin missing': {'pin': None},
                 'bad role': {'role': 'boss'}, 'role missing': {'role': None}, 'name empty': {'name': ''},
                 'name blank': {'name': '   '}, 'name missing': {'name': None}, 'name too long': {'name': 'x' * 101},
                 'duplicate name': {'name': 'Sami'}, 'duplicate name other case': {'name': 'sami'}}
        for label, patch in cases.items():
            with self.subTest(label):
                body = {k: v for k, v in {**ok, **patch}.items() if v is not None}
                self.assertEqual(a.post('/api/users/', body, format='json').status_code, 400)
        self.assertEqual(User.objects.count(), users)

    def test_pin_of_4_to_6_digits_is_accepted(self):
        a = self.api(self.manager)
        for i, pin in enumerate(('1234', '12345', '123456')):
            self.assertEqual(a.post('/api/users/', {'name': f'U{i}', 'pin': pin, 'role': 'cashier'}, format='json').status_code, 201)

    def test_name_is_trimmed(self):
        r = self.api(self.manager).post('/api/users/', {'name': '  Nour  ', 'pin': '3333', 'role': 'cashier'}, format='json')
        self.assertEqual(r.data['name'], 'Nour')
        self.assertEqual(self.try_login('Nour', '3333'), 200)


class UserUpdateTests(UserTestCase):
    def patch(self, user, body, actor=None):
        return self.api(actor or self.manager).patch(f'/api/users/{user.pk}/', body, format='json')

    def test_rename_and_change_role(self):
        r = self.patch(self.cashier, {'name': 'Samir', 'role': 'delivery'})
        self.assertEqual((r.status_code, r.data['name'], r.data['role']), (200, 'Samir', 'delivery'))
        self.assertEqual(self.try_login('Samir', '1111'), 200)
        self.assertEqual(self.try_login('Sami', '1111'), 401)

    def test_patch_validation(self):
        self.assertEqual(self.patch(self.cashier, {'name': 'Karim'}).status_code, 400)  # nom pris
        self.assertEqual(self.patch(self.cashier, {'name': 'KARIM'}).status_code, 400)
        self.assertEqual(self.patch(self.cashier, {'name': ''}).status_code, 400)
        self.assertEqual(self.patch(self.cashier, {'role': 'boss'}).status_code, 400)
        self.assertEqual(self.patch(self.cashier, {'is_active': 'maybe'}).status_code, 400)
        self.assertEqual(User.objects.get(pk=self.cashier.pk).name, 'Sami')

    def test_renaming_to_own_name_is_fine(self):
        self.assertEqual(self.patch(self.cashier, {'name': 'Sami'}).status_code, 200)
        self.assertEqual(self.patch(self.cashier, {'name': 'sami'}).status_code, 200)  # même personne, autre casse

    def test_unknown_user_is_404(self):
        self.assertEqual(self.api(self.manager).patch('/api/users/99999/', {'name': 'x'}, format='json').status_code, 404)
        self.assertEqual(self.api(self.manager).post('/api/users/99999/reset-pin/', {'pin': '1234'}, format='json').status_code, 404)

    def test_patch_cannot_change_the_pin(self):
        before = User.objects.get(pk=self.cashier.pk).password
        self.patch(self.cashier, {'pin': '9999', 'password': 'x'})
        self.assertEqual(User.objects.get(pk=self.cashier.pk).password, before)
        self.assertEqual(self.try_login('Sami', '1111'), 200)

    def test_deactivate_blocks_login_and_kills_the_session(self):
        c, token = self.login('Sami', '1111')
        self.assertEqual(c.get('/api/auth/me/').status_code, 200)
        r = self.patch(self.cashier, {'is_active': False})
        self.assertEqual((r.status_code, r.data['is_active']), (200, False))
        self.assertEqual(self.try_login('Sami', '1111'), 401)
        self.assertEqual(c.get('/api/auth/me/').status_code, 401)
        self.assertFalse(Token.objects.filter(key=token).exists())
        self.assertTrue(User.objects.filter(pk=self.cashier.pk).exists())  # désactivé, pas supprimé

    def test_reactivate(self):
        self.patch(self.cashier, {'is_active': False})
        self.patch(self.cashier, {'is_active': True})
        self.assertEqual(self.try_login('Sami', '1111'), 200)

    def test_deactivated_user_stays_in_the_list(self):
        self.patch(self.cashier, {'is_active': False})
        names = [u['name'] for u in self.api(self.manager).get('/api/users/').data]
        self.assertIn('Sami', names)


class ManagerSafetyRuleTests(UserTestCase):
    def patch(self, user, body, actor):
        return self.api(actor).patch(f'/api/users/{user.pk}/', body, format='json')

    def test_a_manager_cannot_deactivate_himself(self):
        r = self.patch(self.manager, {'is_active': False}, self.manager)
        self.assertEqual((r.status_code, r.data['code']), (400, 'cannot_deactivate_self'))
        self.assertTrue(User.objects.get(pk=self.manager.pk).is_active)

    def test_a_manager_cannot_deactivate_himself_even_with_other_managers(self):
        other = User.objects.create_user('Autre', '5555', Role.MANAGER)
        r = self.patch(self.manager, {'is_active': False}, self.manager)
        self.assertEqual(r.data['code'], 'cannot_deactivate_self')
        self.assertTrue(User.objects.get(pk=other.pk).is_active)

    def test_the_last_active_manager_cannot_be_demoted(self):
        r = self.patch(self.manager, {'role': 'cashier'}, self.manager)
        self.assertEqual((r.status_code, r.data['code']), (400, 'last_manager'))
        self.assertEqual(User.objects.get(pk=self.manager.pk).role, Role.MANAGER)

    def test_the_last_active_manager_cannot_be_removed_by_another_manager(self):
        """Le dernier gérant *actif* : un second gérant désactivé ne compte pas."""
        spare = User.objects.create_user('Spare', '5555', Role.MANAGER)
        self.assertEqual(self.patch(spare, {'is_active': False}, self.manager).status_code, 200)
        r = self.patch(self.manager, {'role': 'cashier'}, self.manager)
        self.assertEqual(r.data['code'], 'last_manager')

    def test_another_manager_can_be_deactivated_or_demoted_while_one_remains(self):
        spare = User.objects.create_user('Spare', '5555', Role.MANAGER)
        self.assertEqual(self.patch(spare, {'role': 'cashier'}, self.manager).status_code, 200)
        self.assertEqual(User.objects.get(pk=spare.pk).role, Role.CASHIER)
        spare2 = User.objects.create_user('Spare2', '5555', Role.MANAGER)
        self.assertEqual(self.patch(spare2, {'is_active': False}, self.manager).status_code, 200)

    def test_two_managers_cannot_remove_each_other_down_to_zero(self):
        b = User.objects.create_user('B', '5555', Role.MANAGER)
        self.assertEqual(self.patch(b, {'role': 'cashier'}, self.manager).status_code, 200)  # reste Papa
        r = self.patch(self.manager, {'role': 'delivery'}, self.manager)  # Papa serait le dernier
        self.assertEqual(r.data['code'], 'last_manager')
        self.assertEqual(User.objects.filter(role=Role.MANAGER, is_active=True).count(), 1)

    def test_a_manager_may_hand_over_by_promoting_first(self):
        b = User.objects.create_user('B', '5555', Role.CASHIER)
        self.assertEqual(self.patch(b, {'role': 'manager'}, self.manager).status_code, 200)
        self.assertEqual(self.patch(self.manager, {'role': 'cashier'}, self.manager).status_code, 200)

    def test_inactive_managers_do_not_count_as_other_managers(self):
        b = User.objects.create_user('B', '5555', Role.MANAGER)
        User.objects.filter(pk=b.pk).update(is_active=False)
        self.assertEqual(self.patch(self.manager, {'role': 'cashier'}, self.manager).data['code'], 'last_manager')

    def test_non_manager_changes_are_unconstrained_by_the_manager_rules(self):
        self.assertEqual(self.patch(self.cashier, {'is_active': False}, self.manager).status_code, 200)
        self.assertEqual(self.patch(self.delivery, {'role': 'cashier'}, self.manager).status_code, 200)


class ResetPinTests(UserTestCase):
    def reset(self, user, pin, actor=None):
        return self.api(actor or self.manager).post(f'/api/users/{user.pk}/reset-pin/', {'pin': pin}, format='json')

    def test_reset_sets_a_new_pin(self):
        self.assertEqual(self.reset(self.cashier, '9876').status_code, 200)
        self.assertEqual(self.try_login('Sami', '9876'), 200)
        self.assertEqual(self.try_login('Sami', '1111'), 401)
        self.assertNotEqual(User.objects.get(pk=self.cashier.pk).password, '9876')

    def test_reset_closes_the_users_session(self):
        c, token = self.login('Sami', '1111')
        self.reset(self.cashier, '9876')
        self.assertEqual(c.get('/api/auth/me/').status_code, 401)
        self.assertFalse(Token.objects.filter(key=token).exists())

    def test_manager_resetting_his_own_pin_keeps_his_session(self):
        c, _ = self.login('Papa', '2468')
        r = c.post(f'/api/users/{self.manager.pk}/reset-pin/', {'pin': '1357'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(c.get('/api/auth/me/').status_code, 200)
        self.assertEqual(self.try_login('Papa', '1357'), 200)
        self.assertEqual(self.try_login('Papa', '2468'), 401)

    def test_reset_does_not_touch_other_users(self):
        c, _ = self.login('Karim', '2222')
        self.reset(self.cashier, '9876')
        self.assertEqual(c.get('/api/auth/me/').status_code, 200)
        self.assertEqual(self.try_login('Karim', '2222'), 200)

    def test_reset_validation(self):
        old = User.objects.get(pk=self.cashier.pk).password
        for bad in ('123', '1234567', 'abcd', '', None, '12 3'):
            with self.subTest(pin=bad):
                r = self.api(self.manager).post(f'/api/users/{self.cashier.pk}/reset-pin/',
                                                {} if bad is None else {'pin': bad}, format='json')
                self.assertEqual(r.status_code, 400)
        self.assertEqual(User.objects.get(pk=self.cashier.pk).password, old)

    def test_reset_works_on_an_inactive_user_without_reactivating_them(self):
        User.objects.filter(pk=self.cashier.pk).update(is_active=False)
        self.assertEqual(self.reset(self.cashier, '9876').status_code, 200)
        self.assertEqual(self.try_login('Sami', '9876'), 401)


class ChangePinTests(UserTestCase):
    def change(self, client, old, new):
        return client.post('/api/auth/change-pin/', {'old_pin': old, 'new_pin': new}, format='json')

    def test_every_role_can_change_their_own_pin(self):
        for name, old in (('Papa', '2468'), ('Sami', '1111'), ('Karim', '2222')):
            with self.subTest(name):
                c, _ = self.login(name, old)
                self.assertEqual(self.change(c, old, '7777').status_code, 200)
                self.assertEqual(self.try_login(name, '7777'), 200)
                self.assertEqual(self.try_login(name, old), 401)

    def test_session_survives_a_pin_change(self):
        c, _ = self.login('Sami', '1111')
        self.change(c, '1111', '7777')
        self.assertEqual(c.get('/api/auth/me/').status_code, 200)

    def test_wrong_old_pin_is_rejected_and_nothing_changes(self):
        c, _ = self.login('Sami', '1111')
        r = self.change(c, '0000', '7777')
        self.assertEqual((r.status_code, r.data['code']), (400, 'wrong_pin'))
        self.assertEqual(self.try_login('Sami', '1111'), 200)
        self.assertEqual(self.try_login('Sami', '7777'), 401)

    def test_new_pin_must_differ_from_the_old_one(self):
        c, _ = self.login('Sami', '1111')
        r = self.change(c, '1111', '1111')
        self.assertEqual((r.status_code, r.data['code']), (400, 'same_pin'))

    def test_new_pin_validation(self):
        c, _ = self.login('Sami', '1111')
        for bad in ('123', '1234567', 'abcd', '', '12 34'):
            with self.subTest(new=bad):
                self.assertEqual(self.change(c, '1111', bad).status_code, 400)
        cache.clear()  # la limite de 5 essais/minute s'applique aussi aux requêtes invalides
        self.assertEqual(c.post('/api/auth/change-pin/', {'old_pin': '1111'}, format='json').status_code, 400)
        self.assertEqual(c.post('/api/auth/change-pin/', {'new_pin': '7777'}, format='json').status_code, 400)
        self.assertEqual(self.try_login('Sami', '1111'), 200)

    def test_new_pin_of_4_to_6_digits(self):
        c, _ = self.login('Sami', '1111')
        self.assertEqual(self.change(c, '1111', '123456').status_code, 200)
        self.assertEqual(self.change(c, '123456', '1234').status_code, 200)

    def test_requires_authentication(self):
        r = APIClient().post('/api/auth/change-pin/', {'old_pin': '1111', 'new_pin': '7777'}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_old_pin_cannot_be_brute_forced(self):
        c, _ = self.login('Sami', '1111')
        codes = [self.change(c, f'000{i}', '7777').status_code for i in range(5)]
        self.assertEqual(codes, [400] * 5)
        self.assertEqual(self.change(c, '1111', '7777').status_code, 429)
        self.assertEqual(self.try_login('Sami', '1111'), 200)  # le PIN n'a pas changé

    def test_acts_on_the_logged_in_user_only(self):
        c, _ = self.login('Sami', '1111')
        self.change(c, '1111', '7777')
        self.assertEqual(self.try_login('Karim', '2222'), 200)
        self.assertEqual(self.try_login('Papa', '2468'), 200)


class LogoutTests(UserTestCase):
    def test_logout_deletes_the_token_for_every_role(self):
        for name, pin in (('Papa', '2468'), ('Sami', '1111'), ('Karim', '2222')):
            with self.subTest(name):
                c, token = self.login(name, pin)
                self.assertEqual(c.post('/api/auth/logout/').status_code, 204)
                self.assertFalse(Token.objects.filter(key=token).exists())
                self.assertEqual(c.get('/api/auth/me/').status_code, 401)

    def test_old_token_is_dead_and_next_login_gives_a_new_one(self):
        c, token = self.login('Sami', '1111')
        c.post('/api/auth/logout/')
        again = APIClient()
        again.credentials(HTTP_AUTHORIZATION='Token ' + token)
        self.assertEqual(again.get('/api/stock/').status_code, 401)
        _, new_token = self.login('Sami', '1111')
        self.assertNotEqual(new_token, token)

    def test_second_logout_with_the_same_token_is_rejected(self):
        c, _ = self.login('Sami', '1111')
        c.post('/api/auth/logout/')
        self.assertEqual(c.post('/api/auth/logout/').status_code, 401)

    def test_logout_only_affects_the_caller(self):
        c, _ = self.login('Sami', '1111')
        other, _ = self.login('Karim', '2222')
        c.post('/api/auth/logout/')
        self.assertEqual(other.get('/api/auth/me/').status_code, 200)

    def test_logout_requires_authentication(self):
        self.assertEqual(APIClient().post('/api/auth/logout/').status_code, 401)

    def test_user_stays_active_after_logout(self):
        c, _ = self.login('Sami', '1111')
        c.post('/api/auth/logout/')
        self.assertTrue(User.objects.get(pk=self.cashier.pk).is_active)


class MeTests(UserTestCase):
    def test_me_returns_id_name_and_role_for_each_role(self):
        for user, pin in ((self.manager, '2468'), (self.cashier, '1111'), (self.delivery, '2222')):
            c, _ = self.login(user.name, pin)
            r = c.get('/api/auth/me/')
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data, {'id': user.pk, 'name': user.name, 'role': user.role})

    def test_me_requires_authentication(self):
        self.assertEqual(APIClient().get('/api/auth/me/').status_code, 401)
        bad = APIClient()
        bad.credentials(HTTP_AUTHORIZATION='Token nope')
        self.assertEqual(bad.get('/api/auth/me/').status_code, 401)

    def test_me_exposes_no_secret(self):
        c, _ = self.login('Sami', '1111')
        self.assertEqual(set(c.get('/api/auth/me/').data), {'id', 'name', 'role'})

    def test_me_reflects_a_rename(self):
        c, _ = self.login('Sami', '1111')
        self.api(self.manager).patch(f'/api/users/{self.cashier.pk}/', {'name': 'Samir'}, format='json')
        self.assertEqual(c.get('/api/auth/me/').data['name'], 'Samir')

    def test_session_restore_flow(self):
        """Ce que fait l'app au démarrage : jeton enregistré -> /me/ -> rôle ; jeton mort -> 401."""
        c, token = self.login('Karim', '2222')
        restored = APIClient()
        restored.credentials(HTTP_AUTHORIZATION='Token ' + token)
        self.assertEqual(restored.get('/api/auth/me/').data['role'], 'delivery')
        c.post('/api/auth/logout/')
        self.assertEqual(restored.get('/api/auth/me/').status_code, 401)
