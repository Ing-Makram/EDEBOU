import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';
import '../data/auth_repository.dart';
import '../domain/session.dart';

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => AuthRepository(ref.watch(apiClientProvider), ref.watch(localStoreProvider)),
);

enum SessionNotice { none, expired }

/// Message à afficher sur l'écran de connexion (ex. « Votre session a expiré »).
class SessionNoticeNotifier extends Notifier<SessionNotice> {
  @override
  SessionNotice build() => SessionNotice.none;

  void set(SessionNotice value) => state = value;
}

final sessionNoticeProvider = NotifierProvider<SessionNoticeNotifier, SessionNotice>(SessionNoticeNotifier.new);

/// État de la session : en chargement (restauration), connecté (`Session`), déconnecté (`null`),
/// ou erreur (serveur injoignable au démarrage → l'écran propose de réessayer).
class AuthController extends AsyncNotifier<Session?> {
  @override
  Future<Session?> build() {
    // Un 401 sur une requête authentifiée = jeton mort : on ferme la session.
    ref.listen(unauthorizedSignalProvider, (_, _) => _expire());
    return ref.read(authRepositoryProvider).restore();
  }

  /// Les erreurs (`ApiError`) remontent à l'écran de connexion, qui les affiche.
  Future<void> login(String name, String pin) async {
    final session = await ref.read(authRepositoryProvider).login(name, pin);
    ref.read(sessionNoticeProvider.notifier).set(SessionNotice.none);
    state = AsyncData(session);
  }

  Future<void> logout() async {
    await ref.read(authRepositoryProvider).logout();
    ref.read(sessionNoticeProvider.notifier).set(SessionNotice.none);
    state = const AsyncData(null);
  }

  Future<void> _expire() async {
    if (state.value == null) return; // pas de session ouverte (ex. mauvais PIN à la connexion)
    await ref.read(authRepositoryProvider).forgetToken();
    ref.read(sessionNoticeProvider.notifier).set(SessionNotice.expired);
    state = const AsyncData(null);
  }
}

final authControllerProvider = AsyncNotifierProvider<AuthController, Session?>(AuthController.new);
