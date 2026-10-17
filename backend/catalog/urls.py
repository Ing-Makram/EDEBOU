from rest_framework.routers import DefaultRouter

from .views import ClientViewSet, ProductViewSet

router = DefaultRouter()
router.register('products', ProductViewSet)
router.register('clients', ClientViewSet)

urlpatterns = router.urls
