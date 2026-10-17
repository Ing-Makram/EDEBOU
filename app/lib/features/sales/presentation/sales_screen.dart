import 'package:flutter/material.dart';

import '../../../core/widgets/coming_soon_scaffold.dart';
import '../../../l10n/app_localizations.dart';

/// Écran provisoire : le module sera construit dans une prochaine tâche.
class SalesScreen extends StatelessWidget {
  const SalesScreen({super.key});

  @override
  Widget build(BuildContext context) =>
      ComingSoonScaffold(title: AppLocalizations.of(context).moduleCashRegister, icon: Icons.point_of_sale);
}
