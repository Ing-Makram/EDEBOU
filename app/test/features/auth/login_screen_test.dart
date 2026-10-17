import 'dart:convert';

import 'package:dio/dio.dart';

import 'package:edebou/core/providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/app_harness.dart';
import '../../helpers/fake_adapter.dart';

/// Serveur factice : connexion acceptée pour Papa/2468 (comme docs/api.md), le reste refusé.
ResponseBody loginServer(RequestOptions o) {
  if (o.path == '/api/auth/login/') {
    final body = jsonDecode(o.data as String) as Map;
    return body['name'] == 'Papa' && body['pin'] == '2468' ? loginOk() : wrongCredentials();
  }
  if (o.path == '/api/auth/logout/') return jsonResponse(204);
  return jsonResponse(404, {'detail': 'x'});
}

Future<void> tapPin(WidgetTester tester, String digits) async {
  for (final d in digits.split('')) {
    await tester.tap(find.byKey(Key('pin_key_$d')));
    await tester.pump();
  }
}

Future<void> fillName(WidgetTester tester, String name) async {
  await tester.enterText(find.byKey(const Key('name_field')), name);
  await tester.pump();
}

Future<void> submit(WidgetTester tester) async {
  await tester.ensureVisible(find.byKey(const Key('login_button')));
  await tester.tap(find.byKey(const Key('login_button')));
  await tester.pumpAndSettle();
}

String pinText(WidgetTester tester) => tester.widget<EditableText>(find.descendant(
      of: find.byKey(const Key('pin_field')),
      matching: find.byType(EditableText),
    )).controller.text;

