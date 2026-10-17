import 'package:shared_preferences/shared_preferences.dart';

/// Réglages enregistrés sur le PC : adresse du serveur, langue, jeton de session, dernier nom saisi.
///
/// Le jeton est stocké ici en clair (fichier utilisateur) : la base SQLite du dépôt se trouve sur le même PC,
/// un coffre-fort n'ajouterait pas de protection réelle (voir docs/decisions.md).
class LocalStore {
  LocalStore(this._prefs);

  final SharedPreferences _prefs;

  static const defaultBaseUrl = 'http://127.0.0.1:8000';
  static const defaultLanguage = 'fr';

  static const _kBaseUrl = 'base_url';
  static const _kLanguage = 'language';
  static const _kToken = 'token';
  static const _kLastUser = 'last_user_name';

  String get baseUrl => _prefs.getString(_kBaseUrl) ?? defaultBaseUrl;
  Future<void> setBaseUrl(String value) => _prefs.setString(_kBaseUrl, value);

  String get language => _prefs.getString(_kLanguage) ?? defaultLanguage;
  Future<void> setLanguage(String code) => _prefs.setString(_kLanguage, code);

  String? get token => _prefs.getString(_kToken);
  Future<void> setToken(String value) => _prefs.setString(_kToken, value);
  Future<void> clearToken() => _prefs.remove(_kToken);

  String? get lastUserName => _prefs.getString(_kLastUser);
  Future<void> setLastUserName(String value) => _prefs.setString(_kLastUser, value);
}
