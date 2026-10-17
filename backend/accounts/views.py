from django.contrib.auth import authenticate
from rest_framework import mixins, serializers, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from .models import Role, User
from .permissions import RolePermission
from . import services

PIN_FIELD = dict(regex=r'^\d{4,6}$', error_messages={'invalid': 'Le PIN doit contenir 4 à 6 chiffres.'},
                 write_only=True, trim_whitespace=False)


class LoginSerializer(serializers.Serializer):
    name = serializers.CharField()
    pin = serializers.CharField(write_only=True)


class LoginThrottle(AnonRateThrottle):
    scope = 'login'


class ChangePinThrottle(UserRateThrottle):
    scope = 'change_pin'


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = authenticate(request, username=s.validated_data['name'], password=s.validated_data['pin'])
        if user is None:
            return Response({'detail': 'Nom ou PIN incorrect.'}, status=401)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'name': user.name, 'role': user.role})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({'id': u.pk, 'name': u.name, 'role': u.role})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.auth.delete()  # le jeton n'est plus valable ; la prochaine connexion en crée un nouveau
        return Response(status=204)


class ChangePinSerializer(serializers.Serializer):
    old_pin = serializers.CharField(write_only=True)
    new_pin = serializers.RegexField(**PIN_FIELD)


class ChangePinView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ChangePinThrottle]  # l'ancien PIN ne doit pas pouvoir être deviné par force brute

    def post(self, request):
        s = ChangePinSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.change_pin(request.user, s.validated_data['old_pin'], s.validated_data['new_pin'])
        return Response({'detail': 'PIN modifié.'})


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=100)
    role = serializers.ChoiceField(choices=Role.choices)

    class Meta:
        model = User
        fields = ['id', 'name', 'role', 'is_active']
        read_only_fields = ['id', 'is_active']

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Le nom est obligatoire.')
        clash = User.objects.filter(name__iexact=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError('Ce nom est déjà utilisé.')
        return value


class UserCreateSerializer(UserSerializer):
    pin = serializers.RegexField(**PIN_FIELD)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['pin']


class UserUpdateSerializer(UserSerializer):
    is_active = serializers.BooleanField(required=False)

    class Meta(UserSerializer.Meta):
        read_only_fields = ['id']


class ResetPinSerializer(serializers.Serializer):
    pin = serializers.RegexField(**PIN_FIELD)


class UserViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
                  viewsets.GenericViewSet):
    """Gérant seulement (toute action absente de role_actions est réservée au gérant). Pas de suppression."""
    permission_classes = [RolePermission]
    role_actions = {}
    queryset = User.objects.order_by('name')
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        return {'create': UserCreateSerializer, 'partial_update': UserUpdateSerializer}.get(self.action, UserSerializer)

    def create(self, request):
        s = UserCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        user = User.objects.create_user(d['name'], d['pin'], d['role'])
        return Response(UserSerializer(user).data, status=201)

    def partial_update(self, request, pk=None):
        user = self.get_object()
        s = UserUpdateSerializer(user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        user = services.update_user(request.user, user, s.validated_data)
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=['post'], url_path='reset-pin')
    def reset_pin(self, request, pk=None):
        user = self.get_object()
        s = ResetPinSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.reset_pin(request.user, user, s.validated_data['pin'], current_token=request.auth)
        return Response({'detail': 'PIN réinitialisé.'})
