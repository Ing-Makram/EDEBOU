from django.db import transaction
from django.db.models import ProtectedError
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from .models import Client, ClientType, ConsignType, Product, ProductPrice, ProductUnit

MAX_MILLIMES = 10 ** 12  # garde-fou contre les valeurs absurdes


def millimes_field(**kwargs):
    kwargs.setdefault('min_value', 0)
    return serializers.IntegerField(max_value=MAX_MILLIMES, **kwargs)


class PriceSerializer(serializers.Serializer):
    client_type = serializers.ChoiceField(choices=ClientType.choices)
    price = millimes_field()


class UnitSerializer(serializers.ModelSerializer):
    factor = serializers.IntegerField(min_value=1)
    consign_type = serializers.ChoiceField(choices=ConsignType.choices, required=False, allow_blank=True)
    prices = PriceSerializer(many=True, required=False)

    class Meta:
        model = ProductUnit
        fields = ['id', 'name', 'factor', 'consign_type', 'consign_qty', 'prices']
        read_only_fields = ['id']

    def validate(self, attrs):
        if attrs.get('consign_qty', 0) > 0 and not attrs.get('consign_type'):
            raise serializers.ValidationError('consign_type est obligatoire si consign_qty > 0.')
        types = [p['client_type'] for p in attrs.get('prices', [])]
        if len(types) != len(set(types)):
            raise serializers.ValidationError('Un seul prix par type de client.')
        return attrs


class ProductSerializer(serializers.ModelSerializer):
    units = UnitSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = ['id', 'name', 'brand', 'category', 'consignable', 'min_threshold', 'is_active', 'units']
        read_only_fields = ['id', 'is_active']

    def validate(self, attrs):
        units = attrs.get('units', [])
        names = [u['name'] for u in units]
        if len(names) != len(set(names)):
            raise serializers.ValidationError({'units': 'Deux unités ont le même nom.'})
        consignable = attrs.get('consignable', self.instance.consignable if self.instance else False)
        if not consignable and any(u.get('consign_qty', 0) > 0 for u in units):
            raise serializers.ValidationError({'units': 'Produit non consignable : consign_qty doit être 0.'})
        return attrs

    @staticmethod
    def _save_prices(unit, prices):
        keep = {p['client_type'] for p in prices}
        unit.prices.exclude(client_type__in=keep).delete()
        for p in prices:
            ProductPrice.objects.update_or_create(unit=unit, client_type=p['client_type'],
                                                  defaults={'price': p['price']})

    @transaction.atomic
    def create(self, validated_data):
        units = validated_data.pop('units', [])
        product = Product.objects.create(**validated_data)
        for u in units:
            prices = u.pop('prices', [])
            self._save_prices(ProductUnit.objects.create(product=product, **u), prices)
        return product

    @transaction.atomic
    def update(self, instance, validated_data):
        units = validated_data.pop('units', None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if units is not None:
            # Les unités sont identifiées par leur nom ; celles absentes de la liste sont supprimées,
            # sauf si des ventes les utilisent (alors 400).
            existing = {u.name: u for u in instance.units.all()}
            for u in units:
                prices = u.pop('prices', None)
                unit = existing.pop(u['name'], None)
                if unit is None:
                    unit = ProductUnit.objects.create(product=instance, **u)
                else:
                    for k, v in u.items():
                        setattr(unit, k, v)
                    unit.save()
                if prices is not None:
                    self._save_prices(unit, prices)
            for unit in existing.values():
                try:
                    unit.delete()
                except ProtectedError:
                    raise serializers.ValidationError(
                        {'units': f'L\'unité « {unit.name} » est utilisée par des ventes : impossible de la supprimer.'})
        return instance


class ClientSerializer(serializers.ModelSerializer):
    credit_limit = millimes_field(required=False)
    debt = serializers.SerializerMethodField()
    consign_holdings = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = ['id', 'name', 'phone', 'type', 'credit_limit', 'is_active', 'debt', 'consign_holdings']
        read_only_fields = ['id', 'is_active']

    # Calculés à partir des mouvements (jamais stockés).
    def get_debt(self, obj):
        from operations.services import client_debt
        return client_debt(obj)

    def get_consign_holdings(self, obj):
        from operations.services import consign_holdings
        return consign_holdings(obj)

    def validate_credit_limit(self, value):
        # Seul le gérant fixe ou change le plafond de crédit.
        user = self.context['request'].user
        current = self.instance.credit_limit if self.instance else 0
        if user.role != 'manager' and value != current:
            raise PermissionDenied('Seul le gérant peut modifier le plafond de crédit.')
        return value
