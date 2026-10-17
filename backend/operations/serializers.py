from rest_framework import serializers

from catalog.models import ConsignType
from catalog.serializers import millimes_field

from .models import ConsignMovement, Payment, PaymentMode, Sale


class LineInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    unit = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1, max_value=1_000_000)
    # Aucun prix accepté : le serveur applique le tarif.


class ReturnedConsignInputSerializer(serializers.Serializer):
    consign_type = serializers.ChoiceField(choices=ConsignType.choices)
    quantity = serializers.IntegerField(min_value=1, max_value=1_000_000)


class SaleCreateSerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    client_id = serializers.IntegerField(required=False, allow_null=True)
    mode = serializers.ChoiceField(choices=PaymentMode.choices)
    paid_amount = millimes_field(required=False, allow_null=True)
    lines = LineInputSerializer(many=True, allow_empty=False, max_length=200)
    returned_consignments = ReturnedConsignInputSerializer(many=True, required=False)


class SaleSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', default=None, read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    paid_amount = serializers.SerializerMethodField()
    reversed_by = serializers.SerializerMethodField()
    lines = serializers.SerializerMethodField()
    consignments = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = ['id', 'request_id', 'client', 'client_name', 'mode', 'total', 'paid_amount', 'user', 'user_name',
                  'created_at', 'reverses', 'reversed_by', 'lines', 'consignments']

    def get_paid_amount(self, obj):
        return sum(p.amount for p in obj.payments.all())

    def get_reversed_by(self, obj):
        return obj.reversed_by.pk if hasattr(obj, 'reversed_by') else None

    def get_lines(self, obj):
        return [{'product': l.product_id, 'product_name': l.product.name, 'unit': l.unit.name,
                 'quantity': l.quantity, 'unit_price': l.unit_price, 'line_total': l.quantity * l.unit_price}
                for l in obj.lines.all()]

    def get_consignments(self, obj):
        return [{'consign_type': c.consign_type, 'qty_out': c.qty_out, 'qty_in': c.qty_in}
                for c in obj.consign_movements.all()]


class PaymentCreateSerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    client_id = serializers.IntegerField()
    amount = millimes_field(min_value=1)
    sale_id = serializers.IntegerField(required=False, allow_null=True)


class PaymentSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    reversed_by = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ['id', 'request_id', 'client', 'client_name', 'amount', 'sale', 'reverses', 'reversed_by',
                  'user', 'user_name', 'created_at']

    def get_reversed_by(self, obj):
        return obj.reversed_by.pk if hasattr(obj, 'reversed_by') else None


class ConsignmentCreateSerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    client_id = serializers.IntegerField()
    consign_type = serializers.ChoiceField(choices=ConsignType.choices)
    direction = serializers.ChoiceField(choices=[('out', 'Sortie'), ('in', 'Retour')])
    quantity = serializers.IntegerField(min_value=1, max_value=1_000_000)


class ConsignmentSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    direction = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()

    class Meta:
        model = ConsignMovement
        fields = ['id', 'request_id', 'client', 'client_name', 'consign_type', 'direction', 'quantity',
                  'qty_out', 'qty_in', 'sale', 'user', 'user_name', 'created_at']

    def get_direction(self, obj):
        return 'out' if obj.qty_out else 'in'

    def get_quantity(self, obj):
        return obj.qty_out or obj.qty_in


class StockEntrySerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    product_id = serializers.IntegerField()
    unit = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1, max_value=1_000_000)
    unit_cost = millimes_field(required=False, allow_null=True)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)


class StockAdjustmentSerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    product_id = serializers.IntegerField()
    reason = serializers.ChoiceField(choices=[('inventory', 'Inventaire'), ('loss', 'Perte / casse')])
    counted_quantity = serializers.IntegerField(min_value=0, max_value=10 ** 9, required=False, allow_null=True)
    delta = serializers.IntegerField(min_value=-10 ** 9, max_value=10 ** 9, required=False, allow_null=True)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, attrs):
        counted, delta = attrs.get('counted_quantity'), attrs.get('delta')
        if (counted is None) == (delta is None):
            raise serializers.ValidationError('Fournir exactement un champ : counted_quantity ou delta.')
        if delta == 0:
            raise serializers.ValidationError({'delta': 'Un écart de 0 ne change rien.'})
        return attrs
