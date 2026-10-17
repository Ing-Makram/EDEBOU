import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:edebou/core/api/api_client.dart';
import 'package:edebou/core/api/api_error.dart';
import 'package:edebou/core/api/business_code.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_adapter.dart';

ApiClient makeClient(
  FakeAdapter adapter, {
  String? token,
  void Function()? onUnauthorized,
  String baseUrl = 'http://127.0.0.1:8000',
}) {
  return ApiClient(
    baseUrl: baseUrl,
    tokenReader: () => token,
    onUnauthorized: onUnauthorized,
    dio: Dio()..httpClientAdapter = adapter,
  );
}

/// Envoie un GET qui reçoit [status] + [body] et renvoie l'erreur levée.
Future<ApiError> errorFor(int status, Object? body, {bool authenticated = true, void Function()? onUnauthorized}) async {
  final client = makeClient(FakeAdapter((_) => jsonResponse(status, body)), token: 't', onUnauthorized: onUnauthorized);
  try {
    await client.get('/api/x/', authenticated: authenticated);
  } on ApiError catch (e) {
    return e;
  }
  fail('Aucune erreur levée pour le statut $status');
}

void main() {
  group('requêtes', () {
    test('GET renvoie le JSON décodé et construit l\'URL à partir de l\'adresse du serveur', () async {
      final adapter = FakeAdapter((_) => jsonResponse(200, {'id': 1, 'name': 'Papa', 'role': 'manager'}));
      final data = await makeClient(adapter, token: 'abc').get('/api/auth/me/');
      expect(data, {'id': 1, 'name': 'Papa', 'role': 'manager'});
      expect(adapter.requests.single.uri.toString(), 'http://127.0.0.1:8000/api/auth/me/');
      expect(adapter.requests.single.method, 'GET');
    });

    test('le jeton est ajouté en « Authorization: Token … »', () async {
      final adapter = FakeAdapter((_) => jsonResponse(200, []));
      await makeClient(adapter, token: 'abc123').get('/api/stock/');
      expect(adapter.requests.single.headers['Authorization'], 'Token abc123');
    });

    test('pas de jeton enregistré : pas d\'en-tête Authorization', () async {
      final adapter = FakeAdapter((_) => jsonResponse(200, []));
      await makeClient(adapter, token: null).get('/api/stock/');
      expect(adapter.requests.single.headers.containsKey('Authorization'), isFalse);
    });

    test('authenticated: false n\'envoie jamais le jeton (connexion)', () async {
      final adapter = FakeAdapter((_) => jsonResponse(200, {'token': 'x'}));
      await makeClient(adapter, token: 'abc').post('/api/auth/login/', body: {'name': 'a', 'pin': '1234'}, authenticated: false);
      expect(adapter.requests.single.headers.containsKey('Authorization'), isFalse);
    });

    test('POST envoie le corps en JSON', () async {
      final adapter = FakeAdapter((_) => jsonResponse(201, {'id': 7}));
      final data = await makeClient(adapter, token: 't').post('/api/payments/', body: {'client_id': 1, 'amount': 5000});
      expect(data, {'id': 7});
      final req = adapter.requests.single;
      expect(req.method, 'POST');
      expect(req.headers['Content-Type'], 'application/json');
      expect(jsonDecode(req.data as String), {'client_id': 1, 'amount': 5000});
    });

    test('PATCH et paramètres de requête', () async {
      final adapter = FakeAdapter((_) => jsonResponse(200, {}));
      final c = makeClient(adapter, token: 't');
      await c.patch('/api/users/2/', body: {'is_active': false});
      await c.get('/api/clients/', query: {'search': 'caf'});
      expect(adapter.requests[0].method, 'PATCH');
      expect(adapter.requests[1].uri.queryParameters, {'search': 'caf'});
    });

    test('204 sans corps donne null', () async {
      final adapter = FakeAdapter((_) => jsonResponse(204));
      expect(await makeClient(adapter, token: 't').post('/api/auth/logout/'), isNull);
    });

    test('un montant en millimes reste un entier (pas de flottant)', () async {
      final adapter = FakeAdapter((_) => jsonResponse(200, {'total': 14100, 'debt': -3500}));
      final data = await makeClient(adapter, token: 't').get('/api/x/') as Map;
      expect(data['total'], isA<int>());
      expect(data['debt'], -3500);
    });
  });

  group('erreurs métier (400 avec code)', () {
    test('insufficient_stock : code typé et contexte entier conservé', () async {
      final e = await errorFor(400, {
        'code': 'insufficient_stock',
        'detail': 'Stock insuffisant pour « Eau » : demandé 3000, disponible 269.',
        'product': 'Eau minérale 1.5L',
        'requested': 3000,
        'available': 269,
      });
      expect(e, isA<BusinessError>());
      final b = e as BusinessError;
      expect(b.code, BusinessCode.insufficientStock);
      expect(b.rawCode, 'insufficient_stock');
      expect(b.intContext('available'), 269);
      expect(b.intContext('requested'), 3000);
      expect(b.stringContext('product'), 'Eau minérale 1.5L');
      expect(b.context.containsKey('code'), isFalse);
      expect(b.context.containsKey('detail'), isFalse);
      expect(b.detail, contains('Stock insuffisant'));
    });

    test('credit_limit_exceeded et consign_return_exceeds_holdings', () async {
      final credit = await errorFor(400, {
        'code': 'credit_limit_exceeded', 'detail': 'x', 'debt': 13100, 'unpaid': 114000, 'credit_limit': 100000,
      }) as BusinessError;
      expect(credit.code, BusinessCode.creditLimitExceeded);
      expect([credit.intContext('debt'), credit.intContext('unpaid'), credit.intContext('credit_limit')],
          [13100, 114000, 100000]);

      final ret = await errorFor(400, {
        'code': 'consign_return_exceeds_holdings', 'detail': 'x', 'consign_type': 'crate', 'returned': 9, 'held': 3,
      }) as BusinessError;
      expect(ret.code, BusinessCode.consignReturnExceedsHoldings);
      expect(ret.intContext('held'), 3);
      expect(ret.stringContext('consign_type'), 'crate');
    });

    test('code inconnu (serveur plus récent) : BusinessCode.unknown, code brut conservé', () async {
      final b = await errorFor(400, {'code': 'brand_new_rule', 'detail': 'x', 'n': 1}) as BusinessError;
      expect(b.code, BusinessCode.unknown);
      expect(b.rawCode, 'brand_new_rule');
      expect(b.intContext('n'), 1);
    });

    test('un contexte absent donne null, pas une exception', () async {
      final b = await errorFor(400, {'code': 'no_change', 'detail': 'x'}) as BusinessError;
      expect(b.intContext('current'), isNull);
      expect(b.stringContext('product'), isNull);
    });

    test('un champ de contexte texte n\'est pas pris pour un entier', () async {
      final b = await errorFor(400, {'code': 'insufficient_stock', 'detail': 'x', 'available': '269'}) as BusinessError;
      expect(b.intContext('available'), isNull);
    });
  });

  group('erreurs de validation (400 sans code)', () {
    test('champs simples', () async {
      final e = await errorFor(400, {
        'amount': ['Assurez-vous que cette valeur est supérieure ou égale à 1.'],
      });
      expect(e, isA<ValidationError>());
      expect((e as ValidationError).fields, {'amount': ['Assurez-vous que cette valeur est supérieure ou égale à 1.']});
    });

    test('structure imbriquée du produit aplatie en units.0.prices.0.price', () async {
      final e = await errorFor(400, {
        'units': {'0': {'prices': {'0': {'price': ['trop petit']}}}},
      }) as ValidationError;
      expect(e.fields, {'units.0.prices.0.price': ['trop petit']});
    });

    test('liste d\'objets (lignes de vente) aplatie avec l\'index', () async {
      final e = await errorFor(400, {
        'lines': [{}, {'quantity': ['invalide']}],
        'name': ['obligatoire', 'trop court'],
      }) as ValidationError;
      expect(e.fields, {'lines.1.quantity': ['invalide'], 'name': ['obligatoire', 'trop court']});
    });

    test('plusieurs champs en erreur', () async {
      final e = await errorFor(400, {
        'name': ['Ce nom est déjà utilisé.'],
        'pin': ['Le PIN doit contenir 4 à 6 chiffres.'],
      }) as ValidationError;
      expect(e.fields.keys, containsAll(['name', 'pin']));
    });

    test('400 dont le corps n\'est pas un objet : UnknownError', () async {
      final e = await errorFor(400, ['bizarre']);
      expect(e, isA<UnknownError>());
      expect((e as UnknownError).status, 400);
    });

    test('400 avec un code qui n\'est pas du texte : traité comme validation', () async {
      expect(await errorFor(400, {'code': ['x']}), isA<ValidationError>());
    });
  });

  group('statuts HTTP', () {
    test('401 → UnauthorizedError avec le detail', () async {
      final e = await errorFor(401, {'detail': 'Token non valide.'});
      expect(e, isA<UnauthorizedError>());
      expect((e as UnauthorizedError).detail, 'Token non valide.');
    });

    test('403 → ForbiddenError', () async {
      expect(await errorFor(403, {'detail': 'Vous n\'avez pas la permission.'}), isA<ForbiddenError>());
    });

    test('404 → NotFoundError', () async {
      expect(await errorFor(404, {'detail': 'Pas trouvé.'}), isA<NotFoundError>());
    });

    test('429 → ThrottledError', () async {
      expect(await errorFor(429, {'detail': 'limité'}), isA<ThrottledError>());
    });

    test('500 et 503 → ServerError avec le statut', () async {
      expect((await errorFor(500, {'detail': 'x'}) as ServerError).status, 500);
      expect((await errorFor(503, null) as ServerError).status, 503);
    });

    test('statut inattendu → UnknownError avec le statut', () async {
      final e = await errorFor(418, null) as UnknownError;
      expect(e.status, 418);
      expect(await errorFor(405, {'detail': 'x'}), isA<UnknownError>());
    });

    test('page HTML d\'erreur (corps non JSON) ne plante pas', () async {
      final client = makeClient(FakeAdapter((_) => textResponse(500, '<html>Server Error</html>')), token: 't');
      await expectLater(client.get('/api/x/'), throwsA(isA<ServerError>()));
    });

    test('un 2xx dont le corps n\'est pas du JSON donne null', () async {
      final client = makeClient(FakeAdapter((_) => textResponse(200, 'pas du json')), token: 't');
      expect(await client.get('/api/x/'), isNull);
    });
  });

  group('session expirée (401 sur une requête authentifiée)', () {
    test('appelle onUnauthorized une fois', () async {
      var calls = 0;
      await errorFor(401, {'detail': 'x'}, onUnauthorized: () => calls++);
      expect(calls, 1);
    });

    test('pas d\'appel pour une requête non authentifiée (mauvais PIN à la connexion)', () async {
      var calls = 0;
      final e = await errorFor(401, {'detail': 'Nom ou PIN incorrect.'}, authenticated: false, onUnauthorized: () => calls++);
      expect(e, isA<UnauthorizedError>());
      expect(calls, 0);
    });

    test('pas d\'appel pour les autres erreurs', () async {
      var calls = 0;
      await errorFor(403, {'detail': 'x'}, onUnauthorized: () => calls++);
      await errorFor(500, null, onUnauthorized: () => calls++);
      await errorFor(400, {'code': 'x', 'detail': 'y'}, onUnauthorized: () => calls++);
      expect(calls, 0);
    });
  });

  group('erreurs réseau', () {
    test('connexion refusée → NetworkError sans timeout', () async {
      final client = makeClient(FakeAdapter((o) => throw connectionError(o)), token: 't');
      await expectLater(
        client.get('/api/x/'),
        throwsA(isA<NetworkError>().having((e) => e.timeout, 'timeout', false)),
      );
    });

    test('délais dépassés → NetworkError avec timeout', () async {
      for (final type in [
        DioExceptionType.connectionTimeout,
        DioExceptionType.sendTimeout,
        DioExceptionType.receiveTimeout,
      ]) {
        final client = makeClient(FakeAdapter((o) => throw timeoutError(o, type)), token: 't');
        await expectLater(
          client.get('/api/x/'),
          throwsA(isA<NetworkError>().having((e) => e.timeout, 'timeout', true)),
          reason: '$type',
        );
      }
    });

    test('une erreur réseau n\'est pas une session expirée', () async {
      var calls = 0;
      final client = makeClient(FakeAdapter((o) => throw connectionError(o)), token: 't', onUnauthorized: () => calls++);
      await expectLater(client.get('/api/x/'), throwsA(isA<NetworkError>()));
      expect(calls, 0);
    });
  });

  group('probe (test de connexion)', () {
    test('serveur Edebou : 401 avec detail → ok, sans envoyer de jeton', () async {
      final adapter = FakeAdapter((_) => jsonResponse(401, {'detail': 'Informations d\'authentification non fournies.'}));
      expect(await makeClient(adapter, token: 'abc').probe(), ConnectionStatus.ok);
      expect(adapter.requests.single.path, '/api/auth/me/');
      expect(adapter.requests.single.headers.containsKey('Authorization'), isFalse);
    });

    test('un autre logiciel : 404, 200, 401 sans detail → notEdebou', () async {
      expect(await makeClient(FakeAdapter((_) => textResponse(404, 'nope'))).probe(), ConnectionStatus.notEdebou);
      expect(await makeClient(FakeAdapter((_) => textResponse(200, '<html></html>'))).probe(), ConnectionStatus.notEdebou);
      expect(await makeClient(FakeAdapter((_) => textResponse(401, 'Unauthorized'))).probe(), ConnectionStatus.notEdebou);
    });

    test('injoignable et délai dépassé', () async {
      expect(await makeClient(FakeAdapter((o) => throw connectionError(o))).probe(), ConnectionStatus.unreachable);
      expect(await makeClient(FakeAdapter((o) => throw timeoutError(o))).probe(), ConnectionStatus.timeout);
    });
  });

  test('mapErrorResponse est cohérent avec les erreurs levées', () {
    expect(ApiClient.mapErrorResponse(401, {'detail': 'a'}), isA<UnauthorizedError>());
    expect(ApiClient.mapErrorResponse(400, {'code': 'overpaid'}), isA<BusinessError>());
  });

  test('BusinessCode.fromWire', () {
    expect(BusinessCode.fromWire('last_manager'), BusinessCode.lastManager);
    expect(BusinessCode.fromWire(''), BusinessCode.unknown);
    expect(BusinessCode.fromWire('nope'), BusinessCode.unknown);
    for (final c in BusinessCode.values.where((c) => c != BusinessCode.unknown)) {
      expect(BusinessCode.fromWire(c.wire), c);
    }
  });
}
