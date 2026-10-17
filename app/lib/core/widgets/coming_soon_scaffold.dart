import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';

/// Écran provisoire d'un module pas encore construit.
class ComingSoonScaffold extends StatelessWidget {
  const ComingSoonScaffold({super.key, required this.title, required this.icon});

  final String title;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 96, color: theme.colorScheme.primary),
            const SizedBox(height: 24),
            Text(AppLocalizations.of(context).comingSoon, style: theme.textTheme.headlineMedium),
          ],
        ),
      ),
    );
  }
}
