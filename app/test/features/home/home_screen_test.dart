import 'package:edebou/features/auth/domain/session.dart';
import 'package:edebou/features/home/presentation/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/app_harness.dart';
import '../../helpers/fake_adapter.dart';

Future<void> openHome(WidgetTester tester, String role, {String language = 'fr', String name = 'Test'}) async {
  await AppHarness.pump(
    tester,
    adapter: FakeAdapter((_) => meOk(name: name, role: role)),
    prefs: {'token': 'abc', 'language': language},
  );
}

void main() {
  group('modules affichés selon le rôle (docs/api.md « Rôles et accès »)', () {
    test('modulesForRole', () {
      expect(modulesForRole(UserRole.manager), HomeModule.values);
      expect(modulesForRole(UserRole.cashier), HomeModule.values);
      expect(modulesForRole(UserRole.delivery), [HomeModule.stock]);
    });

    testWidgets('gérant : Caisse, Clients, Consignes, Stock', (tester) async {
      await openHome(tester, 'manager', name: 'Papa');
      for (final m in ['cashRegister', 'clients', 'consignments', 'stock']) {
        expect(find.byKey(Key('module_$m')), findsOneWidget, reason: m);
      }
      expect(find.text('Caisse'), findsOneWidget);
      expect(find.text('Clients'), findsOneWidget);
      expect(find.text('Consignes'), findsOneWidget);
      expect(find.text('Stock'), findsOneWidget);
      expect(find.text('Gérant'), findsOneWidget);
    });

    testWidgets('caissier : les quatre modules', (tester) async {
      await openHome(tester, 'cashier');
      expect(find.byKey(const Key('module_cashRegister')), findsOneWidget);
      expect(find.byKey(const Key('module_stock')), findsOneWidget);
      expect(find.text('Caissier'), findsOneWidget);
    });

    testWidgets('livreur : seulement le Stock (lecture)', (tester) async {
      await openHome(tester, 'delivery');
      expect(find.byKey(const Key('module_stock')), findsOneWidget);
      for (final m in ['cashRegister', 'clients', 'consignments']) {
        expect(find.byKey(Key('module_$m')), findsNothing, reason: m);
      }
      expect(find.text('Livreur'), findsOneWidget);
    });
  });

  group('navigation', () {
    testWidgets('chaque module s\'ouvre sur un écran provisoire avec retour', (tester) async {
      await openHome(tester, 'manager');
      for (final entry in {'cashRegister': 'Caisse', 'clients': 'Clients', 'consignments': 'Consignes', 'stock': 'Stock'}.entries) {
        await tester.tap(find.byKey(Key('module_${entry.key}')));
        await tester.pumpAndSettle();
        expect(find.text('Bientôt disponible'), findsOneWidget, reason: entry.key);
        expect(find.descendant(of: find.byType(AppBar), matching: find.text(entry.value)), findsOneWidget);
        await tester.tap(find.byType(BackButton));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('welcome')), findsOneWidget);
      }
    });

    testWidgets('le bouton Paramètres de l\'accueil ouvre les Paramètres', (tester) async {
      await openHome(tester, 'manager');
      await tester.tap(find.byKey(const Key('home_settings')));
      await tester.pumpAndSettle();
      expect(find.text('Adresse du serveur'), findsOneWidget);
    });
  });

  group('accessibilité', () {
    testWidgets('les tuiles de module sont grandes (≥ 200 × 150)', (tester) async {
      await openHome(tester, 'manager');
      for (final m in ['cashRegister', 'clients', 'consignments', 'stock']) {
        final size = tester.getSize(find.byKey(Key('module_$m')));
        expect(size.width, greaterThanOrEqualTo(200), reason: m);
        expect(size.height, greaterThanOrEqualTo(150), reason: m);
      }
    });

    testWidgets('les boutons de la barre (réglages, déconnexion) sont des zones tactiles ≥ 48 px', (tester) async {
      await openHome(tester, 'manager');
      for (final k in ['home_settings', 'home_logout']) {
        final size = tester.getSize(find.byKey(Key(k)));
        expect(size.shortestSide, greaterThanOrEqualTo(48), reason: k);
      }
    });

    testWidgets('le bouton de connexion et le clavier PIN ont une hauteur ≥ 56 px', (tester) async {
      await AppHarness.pump(tester, adapter: FakeAdapter((_) => notAuthenticated()));
      expect(tester.getSize(find.byKey(const Key('login_button'))).height, greaterThanOrEqualTo(56));
      expect(tester.getSize(find.byKey(const Key('pin_key_5'))).height, greaterThanOrEqualTo(56));
    });
  });

  group('arabe', () {
    testWidgets('accueil en arabe : textes traduits et tuiles dans l\'ordre inversé', (tester) async {
      await openHome(tester, 'manager', language: 'ar', name: 'بابا');
      expect(Directionality.of(tester.element(find.byKey(const Key('welcome')))), TextDirection.rtl);
      expect(find.text('مرحبًا، بابا'), findsOneWidget);
      expect(find.text('المدير'), findsOneWidget);
      expect(find.text('الصندوق'), findsOneWidget);
      expect(find.text('الحرفاء'), findsOneWidget);
      expect(find.text('المخزون'), findsOneWidget);
      expect(find.text('Caisse'), findsNothing);

      // 1re tuile (Caisse) à droite, dernière (Stock) à gauche — le Wrap suit la direction.
      final cash = tester.getCenter(find.byKey(const Key('module_cashRegister'))).dx;
      final stock = tester.getCenter(find.byKey(const Key('module_stock'))).dx;
      expect(cash, greaterThan(stock));
    });

    testWidgets('en français la première tuile est à gauche (contre-épreuve)', (tester) async {
      await openHome(tester, 'manager');
      final cash = tester.getCenter(find.byKey(const Key('module_cashRegister'))).dx;
      final stock = tester.getCenter(find.byKey(const Key('module_stock'))).dx;
      expect(cash, lessThan(stock));
    });

    testWidgets('la barre d\'application est inversée : réglages et déconnexion passent à gauche', (tester) async {
      await openHome(tester, 'manager');
      final frSettings = tester.getCenter(find.byKey(const Key('home_settings'))).dx;
      expect(frSettings, greaterThan(tester.view.physicalSize.width / 2));

      await openHome(tester, 'manager', language: 'ar');
      final arSettings = tester.getCenter(find.byKey(const Key('home_settings'))).dx;
      expect(arSettings, lessThan(tester.view.physicalSize.width / 2));
    });

    testWidgets('l\'écran provisoire d\'un module est traduit', (tester) async {
      await openHome(tester, 'manager', language: 'ar');
      await tester.tap(find.byKey(const Key('module_stock')));
      await tester.pumpAndSettle();
      expect(find.text('قريبًا'), findsOneWidget);
    });
  });
}
