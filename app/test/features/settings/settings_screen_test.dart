import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:edebou/core/api/api_client.dart';
import 'package:edebou/core/providers.dart';
import 'package:edebou/features/settings/presentation/settings_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/app_harness.dart';
import '../../helpers/fake_adapter.dart';

/// Ouvre l'écran de connexion puis les Paramètres, avec un « testeur de connexion » simulé.
Future<(AppHarness, List<String>)> openSettings(
  WidgetTester tester, {
  ConnectionStatus result = ConnectionStatus.ok,
  Map<String, Object> prefs = const {},
  FakeAdapter? adapter,
}) async {
  final tested = <String>[];
  final app = await AppHarness.pump(
    tester,
    adapter: adapter ?? FakeAdapter((_) => notAuthenticated()),
    prefs: prefs,
    overrides: [
      connectionProberProvider.overrideWithValue((url) async {
        tested.add(url);
        return result;
      }),
    ],
  );
  await tester.tap(find.byKey(const Key('open_settings')));
  await tester.pumpAndSettle();
  return (app, tested);
}

String addressText(WidgetTester tester) => tester.widget<TextFormField>(find.byKey(const Key('address_field'))).controller!.text;

Future<void> typeAddress(WidgetTester tester, String text) async {
  await tester.enterText(find.byKey(const Key('address_field')), text);
  await tester.pump();
}

