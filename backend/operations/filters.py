from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError


def filter_client_and_dates(qs, params):
    """Filtres communs des listes : ?client=<id>&date_from=AAAA-MM-JJ&date_to=AAAA-MM-JJ (heure de Tunis)."""
    if params.get('client'):
        if not params['client'].isdigit():
            raise ValidationError({'client': 'Identifiant invalide.'})
        qs = qs.filter(client_id=int(params['client']))
    for param, lookup in (('date_from', 'created_at__date__gte'), ('date_to', 'created_at__date__lte')):
        if params.get(param):
            day = parse_date(params[param])
            if day is None:
                raise ValidationError({param: 'Date attendue au format AAAA-MM-JJ.'})
            qs = qs.filter(**{lookup: day})
    return qs
