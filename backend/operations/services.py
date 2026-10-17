"""Logique métier des ventes. Tout est ici ; les vues ne font que passer les données.

Montants en millimes (entiers). Stock en unités de base. Les soldes (dette, consignes, stock)
sont toujours calculés à partir des mouvements.
"""
from collections import defaultdict

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from catalog.models import Client, ClientType, ConsignType, Product
from config.errors import BusinessError

from .models import ConsignMovement, Payment, PaymentMode, Sale, SaleLine, StockMovement, StockReason


# ---------- Soldes calculés à partir des mouvements ----------

def client_debt(client):
    """Ventes à crédit − paiements (millimes). Négatif = le client a une avance."""
    credit = Sale.objects.filter(client=client, mode=PaymentMode.CREDIT).aggregate(t=Sum('total'))['t'] or 0
    paid = Payment.objects.filter(client=client).aggregate(t=Sum('amount'))['t'] or 0
    return credit - paid


def consign_holdings(client):
    """Consignes détenues par le client, par type : sorties − retours."""
    holdings = {t: 0 for t in ConsignType.values}
    rows = ConsignMovement.objects.filter(client=client).values('consign_type').annotate(
        out=Sum('qty_out'), back=Sum('qty_in'))
    for r in rows:
        holdings[r['consign_type']] = (r['out'] or 0) - (r['back'] or 0)
    return holdings


def stock_levels(product_ids):
    rows = StockMovement.objects.filter(product_id__in=product_ids).values('product_id').annotate(q=Sum('quantity'))
    levels = {pid: 0 for pid in product_ids}
    levels.update({r['product_id']: r['q'] or 0 for r in rows})
    return levels


# ---------- Création d'une vente ----------

def _get_client(client_id):
    if client_id is None:
        return None
    client = Client.objects.filter(pk=client_id).first()
    if client is None:
        raise BusinessError('client_not_found', 'Client introuvable.')
    if not client.is_active:
        raise BusinessError('client_inactive', f'Le client « {client.name} » est désactivé.')
    return client


def _resolve_lines(raw_lines, client):
    """Valide les lignes et applique le prix du serveur. Renvoie des dicts prêts à enregistrer."""
    products = {p.pk: p for p in Product.objects.filter(pk__in={l['product_id'] for l in raw_lines})
                .prefetch_related('units__prices')}
    client_type = client.type if client else ClientType.RETAIL
    lines = []
    for raw in raw_lines:
        product = products.get(raw['product_id'])
        if product is None:
            raise BusinessError('product_not_found', f'Produit introuvable (id {raw["product_id"]}).')
        if not product.is_active:
            raise BusinessError('product_inactive', f'Le produit « {product.name} » est désactivé.')
        if client is None and product.consignable:
            raise BusinessError('consignable_needs_client',
                                f'« {product.name} » est consigné : un client est obligatoire.', product=product.name)
        unit = next((u for u in product.units.all() if u.name == raw['unit']), None)
        if unit is None:
            raise BusinessError('unit_not_found', f'« {product.name} » n\'a pas d\'unité « {raw["unit"]} ».',
                                product=product.name)
        price = next((p.price for p in unit.prices.all() if p.client_type == client_type), None)
        if price is None:
            raise BusinessError('price_missing',
                                f'Pas de prix pour « {product.name} » ({unit.name}) pour le type de client « {client_type} ».',
                                product=product.name)
        lines.append({'product': product, 'unit': unit, 'quantity': raw['quantity'], 'price': price})
    return lines


def _check_stock(lines):
    needed = defaultdict(int)
    names = {}
    for l in lines:
        needed[l['product'].pk] += l['quantity'] * l['unit'].factor
        names[l['product'].pk] = l['product'].name
    levels = stock_levels(list(needed))
    for pid, qty in needed.items():
        if levels[pid] < qty:
            raise BusinessError(
                'insufficient_stock',
                f'Stock insuffisant pour « {names[pid]} » : demandé {qty}, disponible {levels[pid]}.',
                product=names[pid], requested=qty, available=levels[pid])


def _consign_out(lines):
    out = defaultdict(int)
    for l in lines:
        if l['unit'].consign_qty:
            out[l['unit'].consign_type] += l['unit'].consign_qty * l['quantity']
    return dict(out)