void main() {
  testWidgets('adresse par défaut : http://127.0.0.1:8000', (tester) async {
    await openSettings(tester);
    expect(find.text('Paramètres'), findsWidgets);
    expect(find.text('Adresse du serveur'), findsOneWidget);
    expect(addressText(tester), 'http://127.0.0.1:8000');
  });

  testWidgets('l\'adresse enregistrée est relue', (tester) async {
    await openSettings(tester, prefs: {'base_url': 'http://192.168.1.20:8000'});
    expect(addressText(tester), 'http://192.168.1.20:8000');
  });

  testWidgets('enregistrer : adresse nettoyée, sauvegardée sur le PC, confirmation affichée', (tester) async {
    final (app, _) = await openSettings(tester);
    await typeAddress(tester, '  192.168.1.20:8000/ ');
    await tester.tap(find.byKey(const Key('save_settings')));
    await tester.pumpAndSettle();

    expect(app.prefs.getString('base_url'), 'http://192.168.1.20:8000');
    expect(addressText(tester), 'http://192.168.1.20:8000');
    expect(find.text('Paramètres enregistrés.'), findsOneWidget);
    expect(containerOf(tester).read(baseUrlProvider), 'http://192.168.1.20:8000');
  });

  testWidgets('adresse invalide : erreur, rien d\'enregistré', (tester) async {
    final (app, tested) = await openSettings(tester);
    for (final bad in ['', 'ftp://serveur', 'http://', 'http://a b']) {
      await typeAddress(tester, bad);
      await tester.tap(find.byKey(const Key('save_settings')));
      await tester.pumpAndSettle();
      expect(find.text('Adresse invalide. Exemple : http://127.0.0.1:8000'), findsOneWidget, reason: bad);
      await tester.tap(find.byKey(const Key('test_connection')));
      await tester.pumpAndSettle();
    }
    expect(app.prefs.getString('base_url'), isNull);
    expect(tested, isEmpty); // on ne teste pas une adresse invalide
  });

  group('tester la connexion', () {
    for (final (status, text) in [
      (ConnectionStatus.ok, 'Connexion réussie.'),
      (ConnectionStatus.notEdebou, 'Un serveur répond, mais ce n\'est pas Edebou.'),
      (ConnectionStatus.unreachable, 'Serveur injoignable. Vérifiez l\'adresse et que le serveur est démarré.'),
      (ConnectionStatus.timeout, 'Le serveur ne répond pas (délai dépassé).'),
    ]) {
      testWidgets('résultat ${status.name}', (tester) async {
        await openSettings(tester, result: status);
        await tester.tap(find.byKey(const Key('test_connection')));
        await tester.pumpAndSettle();
        expect(find.byKey(Key('connection_result_${status.name}')), findsOneWidget);
        expect(find.text(text), findsOneWidget);
      });
    }

    testWidgets('teste l\'adresse saisie, sans l\'enregistrer', (tester) async {
      final (app, tested) = await openSettings(tester);
      await typeAddress(tester, 'depot-pc:8000');
      await tester.tap(find.byKey(const Key('test_connection')));
      await tester.pumpAndSettle();
      expect(tested, ['http://depot-pc:8000']);
      expect(app.prefs.getString('base_url'), isNull);
    });

    testWidgets('le résultat disparaît quand on modifie l\'adresse', (tester) async {
      await openSettings(tester);
      await tester.tap(find.byKey(const Key('test_connection')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('connection_result_ok')), findsOneWidget);
      await typeAddress(tester, 'http://127.0.0.1:9000');
      expect(find.byKey(const Key('connection_result_ok')), findsNothing);
    });

    testWidgets('test réel (sans simulation du testeur) : serveur Edebou reconnu via /api/auth/me/', (tester) async {
      final adapter = FakeAdapter((_) => jsonResponse(401, {'detail': 'Informations d\'authentification non fournies.'}));
      final app = await AppHarness.pump(tester, adapter: adapter);
      // Le testeur par défaut crée son propre client réseau : on vérifie ici la logique de probe sur le faux réseau.
      final status = await tester.runAsync(
        () => ApiClient(baseUrl: 'http://x:1', dio: Dio()..httpClientAdapter = adapter).probe(),
      );
      expect(status, ConnectionStatus.ok);
      expect(app.adapter.requestsTo('/api/auth/me/'), hasLength(1));
    });
  });

  testWidgets('la nouvelle adresse est utilisée pour la connexion suivante', (tester) async {
    final adapter = FakeAdapter((o) {
      if (o.path == '/api/auth/login/') return loginOk();
      return notAuthenticated();
    });
    final (app, _) = await openSettings(tester, adapter: adapter);
    await typeAddress(tester, 'http://192.168.1.50:8123');
    await tester.tap(find.byKey(const Key('save_settings')));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('name_field')), 'Papa');
    for (final d in '2468'.split('')) {
      await tester.tap(find.byKey(Key('pin_key_$d')));
    }
    await tester.pump();
    await tester.ensureVisible(find.byKey(const Key('login_button')));
    await tester.tap(find.byKey(const Key('login_button')));
    await tester.pumpAndSettle();

    final req = app.adapter.requestsTo('/api/auth/login/').single;
    expect(req.uri.host, '192.168.1.50');
    expect(req.uri.port, 8123);
    expect(jsonDecode(req.data as String)['name'], 'Papa');
  });

  testWidgets('changement de langue depuis les Paramètres : arabe, droite-à-gauche, enregistré', (tester) async {
    final (app, _) = await openSettings(tester);
    expect(Directionality.of(tester.element(find.byKey(const Key('save_settings')))), TextDirection.ltr);
    await tester.tap(find.text('العربية'));
    await tester.pumpAndSettle();
    expect(find.text('عنوان الخادم'), findsOneWidget);
    expect(Directionality.of(tester.element(find.byKey(const Key('save_settings')))), TextDirection.rtl);
    expect(app.prefs.getString('language'), 'ar');
  });

  testWidgets('en arabe l\'adresse web reste lisible de gauche à droite', (tester) async {
    await openSettings(tester, prefs: {'language': 'ar'});
    final editable = tester.widget<EditableText>(
        find.descendant(of: find.byKey(const Key('address_field')), matching: find.byType(EditableText)));
    expect(editable.textDirection, TextDirection.ltr);
    expect(find.text('عنوان الخادم'), findsOneWidget);
  });

  testWidgets('les Paramètres sont accessibles aussi après connexion (depuis l\'accueil)', (tester) async {
    await AppHarness.pump(tester, adapter: FakeAdapter((_) => meOk()), prefs: {'token': 'abc'});
    await tester.tap(find.byKey(const Key('home_settings')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('address_field')), findsOneWidget);
  });
}
