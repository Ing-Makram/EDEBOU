from rest_framework.routers import DefaultRouter

from .views import ConsignmentViewSet, PaymentViewSet, SaleViewSet, StockViewSet

router = DefaultRouter()
router.register('sales', SaleViewSet, basename='sale')
router.register('payments', PaymentViewSet, basename='payment')
router.register('consignments', ConsignmentViewSet, basename='consignment')
router.register('stock', StockViewSet, basename='stock')

urlpatterns = router.urls
