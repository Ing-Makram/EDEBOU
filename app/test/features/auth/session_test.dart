import 'package:edebou/core/api/api_error.dart';
import 'package:edebou/core/providers.dart';
import 'package:edebou/features/auth/application/auth_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/app_harness.dart';
import '../../helpers/fake_adapter.dart';

/// Appel authentifié direct au client HTTP (hors écran). `runAsync` : Dio utilise de vrais minuteurs,
/// qui n'avancent pas dans l'horloge simulée de testWidgets. L'erreur attendue est ignorée.
Future<void> callApi(WidgetTester tester, String path) async {
  await tester.runAsync(() async {
    try {
      await containerOf(tester).read(apiClientProvider).get(path);
    } on ApiError {
      // attendu : on observe ses effets sur l'écran
    }
  });
}

void main() {
  group('restauration de la session au démarrage (/api/auth/me/)', () {
    testWidgets('jeton valide : on arrive directement sur l\'accueil, sans écran de connexion', (tester) async {
      final app = await AppHarness.pump(
        tester,
        adapter: FakeAdapter((o) => o.path == '/api/auth/me/' ? meOk(name: 'Sami', role: 'cashier') : jsonResponse(404, {})),
        prefs: {'token': 'abc'},
      );
      expect(find.text('Bonjour, Sami'), findsOneWidget);
      expect(find.text('Caissier'), findsOneWidget);
      expect(find.byKey(const Key('login_button')), findsNothing);
      expect(app.adapter.requestsTo('/api/auth/me/').single.headers['Authorization'], 'Token abc');
    });

    testWidgets('pas de jeton : écran de connexion, aucun appel réseau', (tester) async {
      final app = await AppHarness.pump(tester, adapter: FakeAdapter((_) => jsonResponse(404, {})));
      expect(find.byKey(const Key('login_button')), findsOneWidget);
      expect(app.adapter.requests, isEmpty);
    });

    testWidgets('jeton refusé (401) : jeton effacé, écran de connexion', (tester) async {
      final app = await AppHarness.pump(tester, adapter: FakeAdapter((_) => notAuthenticated()), prefs: {'token': 'mort'});
      expect(find.byKey(const Key('login_button')), findsOneWidget);
      expect(app.prefs.getString('token'), isNull);
    });

    testWidgets('le rôle renvoyé décide de l\'écran (livreur)', (tester) async {
      await AppHarness.pump(
        tester,
        adapter: FakeAdapter((_) => meOk(name: 'Karim', role: 'delivery')),
        prefs: {'token': 'abc'},
      );
      expect(find.text('Livreur'), findsOneWidget);
      expect(find.byKey(const Key('module_stock')), findsOneWidget);
      expect(find.byKey(const Key('module_cashRegister')), findsNothing);
    });

    testWidgets('serveur injoignable : le jeton est conservé, écran « Réessayer » + Paramètres', (tester) async {
      final adapter = FakeAdapter((o) => throw connectionError(o));
      final app = await AppHarness.pump(tester, adapter: adapter, prefs: {'token': 'abc'});
      expect(find.byKey(const Key('restore_error')), findsOneWidget);
      expect(find.text('Impossible de joindre le serveur.'), findsOneWidget);
      expect(find.byKey(const Key('login_button')), findsNothing);
      expect(app.prefs.getString('token'), 'abc');

      // Le serveur revient : « Réessayer » restaure la session.
      adapter.handler = (_) => meOk();
      await tester.tap(find.byKey(const Key('restore_retry')));
      await tester.pumpAndSettle();
      expect(find.text('Bonjour, Papa'), findsOneWidget);
    });

    testWidgets('une seule requête quand le serveur est injoignable : pas de réessai automatique caché', (tester) async {
      final app = await AppHarness.pump(tester, adapter: FakeAdapter((o) => throw connectionError(o)), prefs: {'token': 'abc'});
      await tester.pump(const Duration(seconds: 30));
      expect(app.adapter.requestsTo('/api/auth/me/'), hasLength(1));
    });

    testWidgets('l\'écran d\'erreur de démarrage mène aux Paramètres', (tester) async {
      await AppHarness.pump(tester, adapter: FakeAdapter((o) => throw connectionError(o)), prefs: {'token': 'abc'});
      await tester.tap(find.byKey(const Key('restore_settings')));
      await tester.pumpAndSettle();
      expect(find.text('Adresse du serveur'), findsOneWidget);
    });

    testWidgets('réponse inattendue du serveur (rôle inconnu) : écran d\'erreur, pas de plantage', (tester) async {
      await AppHarness.pump(
        tester,
        adapter: FakeAdapter((_) => jsonResponse(200, {'id': 1, 'name': 'X', 'role': 'astronaut'})),
        prefs: {'token': 'abc'},
      );
      expect(find.byKey(const Key('restore_error')), findsOneWidget);
    });
  });

  group('déconnexion', () {
    testWidgets('appelle /api/auth/logout/, efface le jeton, revient à la connexion', (tester) async {
      final app = await AppHarness.pump(
        tester,
        adapter: FakeAdapter((o) => o.path == '/api/auth/logout/' ? jsonResponse(204) : meOk()),
        prefs: {'token': 'abc'},
      );
      await tester.tap(find.byKey(const Key('home_logout')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('login_button')), findsOneWidget);
      expect(app.prefs.getString('token'), isNull);
      final req = app.adapter.requestsTo('/api/auth/logout/').single;
      expect(req.method, 'POST');
      expect(req.headers['Authorization'], 'Token abc'); // le jeton part avant d'être effacé
    });

    testWidgets('serveur injoignable : on se déconnecte quand même localement', (tester) async {
      final adapter = FakeAdapter((_) => meOk());
      final app = await AppHarness.pump(tester, adapter: adapter, prefs: {'token': 'abc'});
      adapter.handler = (o) => throw connectionError(o);
      await tester.tap(find.byKey(const Key('home_logout')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('login_button')), findsOneWidget);
      expect(app.prefs.getString('token'), isNull);
    });

    testWidgets('après déconnexion, on peut se reconnecter avec un autre utilisateur', (tester) async {
      final adapter = FakeAdapter((_) => meOk());
      await AppHarness.pump(tester, adapter: adapter, prefs: {'token': 'abc'});
      adapter.handler = (o) => o.path == '/api/auth/logout/' ? jsonResponse(204) : loginOk(name: 'Karim', role: 'delivery', token: 'zzz');
      await tester.tap(find.byKey(const Key('home_logout')));
      await tester.pumpAndSettle();

      await tester.enterText(find.byKey(const Key('name_field')), 'Karim');
      for (final d in '2222'.split('')) {
        await tester.tap(find.byKey(Key('pin_key_$d')));
      }
      await tester.pump();
      await tester.ensureVisible(find.byKey(const Key('login_button')));
      await tester.tap(find.byKey(const Key('login_button')));
      await tester.pumpAndSettle();
      expect(find.text('Bonjour, Karim'), findsOneWidget);
      expect(find.text('Livreur'), findsOneWidget);
    });
  });

  group('session expirée en cours d\'utilisation (401 sur une requête authentifiée)', () {
    testWidgets('retour à la connexion avec le message « session expirée », jeton effacé', (tester) async {
      final app = await AppHarness.pump(tester, adapter: FakeAdapter((_) => meOk()), prefs: {'token': 'abc'});
      expect(find.text('Bonjour, Papa'), findsOneWidget);

      // Une requête authentifiée quelconque reçoit 401 (ex. le gérant a désactivé ce compte).
      app.adapter.handler = (_) => notAuthenticated();
      await callApi(tester, '/api/stock/');
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('login_button')), findsOneWidget);
      expect(find.byKey(const Key('session_expired')), findsOneWidget);
      expect(find.text('Votre session a expiré. Reconnectez-vous.'), findsOneWidget);
      expect(app.prefs.getString('token'), isNull);
    });

    testWidgets('le message disparaît après une nouvelle connexion', (tester) async {
      final adapter = FakeAdapter((_) => meOk());
      await AppHarness.pump(tester, adapter: adapter, prefs: {'token': 'abc'});
      adapter.handler = (_) => notAuthenticated();
      await callApi(tester, '/api/stock/');
      await tester.pumpAndSettle();
      expect(containerOf(tester).read(sessionNoticeProvider), SessionNotice.expired);

      adapter.handler = (_) => loginOk();
      await tester.enterText(find.byKey(const Key('name_field')), 'Papa');
      for (final d in '2468'.split('')) {
        await tester.tap(find.byKey(Key('pin_key_$d')));
      }
      await tester.pump();
      await tester.ensureVisible(find.byKey(const Key('login_button')));
      await tester.tap(find.byKey(const Key('login_button')));
      await tester.pumpAndSettle();
      expect(containerOf(tester).read(sessionNoticeProvider), SessionNotice.none);
      expect(find.text('Bonjour, Papa'), findsOneWidget);
    });

    testWidgets('une erreur 403 ou réseau ne ferme pas la session', (tester) async {
      final app = await AppHarness.pump(tester, adapter: FakeAdapter((_) => meOk()), prefs: {'token': 'abc'});
      app.adapter.handler = (_) => jsonResponse(403, {'detail': 'x'});
      await callApi(tester, '/api/users/');
      app.adapter.handler = (o) => throw connectionError(o);
      await callApi(tester, '/api/stock/');
      await tester.pumpAndSettle();
      expect(find.text('Bonjour, Papa'), findsOneWidget);
      expect(app.prefs.getString('token'), 'abc');
    });
  });
}
