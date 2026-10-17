import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/error_messages.dart';
import '../../../l10n/app_localizations.dart';
import '../../home/presentation/home_screen.dart';
import '../../settings/presentation/settings_screen.dart';
import '../application/auth_controller.dart';
import 'login_screen.dart';

/// Choisit l'écran selon la session : restauration, connexion, ou accueil du rôle.
class AuthGate extends ConsumerWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authControllerProvider);
    return auth.when(
      loading: () => const _RestoringScreen(),
      error: (error, _) => _RestoreErrorScreen(error: error),
      data: (session) => session == null ? const LoginScreen() : HomeScreen(session: session),
    );
  }
}

class _RestoringScreen extends StatelessWidget {
  const _RestoringScreen();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(strokeWidth: 5),
            const SizedBox(height: 24),
            Text(AppLocalizations.of(context).restoringSession, style: Theme.of(context).textTheme.titleLarge),
          ],
        ),
      ),
    );
  }
}

/// Le serveur n'a pas répondu au démarrage : on garde le jeton et on propose de réessayer ou de corriger l'adresse.
class _RestoreErrorScreen extends ConsumerWidget {
  const _RestoreErrorScreen({required this.error});

  final Object error;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Icon(Icons.cloud_off, size: 80, color: Theme.of(context).colorScheme.error),
                const SizedBox(height: 16),
                Text(
                  errorMessage(l10n, error),
                  key: const Key('restore_error'),
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 24),
                FilledButton.icon(
                  key: const Key('restore_retry'),
                  onPressed: () => ref.invalidate(authControllerProvider),
                  icon: const Icon(Icons.refresh),
                  label: Text(l10n.retry),
                ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  key: const Key('restore_settings'),
                  onPressed: () => Navigator.of(context)
                      .push(MaterialPageRoute<void>(builder: (_) => const SettingsScreen())),
                  icon: const Icon(Icons.settings),
                  label: Text(l10n.settings),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
