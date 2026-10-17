import 'package:dio/dio.dart';
import 'package:edebou/app.dart';
import 'package:edebou/core/api/api_client.dart';
import 'package:edebou/core/providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fake_adapter.dart';

/// Démarre toute l'application (vrai client HTTP, vrai dépôt, vraies écrans) avec un faux réseau
/// et des préférences en mémoire.
class AppHarness {
  AppHarness._(this.adapter, this.prefs);

  final FakeAdapter adapter;
  final SharedPreferences prefs;

  static Future<AppHarness> pump(
    WidgetTester tester, {
    required FakeAdapter adapter,
    Map<String, Object> prefs = const {},
    List<Override> overrides = const [],
    Size size = const Size(1280, 1000),
  }) async {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    SharedPreferences.setMockInitialValues(prefs);
    final sp = await SharedPreferences.getInstance();
    await tester.pumpWidget(
      ProviderScope(
        retry: (_, _) => null,
        overrides: [
          sharedPreferencesProvider.overrideWithValue(sp),
          apiClientProvider.overrideWith((ref) {
            final store = ref.watch(localStoreProvider);
            return ApiClient(
              baseUrl: ref.watch(baseUrlProvider),
              tokenReader: () => store.token,
              onUnauthorized: () => ref.read(unauthorizedSignalProvider.notifier).fire(),
              dio: Dio()..httpClientAdapter = adapter,
            );
          }),
          ...overrides,
        ],
        child: const EdebouApp(),
      ),
    );
    await tester.pumpAndSettle();
    return AppHarness._(adapter, sp);
  }
}

ProviderContainer containerOf(WidgetTester tester) => ProviderScope.containerOf(tester.element(find.byType(EdebouApp)));

/// Réponses types du serveur (docs/api.md).
ResponseBody loginOk({String name = 'Papa', String role = 'manager', String token = 'tok123'}) =>
    jsonResponse(200, {'token': token, 'name': name, 'role': role});

ResponseBody meOk({String name = 'Papa', String role = 'manager'}) =>
    jsonResponse(200, {'id': 1, 'name': name, 'role': role});

ResponseBody notAuthenticated() => jsonResponse(401, {'detail': 'Token non valide.'});

ResponseBody wrongCredentials() => jsonResponse(401, {'detail': 'Nom ou PIN incorrect.'});
