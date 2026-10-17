final _hostPattern = RegExp(r'^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?|[0-9A-Fa-f:]+)$'); // nom, IPv4 ou IPv6

/// Nettoie et valide l'adresse du serveur saisie par l'utilisateur.
/// Renvoie l'adresse normalisée (sans « / » final), ou `null` si elle est inutilisable.
///
/// Accepté : `http://127.0.0.1:8000`, `https://depot.local`, `192.168.1.20:8000` (http ajouté).
String? normalizeBaseUrl(String input) {
  var text = input.trim();
  if (text.isEmpty) return null;
  if (!text.contains('://')) text = 'http://$text';
  final uri = Uri.tryParse(text);
  if (uri == null) return null;
  final okScheme = uri.scheme == 'http' || uri.scheme == 'https';
  if (!okScheme || !_hostPattern.hasMatch(uri.host) || uri.hasQuery || uri.hasFragment || uri.userInfo.isNotEmpty) return null;
  var out = uri.toString();
  while (out.endsWith('/')) {
    out = out.substring(0, out.length - 1);
  }
  return out;
}
