from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Role, User


class UserModelTests(TestCase):
    def test_pin_is_hashed(self):
        u = User.objects.create_user('Ali', '1234', Role.CASHIER)
        self.assertNotEqual(u.password, '1234')
        self.assertTrue(u.check_password('1234'))

    def test_pin_must_be_4_to_6_digits(self):
        for bad in ('123', '1234567', 'abcd', '12 34', ''):
            with self.assertRaises(ValidationError):
                User.objects.create_user('X' + bad, bad)

    def test_default_role_is_cashier(self):
        self.assertEqual(User.objects.create_user('Sami', '4321').role, Role.CASHIER)


class PinLoginTests(TestCase):
    def setUp(self):
        cache.clear()  # le throttle utilise le cache
        self.api = APIClient()
        User.objects.create_user('Ali', '1234', Role.MANAGER)

    def login(self, name, pin):
        return self.api.post('/api/auth/login/', {'name': name, 'pin': pin}, format='json')

    def test_login_ok_returns_token_and_role(self):
        r = self.login('Ali', '1234')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['role'], Role.MANAGER)
        self.assertTrue(r.data['token'])

    def test_wrong_pin_rejected(self):
        self.assertEqual(self.login('Ali', '9999').status_code, 401)

    def test_unknown_user_rejected(self):
        self.assertEqual(self.login('Zed', '1234').status_code, 401)

    def test_inactive_user_rejected(self):
        User.objects.filter(name='Ali').update(is_active=False)
        self.assertEqual(self.login('Ali', '1234').status_code, 401)

    def test_login_is_throttled(self):
        for _ in range(10):
            self.login('Ali', '0000')
        self.assertEqual(self.login('Ali', '1234').status_code, 429)
