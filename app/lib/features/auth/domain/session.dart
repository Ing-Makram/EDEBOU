/// Rôles du serveur (docs/api.md). Le serveur reste seul juge des droits ; l'app s'en sert pour
/// montrer ou cacher des boutons.
enum UserRole {
  manager('manager'),
  cashier('cashier'),
  delivery('delivery');

  const UserRole(this.wire);

  final String wire;

  static UserRole? tryParse(Object? value) {
    for (final r in values) {
      if (r.wire == value) return r;
    }
    return null;
  }
}

/// Utilisateur connecté, tel que renvoyé par `/api/auth/login/` et `/api/auth/me/`.
class Session {
  const Session({required this.name, required this.role});

  final String name;
  final UserRole role;

  @override
  bool operator ==(Object other) => other is Session && other.name == name && other.role == role;

  @override
  int get hashCode => Object.hash(name, role);

  @override
  String toString() => 'Session($name, ${role.wire})';
}
