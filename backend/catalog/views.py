from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from accounts.permissions import RolePermission

from .models import Client, Product
from .serializers import ClientSerializer, ProductSerializer

ALL = {'manager', 'cashier', 'delivery'}
STAFF = {'manager', 'cashier'}


class CatalogViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                     mixins.ListModelMixin, viewsets.GenericViewSet):
    """Pas de DELETE : on désactive (jamais de suppression)."""
    permission_classes = [RolePermission]

    def get_queryset(self):
        qs = super().get_queryset()
        active = self.request.query_params.get('is_active')
        if active in ('true', 'false'):
            qs = qs.filter(is_active=(active == 'true'))
        return qs

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        obj = self.get_object()
        obj.is_active = False
        obj.save(update_fields=['is_active'])
        return Response(self.get_serializer(obj).data)


class ProductViewSet(CatalogViewSet):
    queryset = Product.objects.prefetch_related('units__prices').order_by('name')
    serializer_class = ProductSerializer
    role_actions = {'list': ALL, 'retrieve': ALL}  # écriture : gérant seulement


class ClientViewSet(CatalogViewSet):
    queryset = Client.objects.order_by('name')
    serializer_class = ClientSerializer
    filter_backends = [SearchFilter]
    search_fields = ['name', 'phone']
    role_actions = {'list': STAFF, 'retrieve': STAFF, 'create': STAFF,
                    'update': STAFF, 'partial_update': STAFF,
                    'statement': STAFF}  # désactivation : gérant seulement

    @action(detail=True, methods=['get'])
    def statement(self, request, pk=None):
        from operations import services
        client = self.get_object()
        return Response({'client': client.pk, 'name': client.name,
                         'debt': services.client_debt(client),
                         'consign_holdings': services.consign_holdings(client),
                         'entries': services.client_statement(client)})
