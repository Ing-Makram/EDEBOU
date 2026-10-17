"""Consignes : mouvements manuels (hors vente) et synthèse."""
from collections import defaultdict, deque
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from catalog.models import ConsignType

from .models import ConsignMovement
from .services import BusinessError, _get_client, consign_holdings

OVERDUE_DAYS = 30


@transaction.atomic
def create_consign_movement(user, data):
    """Sortie ou retour manuel. Renvoie (mouvement, created) ; request_id connu : (original, False)."""
    existing = ConsignMovement.objects.filter(request_id=data['request_id']).first()
    if existing:
        return existing, False
    client = _get_client(data['client_id'])
    qty, ctype = data['quantity'], data['consign_type']
    if data['direction'] == 'in':
        held = consign_holdings(client)[ctype]
        if qty > held:
            raise BusinessError(
                'consign_return_exceeds_holdings',
                f'Retour de {qty} ({ctype}) supérieur à ce que le client détient ({held}).',
                consign_type=ctype, returned=qty, held=held)
    movement = ConsignMovement.objects.create(
        client=client, consign_type=ctype, qty_out=qty if data['direction'] == 'out' else 0,
        qty_in=qty if data['direction'] == 'in' else 0, request_id=data['request_id'], user=user)
    return movement, True


def consign_summary(now=None):
    """Total détenu par type, et clients détenant des consignes depuis plus de OVERDUE_DAYS jours.

    Règle FIFO : un retour solde d'abord les plus anciennes sorties encore en cours. Une sortie est
    « en retard » si elle est encore (en partie) due et date de plus de OVERDUE_DAYS jours."""
    now = now or timezone.now()
    limit = timedelta(days=OVERDUE_DAYS)
    totals = {t: 0 for t in ConsignType.values}
    lots = defaultdict(deque)  # (client, type) -> [[date, quantité restante], ...], du plus ancien au plus récent
    names = {}
    for m in ConsignMovement.objects.select_related('client').order_by('created_at', 'id'):
        key = (m.client_id, m.consign_type)
        names[m.client_id] = m.client.name
        totals[m.consign_type] += m.qty_out - m.qty_in
        if m.qty_out:
            lots[key].append([m.created_at, m.qty_out])
        back = m.qty_in
        while back and lots[key]:
            take = min(back, lots[key][0][1])
            lots[key][0][1] -= take
            back -= take
            if lots[key][0][1] == 0:
                lots[key].popleft()

    overdue = []
    for (client_id, ctype), queue in lots.items():
        old = [(d, q) for d, q in queue if now - d > limit]
        if old:
            oldest = old[0][0]
            overdue.append({'client': client_id, 'client_name': names[client_id], 'consign_type': ctype,
                            'held': sum(q for _, q in queue), 'overdue_quantity': sum(q for _, q in old),
                            'oldest_since': timezone.localtime(oldest), 'days': (now - oldest).days})
    overdue.sort(key=lambda r: (-r['days'], r['client_name'], r['consign_type']))
    return {'totals': totals, 'overdue_days': OVERDUE_DAYS, 'overdue': overdue}
