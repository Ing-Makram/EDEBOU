from .settings import *  # noqa: F401,F403

# Hasher rapide : uniquement pour les tests, jamais en production.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
