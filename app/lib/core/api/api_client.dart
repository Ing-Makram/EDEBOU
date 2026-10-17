import 'dart:convert';

import 'package:dio/dio.dart';

import 'api_error.dart';
import 'business_code.dart';

typedef TokenReader = String? Function();

/// Résultat du test de connexion de l'écran Paramètres.
enum ConnectionStatus { ok, notEdebou, unreachable, timeout }

/// Client HTTP unique de l'application. Il envoie les requêtes, ajoute le jeton et traduit les erreurs
/// de docs/api.md en erreurs typées (`ApiError`). **Aucune logique métier** : prix, totaux, stock, dettes
/// et consignes sont calculés par le serveur.
class ApiClient {
  ApiClient({
    required String baseUrl,
    this._tokenReader,
    this._onUnauthorized,
    Dio? dio,
  }) : _dio = dio ?? Dio() {
    _dio.options
      ..baseUrl = baseUrl
      ..connectTimeout = const Duration(seconds: 5)
      ..sendTimeout = const Duration(seconds: 20)
      ..receiveTimeout = const Duration(seconds: 20)
      ..responseType = ResponseType.plain; // on décode nous-mêmes : un corps non JSON ne doit pas planter
  }

  final Dio _dio;
  final TokenReader? _tokenReader;
  final void Function()? _onUnauthorized;

  String get baseUrl => _dio.options.baseUrl;

  /// Les trois méthodes renvoient le JSON décodé (`Map`, `List`) ou `null` (corps vide, ex. 204).
  /// `authenticated: false` : pas de jeton, et un 401 n'est pas une session expirée (ex. mauvais PIN).
  Future<Object?> get(String path, {Map<String, Object?>? query, bool authenticated = true}) =>
      _send('GET', path, query: query, authenticated: authenticated);

  Future<Object?> post(String path, {Object? body, bool authenticated = true}) =>
      _send('POST', path, body: body, authenticated: authenticated);

  Future<Object?> patch(String path, {Object? body, bool authenticated = true}) =>
      _send('PATCH', path, body: body, authenticated: authenticated);

  /// Le serveur répond-il, et est-ce Edebou ? Sans jeton, un serveur Edebou répond toujours 401 avec
  /// `{"detail": ...}` ; une réponse 2xx ou un autre statut vient d'un autre logiciel.
  Future<ConnectionStatus> probe() async {
    try {
      await get('/api/auth/me/', authenticated: false);
      return ConnectionStatus.notEdebou;
    } on UnauthorizedError catch (e) {
      return e.detail != null ? ConnectionStatus.ok : ConnectionStatus.notEdebou;
    } on NetworkError catch (e) {
      return e.timeout ? ConnectionStatus.timeout : ConnectionStatus.unreachable;
    } on ApiError {
      return ConnectionStatus.notEdebou;
    }
  }

  Future<Object?> _send(
    String method,
    String path, {
    Object? body,
    Map<String, Object?>? query,
    required bool authenticated,
  }) async {
    final token = authenticated ? _tokenReader?.call() : null;
    final Response<String> response;
    try {
      response = await _dio.request<String>(
        path,
        data: body == null ? null : jsonEncode(body),
        queryParameters: query,
        options: Options(
          method: method,
          headers: {
            'Accept': 'application/json',
            if (body != null) 'Content-Type': 'application/json',
            if (token != null) 'Authorization': 'Token $token',
          },
          validateStatus: (_) => true, // les statuts d'erreur sont traduits ci-dessous
        ),
      );
    } on DioException catch (e) {
      throw _mapTransportError(e);
    }

    final status = response.statusCode ?? 0;
    final decoded = _decode(response.data);
    if (status >= 200 && status < 300) return decoded;

    final error = mapErrorResponse(status, decoded);
    if (error is UnauthorizedError && authenticated) _onUnauthorized?.call();
    throw error;
  }

  static Object? _decode(String? raw) {
    if (raw == null || raw.trim().isEmpty) return null;
    try {
      return jsonDecode(raw);
    } on FormatException {
      return null; // page HTML d'erreur, etc.
    }
  }

  static ApiError _mapTransportError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.transformTimeout:
        return const NetworkError(timeout: true);
      case DioExceptionType.connectionError:
      case DioExceptionType.badCertificate:
      case DioExceptionType.unknown:
        return const NetworkError();
      case DioExceptionType.badResponse:
      case DioExceptionType.cancel:
        return UnknownError(cause: e);
    }
  }

  /// Traduction statut + corps → erreur typée. Publique pour les tests.
  static ApiError mapErrorResponse(int status, Object? body) {
    final detail = body is Map && body['detail'] is String ? body['detail'] as String : null;
    switch (status) {
      case 400:
        if (body is Map && body['code'] is String) {
          final raw = body['code'] as String;
          final context = {
            for (final e in body.entries)
              if (e.key != 'code' && e.key != 'detail') e.key as String: e.value as Object?,
          };
          return BusinessError(code: BusinessCode.fromWire(raw), rawCode: raw, detail: detail, context: context);
        }
        if (body is Map) return ValidationError(_flattenFieldErrors(body));
        return UnknownError(status: status);
      case 401:
        return UnauthorizedError(detail);
      case 403:
        return ForbiddenError(detail);
      case 404:
        return NotFoundError(detail);
      case 429:
        return ThrottledError(detail);
      default:
        return status >= 500 ? ServerError(status) : UnknownError(status: status);
    }
  }

  /// `{"units": {"0": {"prices": {"0": {"price": ["msg"]}}}}}` → `{"units.0.prices.0.price": ["msg"]}`.
  static Map<String, List<String>> _flattenFieldErrors(Object? node, [String prefix = '']) {
    final out = <String, List<String>>{};
    void walk(Object? value, String path) {
      if (value is Map) {
        value.forEach((k, v) => walk(v, path.isEmpty ? '$k' : '$path.$k'));
      } else if (value is List) {
        if (value.isNotEmpty && value.every((v) => v is String)) {
          out[path] = value.cast<String>();
        } else {
          for (var i = 0; i < value.length; i++) {
            walk(value[i], path.isEmpty ? '$i' : '$path.$i');
          }
        }
      } else if (value is String) {
        out[path] = [value];
      }
    }

    walk(node, prefix);
    return out;
  }
}