void main() {
  group('écran de connexion', () {
    testWidgets('affiche le formulaire en français par défaut', (tester) async {
      await AppHarness.pump(tester, adapter: FakeAdapter(loginServer));
      expect(find.text('Connexion'), findsOneWidget);
      expect(find.text('Se connecter'), findsOneWidget);
      expect(find.text('Nom'), findsOneWidget);
      expect(find.text('Code PIN'), findsOneWidget);
      expect(find.byKey(const Key('language_switcher')), findsOneWidget);
      expect(find.byKey(const Key('open_settings')), findsOneWidget);
      expect(Directionality.of(tester.element(find.byKey(const Key('login_button')))), TextDirection.ltr);
    });

    testWidgets('connexion réussie : jeton enregistré, accueil du rôle affiché', (tester) async {
      final app = await AppHarness.pump(tester, adapter: FakeAdapter(loginServer));
      await fillName(tester, '  Papa ');
      await tapPin(tester, '2468');
      await submit(tester);

      expect(find.byKey(const Key('welcome')), findsOneWidget);
      expect(find.text('Bonjour, Papa'), findsOneWidget);
      expect(find.text('Gérant'), findsOneWidget);
      expect(find.byKey(const Key('login_button')), findsNothing);

      final req = app.adapter.requestsTo('/api/auth/login/').single;
      expect(jsonDecode(req.data as String), {'name': 'Papa', 'pin': '2468'}); // nom nettoyé des espaces
      expect(req.headers.containsKey('Authorization'), isFalse);
      expect(app.prefs.getString('token'), 'tok123');
      expect(app.prefs.getString('last_user_name'), 'Papa');
    });

    testWidgets('le dernier nom saisi est pré-rempli', (tester) async {
      await AppHarness.pump(tester, adapter: FakeAdapter(loginServer), prefs: {'last_user_name': 'Sami'});
      expect(tester.widget<TextFormField>(find.byKey(const Key('name_field'))).controller!.text, 'Sami');
    });

    testWidgets('mauvais nom ou PIN : message, on reste sur l\'écran, PIN effacé, pas de jeton', (tester) async {
      final app = await AppHarness.pump(tester, adapter: FakeAdapter(loginServer));
      await fillName(tester, 'Papa');
      await tapPin(tester, '9999');
      await submit(tester);

      expect(find.byKey(const Key('login_error')), findsOneWidget);
      expect(find.text('Nom ou code PIN incorrect.'), findsOneWidget);
      expect(find.byKey(const Key('login_button')), findsOneWidget);
      expect(find.byKey(const Key('welcome')), findsNothing);
      expect(pinText(tester), '');
      expect(app.prefs.getString('token'), isNull);
      expect(find.byKey(const Key('session_expired')), findsNothing); // un mauvais PIN n'est pas une session expirée
    });

    testWidgets('PIN trop court : erreur de format, aucune requête envoyée', (tester) async {
      final app = await AppHarness.pump(tester, adapter: FakeAdapter(loginServer));
      await fillName(tester, 'Papa');
      await tapPin(tester, '123');
      await submit(tester);
      expect(find.text('Le code PIN contient 4 à 6 chiffres.'), findsOneWidget);
      expect(app.adapter.requests, isEmpty);
    });

    testWidgets('nom vide : erreur, aucune requête envoyée', (tester) async {
      final app = await AppHarness.pump(tester, adapter: FakeAdapter(loginServer));
      await tapPin(tester, '2468');
      await submit(tester);
      expect(find.text('Entrez votre nom.'), findsOneWidget);
      expect(app.adapter.requests, isEmpty);
    });

    testWidgets('serveur injoignable : message clair + accès direct aux Paramètres', (tester) async {
      await AppHarness.pump(tester, adapter: FakeAdapter((o) => throw connectionError(o)));
      await fillName(tester, 'Papa');
      await tapPin(tester, '2468');
      await submit(tester);
      expect(find.text('Impossible de joindre le serveur.'), findsOneWidget);
      await tester.ensureVisible(find.byKey(const Key('error_open_settings')));
      await tester.tap(find.byKey(const Key('error_open_settings')));
      await tester.pumpAndSettle();
      expect(find.text('Adresse du serveur'), findsOneWidget);
    });

    testWidgets('délai dépassé, trop d\'essais (429) et erreur serveur (500)', (tester) async {
      final adapter = FakeAdapter((o) => throw timeoutError(o));
      await AppHarness.pump(tester, adapter: adapter);
      await fillName(tester, 'Papa');
      await tapPin(tester, '2468');
      await submit(tester);
      expect(find.text('Le serveur met trop de temps à répondre.'), findsOneWidget);

      adapter.handler = (_) => jsonResponse(429, {'detail': 'limité'});
      await tapPin(tester, '2468');
      await submit(tester);
      expect(find.text('Trop d\'essais. Patientez une minute.'), findsOneWidget);

      adapter.handler = (_) => jsonResponse(500, {'detail': 'boom'});
      await tapPin(tester, '2468');
      await submit(tester);
      expect(find.text('Erreur du serveur. Réessayez.'), findsOneWidget);
    });

    testWidgets('rôle inconnu renvoyé par le serveur : erreur générique, pas de plantage', (tester) async {
      final app = await AppHarness.pump(
        tester,
        adapter: FakeAdapter((o) => jsonResponse(200, {'token': 't', 'name': 'X', 'role': 'astronaut'})),
      );
      await fillName(tester, 'X');
      await tapPin(tester, '1234');
      await submit(tester);
      expect(find.text('Une erreur est survenue.'), findsOneWidget);
      expect(app.prefs.getString('token'), isNull);
    });

    testWidgets('le bouton est désactivé pendant la requête (pas de double envoi)', (tester) async {
      final app = await AppHarness.pump(tester, adapter: FakeAdapter(loginServer));
      await fillName(tester, 'Papa');
      await tapPin(tester, '2468');
      await tester.ensureVisible(find.byKey(const Key('login_button')));
      await tester.tap(find.byKey(const Key('login_button')));
      await tester.tap(find.byKey(const Key('login_button')), warnIfMissed: false); // second clic immédiat
      await tester.pumpAndSettle();
      expect(app.adapter.requestsTo('/api/auth/login/'), hasLength(1));
    });
  });

  group('clavier PIN', () {
    testWidgets('chiffres, effacer un chiffre, tout effacer, 6 chiffres maximum', (tester) async {
      await AppHarness.pump(tester, adapter: FakeAdapter(loginServer));
      await tapPin(tester, '12');
      expect(pinText(tester), '12');
      await tester.tap(find.byKey(const Key('pin_backspace')));
      await tester.pump();
      expect(pinText(tester), '1');
      await tapPin(tester, '23456789');
      expect(pinText(tester), '123456');
      await tester.tap(find.byKey(const Key('pin_clear')));
      await tester.pump();
      expect(pinText(tester), '');
    });

    testWidgets('le champ PIN est masqué et n\'accepte que des chiffres au clavier', (tester) async {
      await AppHarness.pump(tester, adapter: FakeAdapter(loginServer));
      expect(tester.widget<EditableText>(find.descendant(
        of: find.byKey(const Key('pin_field')),
        matching: find.byType(EditableText),
      )).obscureText, isTrue);
      await tester.enterText(find.byKey(const Key('pin_field')), '12ab34cd5678');
      expect(pinText(tester), '123456');
    });

    testWidgets('on valide au clavier avec Entrée', (tester) async {
      final app = await AppHarness.pump(tester, adapter: FakeAdapter(loginServer));
      await fillName(tester, 'Papa');
      await tester.enterText(find.byKey(const Key('pin_field')), '2468');
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pumpAndSettle();
      expect(app.adapter.requestsTo('/api/auth/login/'), hasLength(1));
      expect(find.byKey(const Key('welcome')), findsOneWidget);
    });
  });

  group('arabe et droite-à-gauche', () {
    testWidgets('en arabe, l\'écran est vraiment inversé et traduit', (tester) async {
      await AppHarness.pump(tester, adapter: FakeAdapter(loginServer), prefs: {'language': 'ar'});

      // Direction du texte
      expect(Directionality.of(tester.element(find.byKey(const Key('login_button')))), TextDirection.rtl);
      // Textes arabes, plus de français
      expect(find.text('تسجيل الدخول'), findsOneWidget);
      expect(find.text('دخول'), findsOneWidget);
      expect(find.text('الاسم'), findsOneWidget);
      expect(find.text('الرمز السري'), findsOneWidget);
      expect(find.text('Se connecter'), findsNothing);
    });

    testWidgets('la mise en page est un miroir : sélecteur de langue à droite, réglages à gauche', (tester) async {
      Future<(double, double)> positions(String language) async {
        await AppHarness.pump(tester, adapter: FakeAdapter(loginServer), prefs: {'language': language});
        final switcher = tester.getCenter(find.byKey(const Key('language_switcher'))).dx;
        final settings = tester.getCenter(find.byKey(const Key('open_settings'))).dx;
        return (switcher, settings);
      }

      final (frSwitcher, frSettings) = await positions('fr');
      expect(frSwitcher, lessThan(frSettings), reason: 'en français : langue à gauche, réglages à droite');

      final (arSwitcher, arSettings) = await positions('ar');
      expect(arSwitcher, greaterThan(arSettings), reason: 'en arabe : langue à droite, réglages à gauche');
    });

    testWidgets('l\'alignement des libellés suit la direction (le champ Nom est aligné à droite en arabe)', (tester) async {
      await AppHarness.pump(tester, adapter: FakeAdapter(loginServer), prefs: {'language': 'ar', 'last_user_name': 'Sami'});
      final field = tester.getRect(find.byKey(const Key('name_field')));
      final typed = tester.getRect(find.descendant(of: find.byKey(const Key('name_field')), matching: find.byType(EditableText)));
      // Le texte saisi se place du côté « début » = la droite en RTL.
      expect(typed.right, greaterThan(field.center.dx));
    });

    testWidgets('le clavier numérique garde la disposition universelle 1-2-3 de gauche à droite', (tester) async {
      for (final language in ['fr', 'ar']) {
        await AppHarness.pump(tester, adapter: FakeAdapter(loginServer), prefs: {'language': language});
        final one = tester.getCenter(find.byKey(const Key('pin_key_1'))).dx;
        final three = tester.getCenter(find.byKey(const Key('pin_key_3'))).dx;
        expect(one, lessThan(three), reason: 'langue $language');
      }
    });

    testWidgets('changer de langue en direct : bascule fr → ar → fr et le choix est enregistré', (tester) async {
      final app = await AppHarness.pump(tester, adapter: FakeAdapter(loginServer));
      expect(find.text('Connexion'), findsOneWidget);

      await tester.tap(find.text('العربية'));
      await tester.pumpAndSettle();
      expect(find.text('تسجيل الدخول'), findsOneWidget);
      expect(Directionality.of(tester.element(find.byKey(const Key('login_button')))), TextDirection.rtl);
      expect(app.prefs.getString('language'), 'ar');

      await tester.tap(find.text('Français'));
      await tester.pumpAndSettle();
      expect(find.text('Connexion'), findsOneWidget);
      expect(Directionality.of(tester.element(find.byKey(const Key('login_button')))), TextDirection.ltr);
      expect(app.prefs.getString('language'), 'fr');
    });

    testWidgets('les erreurs sont aussi traduites en arabe', (tester) async {
      await AppHarness.pump(tester, adapter: FakeAdapter(loginServer), prefs: {'language': 'ar'});
      await fillName(tester, 'Papa');
      await tapPin(tester, '9999');
      await submit(tester);
      expect(find.text('الاسم أو الرمز السري غير صحيح.'), findsOneWidget);
    });

    testWidgets('la langue enregistrée est relue au démarrage', (tester) async {
      await AppHarness.pump(tester, adapter: FakeAdapter(loginServer), prefs: {'language': 'ar'});
      expect(containerOf(tester).read(localeProvider).languageCode, 'ar');
    });
  });
}
