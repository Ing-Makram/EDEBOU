from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from accounts.permissions import RolePermission
from catalog.models import Product

from . import consign_services, services, stock_services
from .filters import filter_client_and_dates
from .models import ConsignMovement, Payment, Sale
from .serializers import (ConsignmentCreateSerializer, ConsignmentSerializer, PaymentCreateSerializer,
                          PaymentSerializer, SaleCreateSerializer, SaleSerializer, StockAdjustmentSerializer,
                          StockEntrySerializer)

STAFF = {'manager', 'cashier'}


class SaleViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [RolePermission]
    serializer_class = SaleSerializer
    role_actions = {'list': STAFF, 'retrieve': STAFF, 'create': STAFF}  # cancel : gérant seulement

    def get_queryset(self):
        qs = Sale.objects.select_related('client', 'user', 'reversed_by').prefetch_related(
            'lines__product', 'lines__unit', 'payments', 'consign_movements').order_by('-created_at', '-id')
        if self.action != 'list':
            return qs
        return filter_client_and_dates(qs, self.request.query_params)

    def create(self, request):
        s = SaleCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        sale, created = services.create_sale(request.user, s.validated_data)
        sale = self.get_queryset().get(pk=sale.pk)
        return Response(self.get_serializer(sale).data, status=201 if created else 200)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        original = get_object_or_404(Sale, pk=pk)
        reversal = services.cancel_sale(request.user, original)
        reversal = self.get_queryset().get(pk=reversal.pk)
        return Response(self.get_serializer(reversal).data, status=201)


class PaymentViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [RolePermission]
    serializer_class = PaymentSerializer
    role_actions = {'list': STAFF, 'create': STAFF}  # cancel : gérant seulement

    def get_queryset(self):
        qs = Payment.objects.select_related('client', 'user', 'reversed_by').order_by('-created_at', '-id')
        if self.action != 'list':
            return qs
        return filter_client_and_dates(qs, self.request.query_params)

    def create(self, request):
        s = PaymentCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        payment, created, warning = services.create_payment(request.user, s.validated_data)
        data = dict(self.get_serializer(self.get_queryset().get(pk=payment.pk)).data)
        data['warning'] = warning
        return Response(data, status=201 if created else 200)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        original = get_object_or_404(Payment, pk=pk)
        reversal = services.cancel_payment(request.user, original)
        return Response(self.get_serializer(self.get_queryset().get(pk=reversal.pk)).data, status=201)


class ConsignmentViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Mouvements de consigne (ceux des ventes + les mouvements manuels). Lecture et ajout seulement."""
    permission_classes = [RolePermission]
    serializer_class = ConsignmentSerializer
    role_actions = {'list': STAFF, 'create': STAFF, 'summary': STAFF}

    def get_queryset(self):
        qs = ConsignMovement.objects.select_related('client', 'user').order_by('-created_at', '-id')
        if self.action != 'list':
            return qs
        params = self.request.query_params
        if params.get('type'):
            if params['type'] not in ('crate', 'glass_bottle'):
                raise ValidationError({'type': 'Type de consigne inconnu.'})
            qs = qs.filter(consign_type=params['type'])
        return filter_client_and_dates(qs, params)

    def create(self, request):
        s = ConsignmentCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        movement, created = consign_services.create_consign_movement(request.user, s.validated_data)
        return Response(self.get_serializer(self.get_queryset().get(pk=movement.pk)).data,
                        status=201 if created else 200)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        return Response(consign_services.consign_summary())


class StockViewSet(viewsets.GenericViewSet):
    """Stock calculé à partir des mouvements. Lecture : tous les rôles ; écriture et historique : gérant."""
    permission_classes = [RolePermission]
    queryset = Product.objects.all()
    role_actions = {'list': {'manager', 'cashier', 'delivery'}}  # entries, adjustments, movements : gérant

    def list(self, request):
        return Response(stock_services.stock_overview())

    def _write(self, request, serializer_class, service):
        s = serializer_class(data=request.data)
        s.is_valid(raise_exception=True)
        movement, stock, created = service(request.user, s.validated_data)
        row = stock_services.movement_row(movement, None)
        row.pop('balance_after')
        return Response({**row, 'stock': stock}, status=201 if created else 200)

    @action(detail=False, methods=['post'])
    def entries(self, request):
        return self._write(request, StockEntrySerializer, stock_services.create_entry)

    @action(detail=False, methods=['post'])
    def adjustments(self, request):
        return self._write(request, StockAdjustmentSerializer, stock_services.create_adjustment)

    @action(detail=True, methods=['get'])
    def movements(self, request, pk=None):
        return Response(stock_services.movement_history(get_object_or_404(Product, pk=pk)))
