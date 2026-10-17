import 'dart:ui';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api/api_client.dart';
import 'storage/local_store.dart';

/// Fourni au démarrage (`main`) et dans les tests : `SharedPreferences` s'ouvre de façon asynchrone.
final sharedPreferencesProvider = Provider<SharedPreferences>(
  (ref) => throw UnimplementedError('sharedPreferencesProvider doit être surchargé'),
);

final localStoreProvider = Provider<LocalStore>((ref) => LocalStore(ref.watch(sharedPreferencesProvider)));

/// Adresse du serveur, enregistrée sur le PC.
class BaseUrlNotifier extends Notifier<String> {
  @override
  String build() => ref.watch(localStoreProvider).baseUrl;

  Future<void> save(String url) async {
    await ref.read(localStoreProvider).setBaseUrl(url);
    state = url;
  }
}

final baseUrlProvider = NotifierProvider<BaseUrlNotifier, String>(BaseUrlNotifier.new);

/// Langue de l'interface (`fr` ou `ar`), enregistrée sur le PC. L'arabe passe l'interface en droite-à-gauche.
class LocaleNotifier extends Notifier<Locale> {
  @override
  Locale build() => Locale(ref.watch(localStoreProvider).language);

  Future<void> setLanguage(String code) async {
    await ref.read(localStoreProvider).setLanguage(code);
    state = Locale(code);
  }
}

final localeProvider = NotifierProvider<LocaleNotifier, Locale>(LocaleNotifier.new);

/// Incrémenté quand le serveur répond 401 à une requête authentifiée (jeton mort).
/// La couche auth l'écoute pour fermer la session ; le client HTTP n'a pas besoin de la connaître.
class UnauthorizedSignal extends Notifier<int> {
  @override
  int build() => 0;

  void fire() => state++;
}

final unauthorizedSignalProvider = NotifierProvider<UnauthorizedSignal, int>(UnauthorizedSignal.new);

/// Un client par adresse de serveur : changer l'adresse dans les Paramètres en crée un nouveau.
final apiClientProvider = Provider<ApiClient>((ref) {
  final store = ref.watch(localStoreProvider);
  return ApiClient(
    baseUrl: ref.watch(baseUrlProvider),
    tokenReader: () => store.token,
    onUnauthorized: () => ref.read(unauthorizedSignalProvider.notifier).fire(),
  );
});
