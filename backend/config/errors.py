from rest_framework.exceptions import APIException


class BusinessError(APIException):
    """Règle métier violée : réponse 400 avec un `code` stable (traduisible côté Flutter)."""
    status_code = 400

    def __init__(self, code, message, **extra):
        super().__init__(message)
        # Garder les valeurs brutes : DRF convertirait les entiers (stock, dette…) en chaînes.
        self.detail = {'code': code, 'detail': message, **extra}
