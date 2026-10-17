"""Stock : entrées, ajustements, vue d'ensemble, historique.

Le stock n'est jamais stocké : c'est la somme des StockMovement (unités de base).
"""
from django.db import transaction
from django.utils import timezone

from catalog.models import Product

from .models import StockMovement, StockReason
from .services import BusinessError, stock_levels


def _get_product(product_id):
    product = Product.objects.filter(pk=product_id).prefetch_related('units').first()
    if product is None:
        raise BusinessError('product_not_found', f'Produit introuvable (id {product_id}).')
    if not product.is_active:
        raise BusinessError('product_inactive', f'Le produit « {product.name} » est désactivé.')
    return product


def _movement_result(movement):
    return movement, stock_levels([movement.product_id])[movement.product_id]


@transaction.atomic
def create_entry(user, data):
    """Achat fournisseur / livraison reçue. Renvoie (mouvement, stock_actuel, created)."""
    existing = StockMovement.objects.filter(request_id=data['request_id']).first()
    if existing:
        return (*_movement_result(existing), False)
    product = _get_product(data['product_id'])
    unit = next((u for u in product.units.all() if u.name == data['unit']), None)
    if unit is None:
        raise BusinessError('unit_not_found', f'« {product.name} » n\'a pas d\'unité « {data["unit"]} ».',
                            product=product.name)
    movement = StockMovement.objects.create(
        product=product, quantity=data['quantity'] * unit.factor, reason=StockReason.PURCHASE, unit=unit,
        unit_cost=data.get('unit_cost'), note=data.get('note', ''), request_id=data['request_id'], user=user)
    return (*_movement_result(movement), True)


@transaction.atomic
def create_adjustment(user, data):
    """Correction d'inventaire ou perte/casse. Renvoie (mouvement, stock_actuel, created).
    `counted_quantity` : le mouvement est l'écart avec le stock actuel ; `delta` : écart signé direct."""
    existing = StockMovement.objects.filter(request_id=data['request_id']).first()
    if existing:
        return (*_movement_result(existing), False)
    product = _get_product(data['product_id'])
    current = stock_levels([product.pk])[product.pk]

    if data.get('counted_quantity') is not None:
        delta = data['counted_quantity'] - current
        if delta == 0:
            raise BusinessError('no_change', f'Le stock compté ({current}) est déjà le stock actuel.',
                                product=product.name, current=current)
    else:
        delta = data['delta']
    if data['reason'] == StockReason.LOSS and delta > 0:
        raise BusinessError('loss_must_decrease', 'Une perte ou casse doit diminuer le stock.',
                            product=product.name, delta=delta)
    if current + delta < 0:
        raise BusinessError('adjustment_below_zero',
                            f'Ajustement impossible pour « {product.name} » : le stock deviendrait négatif '
                            f'({current} {delta:+d}).', product=product.name, current=current, delta=delta)
    movement = StockMovement.objects.create(
        product=product, quantity=delta, reason=data['reason'], note=data.get('note', ''),
        request_id=data['request_id'], user=user)
    return (*_movement_result(movement), True)


def breakdown(product, quantity):
    """Décompose une quantité (unités de base) en unités de vente, de la plus grande à la plus petite.
    `remainder` = unités de base restantes qui ne forment aucune unité (produit sans unité de facteur 1)."""
    rows, rest = [], max(quantity, 0)
    for unit in sorted(product.units.all(), key=lambda u: -u.factor):
        count, rest = divmod(rest, unit.factor)
        rows.append({'unit': unit.name, 'factor': unit.factor, 'count': count})
    return rows, rest


def stock_overview():
    products = list(Product.objects.prefetch_related('units').order_by('name'))
    levels = stock_levels([p.pk for p in products])
    out = []
    for p in products:
        qty = levels[p.pk]
        rows, rest = breakdown(p, qty)
        out.append({
            'product': p.pk, 'name': p.name, 'brand': p.brand, 'category': p.category, 'is_active': p.is_active,
            'quantity': qty, 'breakdown': rows, 'remainder': rest,
            'min_threshold': p.min_threshold,
            'low_stock': p.min_threshold > 0 and qty <= p.min_threshold,
        })
    return out


def movement_row(m, balance_after):
    return {'id': m.pk, 'request_id': m.request_id, 'product': m.product_id, 'quantity': m.quantity,
            'reason': m.reason, 'sale': m.sale_id, 'unit': m.unit.name if m.unit else None,
            'unit_cost': m.unit_cost, 'note': m.note, 'user': m.user_id, 'user_name': m.user.name,
            'created_at': timezone.localtime(m.created_at), 'balance_after': balance_after}


def movement_history(product):
    """Historique du produit, du plus récent au plus ancien, avec le stock après chaque mouvement."""
    balance, rows = 0, []
    for m in StockMovement.objects.filter(product=product).select_related('user', 'unit').order_by('created_at', 'id'):
        balance += m.quantity
        rows.append(movement_row(m, balance))
    return rows[::-1]
