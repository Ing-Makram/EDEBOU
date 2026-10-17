// Test d'intégration contre un VRAI serveur Edebou (docs/api.md). Ignoré par défaut.
//
//   cd backend
//   .venv\Scripts\python manage.py migrate
//   .venv\Scripts\python manage.py createmanager Papa --pin 2468
//   .venv\Scripts\python manage.py runserver 127.0.0.1:8000
//
//   cd app
//   $env:EDEBOU_BACKEND_URL="http://127.0.0.1:8000"; flutter test test/backend_contract_test.dart
//
// À lancer sur une base jetable : le test crée un utilisateur « caissier_test » (désactivé à la fin).
import 'dart:io';

import 'package:edebou/core/api/api_client.dart';
import 'package:edebou/core/api/api_error.dart';
import 'package:edebou/core/api/business_code.dart';
import 'package:edebou/core/storage/local_store.dart';
import 'package:edebou/features/auth/data/auth_repository.dart';
import 'package:edebou/features/auth/domain/session.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

final _url = Platform.environment['EDEBOU_BACKEND_URL'];
final _name = Platform.environment['EDEBOU_MANAGER_NAME'] ?? 'Papa';
final _pin = Platform.environment['EDEBOU_MANAGER_PIN'] ?? '2468';

void main() {
  final skip = _url == null ? 'EDEBOU_BACKEND_URL non défini (serveur réel requis)' : null;

  late LocalStore store;
  late ApiClient api;
  late AuthRepository auth;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    store = LocalStore(await SharedPreferences.getInstance());
    api = ApiClient(baseUrl: _url ?? 'http://127.0.0.1:8000', tokenReader: () => store.token);
    auth = AuthRepository(api, store);
  });

  test('probe reconnaît un serveur Edebou', () async {
    expect(await api.probe(), ConnectionStatus.ok);
    expect(await ApiClient(baseUrl: 'http://127.0.0.1:1').probe(), ConnectionStatus.unreachable);
  }, skip: skip);

  test('connexion, restauration de session, déconnexion (docs/api.md « Authentification »)', () async {
    final session = await auth.login(_name, _pin);
    expect(session.role, UserRole.manager);
    expect(session.name, _name);
    expect(store.token, isNotNull);

    final restored = await auth.restore();
    expect(restored, session);

    final oldToken = store.token!;
    await auth.logout();
    expect(store.token, isNull);

    // Le jeton supprimé côté serveur ne marche plus.
    final dead = ApiClient(baseUrl: _url!, tokenReader: () => oldToken);
    await expectLater(dead.get('/api/auth/me/'), throwsA(isA<UnauthorizedError>()));
  }, skip: skip);

  test('mauvais PIN : 401 sans effet de bord', () async {
    await expectLater(auth.login(_name, '0000'), throwsA(isA<UnauthorizedError>()));
    expect(store.token, isNull);
  }, skip: skip);

  test('restore avec un jeton inconnu : 401, jeton effacé', () async {
    await store.setToken('nimporte-quoi');
    expect(await auth.restore(), isNull);
    expect(store.token, isNull);
  }, skip: skip);

  test('erreurs réelles du serveur traduites en erreurs typées', () async {
    await auth.login(_name, _pin);

    // Règle métier (400 + code) : produit inconnu dans une vente.
    final sale = api.post('/api/sales/', body: {
      'request_id': '11111111-1111-4111-8111-111111111111',
      'mode': 'cash',
      'lines': [
        {'product_id': 999999, 'unit': 'unit', 'quantity': 1},
      ],
    });
    await expectLater(
      sale,
      throwsA(isA<BusinessError>()
          .having((e) => e.code, 'code', BusinessCode.productNotFound)
          .having((e) => e.rawCode, 'rawCode', 'product_not_found')),
    );

    // Validation de format (400 sans code), structure imbriquée aplatie.
    final bad = api.post('/api/products/', body: {
      'name': 'Test',
      'category': 'water',
      'units': [
        {
          'name': 'unit',
          'factor': 1,
          'prices': [
            {'client_type': 'retail', 'price': -5},
          ],
        },
      ],
    });
    await expectLater(
      bad,
      throwsA(isA<ValidationError>().having((e) => e.fields.keys, 'clés', contains('units.0.prices.0.price'))),
    );

    // 404 (route inexistante côté ressource).
    await expectLater(api.post('/api/sales/999999/cancel/'), throwsA(isA<NotFoundError>()));
  }, skip: skip);

  test('403 : un caissier ne peut pas lister les utilisateurs', () async {
    await auth.login(_name, _pin);
    Object? created;
    try {
      created = await api.post('/api/users/', body: {'name': 'caissier_test', 'pin': '1357', 'role': 'cashier'});
    } on BusinessError {
      // déjà créé par un lancement précédent
    } on ValidationError {
      // nom déjà pris : lancement précédent
    }
    expect(created == null || created is Map, isTrue);

    final cashierStore = LocalStore(await SharedPreferences.getInstance())..clearToken();
    final cashierApi = ApiClient(baseUrl: _url!, tokenReader: () => cashierStore.token);
    final cashier = await AuthRepository(cashierApi, cashierStore).login('caissier_test', '1357');
    expect(cashier.role, UserRole.cashier);
    await expectLater(cashierApi.get('/api/users/'), throwsA(isA<ForbiddenError>()));
    // Le caissier lit le stock (200) : le jeton est bien attaché par le client.
    expect(await cashierApi.get('/api/stock/'), isA<List>());
  }, skip: skip);

  test('les réponses de /api/auth/login/ et /me/ ont la forme documentée', () async {
    final login = await api.post('/api/auth/login/', body: {'name': _name, 'pin': _pin}, authenticated: false) as Map;
    expect(login.keys, containsAll(['token', 'name', 'role']));
    store.setToken(login['token'] as String);
    final me = await api.get('/api/auth/me/') as Map;
    expect(me.keys.toSet(), {'id', 'name', 'role'});
    expect(me['id'], isA<int>());
  }, skip: skip);
}
