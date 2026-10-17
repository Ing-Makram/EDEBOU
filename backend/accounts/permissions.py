from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):
    """Autorise selon `view.role_actions` = {action: {rôles}}.
    Action absente de la table = réservée au gérant."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        allowed = view.role_actions.get(view.action, {'manager'})
        return user.role in allowed
