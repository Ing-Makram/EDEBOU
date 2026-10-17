import 'business_code.dart';

/// Erreurs typées de l'API (voir docs/api.md « Format des erreurs »). Aucun texte d'interface ici :
/// l'affichage traduit passe par `errorMessage()` (core/errors).
sealed class ApiError implements Exception {
  const ApiError();
}

/// Pas de réponse du serveur : réseau coupé, serveur arrêté, délai dépassé.
final class NetworkError extends ApiError {
  const NetworkError({this.timeout = false});

  final bool timeout;

  @override
  String toString() => 'NetworkError(timeout: $timeout)';
}

/// 401 : jeton absent/invalide, ou (à la connexion) nom ou PIN faux.
final class UnauthorizedError extends ApiError {
  const UnauthorizedError([this.detail]);

  final String? detail;

  @override
  String toString() => 'UnauthorizedError($detail)';
}

/// 403 : rôle non autorisé.
final class ForbiddenError extends ApiError {
  const ForbiddenError([this.detail]);

  final String? detail;

  @override
  String toString() => 'ForbiddenError($detail)';
}

/// 404.
final class NotFoundError extends ApiError {
  const NotFoundError([this.detail]);

  final String? detail;

  @override
  String toString() => 'NotFoundError($detail)';
}

/// 429 : trop de requêtes (connexion, changement de PIN).
final class ThrottledError extends ApiError {
  const ThrottledError([this.detail]);

  final String? detail;

  @override
  String toString() => 'ThrottledError($detail)';
}

/// 400 avec `code` : règle métier refusée par le serveur. Rien n'a été enregistré.
final class BusinessError extends ApiError {
  const BusinessError({required this.code, required this.rawCode, this.detail, this.context = const {}});

  final BusinessCode code;

  /// Code tel que reçu (utile quand `code == BusinessCode.unknown`).
  final String rawCode;

  /// Texte français du serveur : pour les journaux, jamais pour l'écran.
  final String? detail;

  /// Champs de contexte (`product`, `requested`, `available`, `debt`…).
  final Map<String, Object?> context;

  int? intContext(String key) {
    final v = context[key];
    return v is int ? v : null;
  }

  String? stringContext(String key) {
    final v = context[key];
    return v is String ? v : null;
  }

  @override
  String toString() => 'BusinessError($rawCode, $context)';
}

/// 400 sans `code` : erreurs de format par champ. Les clés sont aplaties : `units.0.prices.0.price`.
final class ValidationError extends ApiError {
  const ValidationError(this.fields);

  final Map<String, List<String>> fields;

  @override
  String toString() => 'ValidationError($fields)';
}

/// 5xx.
final class ServerError extends ApiError {
  const ServerError(this.status);

  final int status;

  @override
  String toString() => 'ServerError($status)';
}

/// Tout le reste (statut inattendu, corps illisible).
final class UnknownError extends ApiError {
  const UnknownError({this.status, this.cause});

  final int? status;
  final Object? cause;

  @override
  String toString() => 'UnknownError(status: $status, cause: $cause)';
}