def _merge_returns(returned, client):
    merged = defaultdict(int)
    for r in returned:
        merged[r['consign_type']] += r['quantity']
    if merged and client is None:
        raise BusinessError('consign_return_needs_client', 'Un retour de consigne nécessite un client.')
    if merged:
        held = consign_holdings(client)  # avant cette vente
        for ctype, qty in merged.items():
            if qty > held[ctype]:
                raise BusinessError(
                    'consign_return_exceeds_holdings',
                    f'Retour de {qty} ({ctype}) supérieur à ce que le client détient ({held[ctype]}).',
                    consign_type=ctype, returned=qty, held=held[ctype])
    return dict(merged)


def _check_credit(client, total, paid):
    unpaid = total - paid
    if unpaid > 0 and client.credit_limit > 0:  # plafond 0 = pas de limite
        debt = client_debt(client)
        if debt + unpaid > client.credit_limit:
            raise BusinessError(
                'credit_limit_exceeded',
                f'Plafond de crédit dépassé : dette {debt} + reste à payer {unpaid} > plafond {client.credit_limit}.',
                debt=debt, unpaid=unpaid, credit_limit=client.credit_limit)


def _record_lines(sale, lines):
    for l in lines:
        SaleLine.objects.create(sale=sale, product=l['product'], unit=l['unit'],
                                quantity=l['quantity'], unit_price=l['price'])


def _record_stock(sale, user, lines):
    for l in lines:
        StockMovement.objects.create(product=l['product'], quantity=-l['quantity'] * l['unit'].factor,
                                     reason=StockReason.SALE, sale=sale, user=user)


def _record_consign(sale, user, out, back):
    for ctype, qty in out.items():
        ConsignMovement.objects.create(client=sale.client, consign_type=ctype, qty_out=qty, sale=sale, user=user)
    for ctype, qty in back.items():
        ConsignMovement.objects.create(client=sale.client, consign_type=ctype, qty_in=qty, sale=sale, user=user)


def _record_payment(sale, user, amount):
    if amount:
        Payment.objects.create(client=sale.client, amount=amount, sale=sale, at_sale=True, user=user)


@transaction.atomic
def create_sale(user, data):
    """Crée une vente. Renvoie (sale, created). Si `request_id` existe déjà : (vente d'origine, False).
    Une seule transaction : toute erreur annule tout."""
    existing = Sale.objects.filter(request_id=data['request_id']).first()
    if existing:
        return existing, False

    client = _get_client(data.get('client_id'))
    mode = data['mode']
    paid = data.get('paid_amount') or 0

    if mode == PaymentMode.CASH and paid:
        raise BusinessError('paid_amount_not_allowed', 'paid_amount ne s\'utilise que pour une vente à crédit.')
    if mode == PaymentMode.CREDIT and client is None:
        raise BusinessError('credit_needs_client', 'Une vente à crédit nécessite un client.')

    lines = _resolve_lines(data['lines'], client)
    total = sum(l['quantity'] * l['price'] for l in lines)
    if paid > total:
        raise BusinessError('overpaid', f'Le montant payé ({paid}) dépasse le total ({total}).')

    _check_stock(lines)
    out = _consign_out(lines)
    back = _merge_returns(data.get('returned_consignments', []), client)
    if mode == PaymentMode.CREDIT:
        _check_credit(client, total, paid)

    sale = Sale.objects.create(client=client, mode=mode, total=total, user=user, request_id=data['request_id'])
    _record_lines(sale, lines)
    _record_stock(sale, user, lines)
    _record_consign(sale, user, out, back)
    _record_payment(sale, user, paid)
    return sale, True


# ---------- Annulation ----------

@transaction.atomic
def cancel_sale(user, sale):
    """Écriture inverse complète. L'original n'est jamais modifié."""
    original = Sale.objects.select_related('client').get(pk=sale.pk)
    if original.reverses_id is not None:
        raise BusinessError('cannot_cancel_reversal', 'Une écriture d\'annulation ne peut pas être annulée.')
    if Sale.objects.filter(reverses=original).exists():
        raise BusinessError('already_cancelled', 'Cette vente est déjà annulée.')

    consigns = list(original.consign_movements.all())
    if consigns:
        # L'annulation inverse les consignes : le client ne doit pas se retrouver avec un solde négatif.
        held = consign_holdings(original.client)
        for ctype in {c.consign_type for c in consigns}:
            delta = sum(c.qty_in - c.qty_out for c in consigns if c.consign_type == ctype)
            if held[ctype] + delta < 0:
                raise BusinessError(
                    'cancel_consign_conflict',
                    f'Annulation impossible : le client a déjà rendu les consignes ({ctype}) de cette vente.',
                    consign_type=ctype)

    reversal = Sale.objects.create(client=original.client, mode=original.mode, total=-original.total,
                                   user=user, reverses=original)
    for l in original.lines.all():
        SaleLine.objects.create(sale=reversal, product=l.product, unit=l.unit,
                                quantity=-l.quantity, unit_price=l.unit_price)
    for m in original.stock_movements.all():
        StockMovement.objects.create(product=m.product, quantity=-m.quantity, reason=m.reason,
                                     sale=reversal, user=user)
    for c in consigns:
        ConsignMovement.objects.create(client=c.client, consign_type=c.consign_type,
                                       qty_out=c.qty_in, qty_in=c.qty_out, sale=reversal, user=user)
    # Seuls les paiements faits à la vente sont annulés avec elle. Les paiements ultérieurs restent :
    # le client se retrouve alors avec une avance (dette négative), sans erreur ni arrondi à zéro.
    for p in original.payments.filter(at_sale=True, reversed_by__isnull=True):
        Payment.objects.create(client=p.client, amount=-p.amount, sale=reversal, reverses=p, user=user)
    return reversal


