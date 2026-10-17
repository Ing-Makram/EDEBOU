from django.urls import include, path

urlpatterns = [
    path('api/auth/', include('accounts.urls')),
    path('api/', include('accounts.api_urls')),
    path('api/', include('catalog.urls')),
    path('api/', include('operations.urls')),
]
