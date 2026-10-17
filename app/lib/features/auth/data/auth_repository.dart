import '../../../core/api/api_client.dart';
import '../../../core/api/api_error.dart';
import '../../../core/storage/local_store.dart';
import '../domain/session.dart';

/// Connexion, restauration de session et déconnexion (docs/api.md « Authentification »).
class AuthRepository {
  AuthRepository(this._api, this._store);

  final ApiClient _api;
  final LocalStore _store;

  String? get lastUserName => _store.lastUserName;

  /// 401 (`UnauthorizedError`) = nom ou PIN incorrect ; 429 (`ThrottledError`) = trop d'essais.
  Future<Session> login(String name, String pin) async {
    final data = await _api.post('/api/auth/login/', body: {'name': name, 'pin': pin}, authenticated: false);
    final session = _sessionFrom(data);
    final token = (data as Map)['token'];
    if (token is! String || token.isEmpty) throw UnknownError(cause: data);
    await _store.setToken(token);
    await _store.setLastUserName(name);
    return session;
  }

  /// Session enregistrée ? `null` si pas de jeton ou jeton refusé (401).
  /// Une erreur réseau est relancée : le jeton reste, l'app propose de réessayer.
  Future<Session?> restore() async {
    if (_store.token == null) return null;
    try {
      return _sessionFrom(await _api.get('/api/auth/me/'));
    } on UnauthorizedError {
      await _store.clearToken();
      return null;
    }
  }

  /// Ferme la session côté serveur si possible ; le jeton local est toujours effacé.
  Future<void> logout() async {
    try {
      await _api.post('/api/auth/logout/');
    } on ApiError {
      // serveur injoignable ou jeton déjà mort : on oublie quand même le jeton ici
    } finally {
      await _store.clearToken();
    }
  }

  Future<void> forgetToken() => _store.clearToken();

  /// `{name, role, ...}` de `/login/` ou `/me/`. Un rôle inconnu (serveur plus récent) est une erreur.
  static Session _sessionFrom(Object? data) {
    if (data is! Map) throw UnknownError(cause: data);
    final role = UserRole.tryParse(data['role']);
    final name = data['name'];
    if (role == null || name is! String) throw UnknownError(cause: data);
    return Session(name: name, role: role);
  }
}
