import re

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models

PIN_RE = re.compile(r'^\d{4,6}$')


def validate_pin(pin):
    if not PIN_RE.match(str(pin or '')):
        raise ValidationError('Le PIN doit contenir 4 à 6 chiffres.')


class Role(models.TextChoices):
    MANAGER = 'manager', 'Gérant'
    CASHIER = 'cashier', 'Caissier'
    DELIVERY = 'delivery', 'Livreur'


class UserManager(BaseUserManager):
    def create_user(self, name, pin, role=Role.CASHIER):
        validate_pin(pin)
        user = self.model(name=name, role=role)
        user.set_password(pin)  # le PIN est stocké haché dans le champ password
        user.save(using=self._db)
        return user

    def create_superuser(self, name, pin, **extra):
        return self.create_user(name, pin, role=Role.MANAGER)


class User(AbstractBaseUser):
    name = models.CharField(max_length=100, unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CASHIER)
    is_active = models.BooleanField(default=True)

    USERNAME_FIELD = 'name'
    objects = UserManager()

    def __str__(self):
        return self.name
