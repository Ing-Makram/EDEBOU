"""Gestion des utilisateurs : règles métier (qui peut être désactivé, rétrogradé, etc.)."""
from django.db import transaction
from rest_framework.authtoken.models import Token

from config.errors import BusinessError

from .models import Role, User


def _other_active_managers(user):
    return User.objects.filter(role=Role.MANAGER, is_active=True).exclude(pk=user.pk).exists()


@transaction.atomic
def update_user(actor, user, data):
    """Modifie nom, rôle, état actif. Règles :
    - un gérant ne peut pas se désactiver lui-même ;
    - le dernier gérant actif ne peut être ni désactivé ni rétrogradé."""
    user = User.objects.get(pk=user.pk)
    new_active = data.get('is_active', user.is_active)
    new_role = data.get('role', user.role)

    if user.pk == actor.pk and user.is_active and not new_active:
        raise BusinessError('cannot_deactivate_self', 'Vous ne pouvez pas désactiver votre propre compte.')
    loses_manager_power = user.role == Role.MANAGER and user.is_active and (not new_active or new_role != Role.MANAGER)
    if loses_manager_power and not _other_active_managers(user):
        raise BusinessError('last_manager', 'Il doit rester au moins un gérant actif.')

    for field in ('name', 'role', 'is_active'):
        if field in data:
            setattr(user, field, data[field])
    user.save()
    if not user.is_active:
        Token.objects.filter(user=user).delete()  # déconnecte l'utilisateur désactivé immédiatement
    return user


@transaction.atomic
def reset_pin(actor, user, pin, current_token=None):
    """Le gérant fixe un nouveau PIN. Les sessions de l'utilisateur sont fermées
    (sauf la session en cours si le gérant se réinitialise lui-même)."""
    user.set_password(pin)
    user.save(update_fields=['password'])
    tokens = Token.objects.filter(user=user)
    if user.pk == actor.pk and current_token is not None:
        tokens = tokens.exclude(pk=current_token.pk)
    tokens.delete()
    return user


@transaction.atomic
def change_pin(user, old_pin, new_pin):
    if not user.check_password(old_pin):
        raise BusinessError('wrong_pin', 'Ancien PIN incorrect.')
    if old_pin == new_pin:
        raise BusinessError('same_pin', 'Le nouveau PIN doit être différent de l\'ancien.')
    user.set_password(new_pin)
    user.save(update_fields=['password'])
    return user