# ---------- Paiements de dette ----------

@transaction.atomic
def create_payment(user, data):
    """Encaisse un paiement. Renvoie (payment, created, warning).
    request_id déjà connu : (paiement d'origine, False, None)."""
    existing = Payment.objects.filter(request_id=data['request_id']).first()
    if existing:
        return existing, False, None

    client = _get_client(data['client_id'])
    sale = None
    if data.get('sale_id') is not None:
        sale = Sale.objects.filter(pk=data['sale_id']).first()
        if sale is None:
            raise BusinessError('sale_not_found', 'Vente introuvable.')
        if sale.client_id != client.pk:
            raise BusinessError('sale_client_mismatch', "Cette vente n'appartient pas à ce client.")
        if sale.mode != PaymentMode.CREDIT:
            raise BusinessError('sale_not_credit', "Cette vente n'est pas une vente à crédit.")
        if sale.reverses_id is not None or Sale.objects.filter(reverses=sale).exists():
            raise BusinessError('sale_cancelled', 'Cette vente est une annulation ou a été annulée.')

    debt_before = client_debt(client)
    payment = Payment.objects.create(client=client, amount=data['amount'], sale=sale,
                                     request_id=data['request_id'], user=user)
    warning = None
    if data['amount'] > debt_before:
        warning = {'code': 'exceeds_debt', 'debt_before': debt_before,
                   'credit_after': data['amount'] - debt_before}
    return payment, True, warning


@transaction.atomic
def cancel_payment(user, payment):
    """Écriture inverse d'un paiement. L'original n'est jamais modifié."""
    original = Payment.objects.get(pk=payment.pk)
    if original.reverses_id is not None or original.amount <= 0:
        raise BusinessError('cannot_cancel_reversal', "Une écriture d'annulation ne peut pas être annulée.")
    if Payment.objects.filter(reverses=original).exists():
        raise BusinessError('already_cancelled', 'Ce paiement est déjà annulé.')
    return Payment.objects.create(client=original.client, amount=-original.amount, sale=original.sale,
                                  reverses=original, user=user)


# ---------- Relevé client ----------

def client_statement(client):
    """Ventes, paiements et mouvements de consigne du client, du plus ancien au plus récent,
    avec la dette courante après chaque écriture. Construit uniquement à partir des mouvements."""
    entries = []
    for s in Sale.objects.filter(client=client):
        delta = s.total if s.mode == PaymentMode.CREDIT else 0
        entries.append((s.created_at, 0, s.pk, {
            'type': 'sale', 'id': s.pk, 'mode': s.mode, 'total': s.total, 'reverses': s.reverses_id,
            'debt_delta': delta}))
    for c in ConsignMovement.objects.filter(client=client):
        entries.append((c.created_at, 1, c.pk, {
            'type': 'consign', 'id': c.pk, 'consign_type': c.consign_type, 'qty_out': c.qty_out,
            'qty_in': c.qty_in, 'sale': c.sale_id, 'debt_delta': 0}))
    for p in Payment.objects.filter(client=client):
        entries.append((p.created_at, 2, p.pk, {
            'type': 'payment', 'id': p.pk, 'amount': p.amount, 'sale': p.sale_id, 'reverses': p.reverses_id,
            'debt_delta': -p.amount}))
    entries.sort(key=lambda e: e[:3])

    balance, rows = 0, []
    holdings = {t: 0 for t in ConsignType.values}
    for created_at, _, _, row in entries:
        balance += row['debt_delta']
        if row['type'] == 'consign':
            holdings[row['consign_type']] += row['qty_out'] - row['qty_in']
        rows.append({'date': timezone.localtime(created_at), **row, 'debt_after': balance, 'consign_after': dict(holdings)})
    return rows
