from django.urls import path

from .views import ChangePinView, LoginView, LogoutView, MeView

urlpatterns = [
    path('login/', LoginView.as_view()),
    path('logout/', LogoutView.as_view()),
    path('me/', MeView.as_view()),
    path('change-pin/', ChangePinView.as_view()),
]
