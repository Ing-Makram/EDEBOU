import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/app_localizations.dart';
import '../../auth/application/auth_controller.dart';
import '../../auth/domain/session.dart';
import '../../clients/presentation/clients_screen.dart';
import '../../consignments/presentation/consignments_screen.dart';
import '../../sales/presentation/sales_screen.dart';
import '../../settings/presentation/settings_screen.dart';
import '../../stock/presentation/stock_screen.dart';

enum HomeModule { cashRegister, clients, consignments, stock }

/// Modules affichés pour chaque rôle (docs/api.md « Rôles et accès »). Affichage seulement :
/// le serveur refuse (403) tout ce que le rôle n'a pas le droit de faire.
List<HomeModule> modulesForRole(UserRole role) => switch (role) {
      UserRole.manager || UserRole.cashier => HomeModule.values,
      UserRole.delivery => const [HomeModule.stock], // le livreur ne peut que consulter le stock
    };

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key, required this.session});

  final Session session;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final roleLabel = switch (session.role) {
      UserRole.manager => l10n.roleManager,
      UserRole.cashier => l10n.roleCashier,
      UserRole.delivery => l10n.roleDelivery,
    };

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.appName),
        actions: [
          IconButton(
            key: const Key('home_settings'),
            tooltip: l10n.settings,
            icon: const Icon(Icons.settings),
            onPressed: () =>
                Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const SettingsScreen())),
          ),
          IconButton(
            key: const Key('home_logout'),
            tooltip: l10n.logout,
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authControllerProvider.notifier).logout(),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              l10n.welcomeUser(session.name),
              key: const Key('welcome'),
              style: theme.textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            Text(roleLabel, key: const Key('role_label'), style: theme.textTheme.headlineSmall),
            const SizedBox(height: 32),
            Wrap(
              spacing: 24,
              runSpacing: 24,
              children: [
                for (final m in modulesForRole(session.role))
                  _ModuleTile(
                    key: Key('module_${m.name}'),
                    icon: _icon(m),
                    label: _label(l10n, m),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => _screen(m))),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  static IconData _icon(HomeModule m) => switch (m) {
        HomeModule.cashRegister => Icons.point_of_sale,
        HomeModule.clients => Icons.people,
        HomeModule.consignments => Icons.inventory_2,
        HomeModule.stock => Icons.warehouse,
      };

  static String _label(AppLocalizations l10n, HomeModule m) => switch (m) {
        HomeModule.cashRegister => l10n.moduleCashRegister,
        HomeModule.clients => l10n.moduleClients,
        HomeModule.consignments => l10n.moduleConsignments,
        HomeModule.stock => l10n.moduleStock,
      };

  static Widget _screen(HomeModule m) => switch (m) {
        HomeModule.cashRegister => const SalesScreen(),
        HomeModule.clients => const ClientsScreen(),
        HomeModule.consignments => const ConsignmentsScreen(),
        HomeModule.stock => const StockScreen(),
      };
}

class _ModuleTile extends StatelessWidget {
  const _ModuleTile({super.key, required this.icon, required this.label, required this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SizedBox(
      width: 240,
      height: 180,
      child: Material(
        color: theme.colorScheme.primary,
        borderRadius: BorderRadius.circular(20),
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: onTap,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 64, color: Colors.white),
              const SizedBox(height: 12),
              Text(
                label,
                style: theme.textTheme.headlineSmall?.copyWith(color: Colors.white, fontWeight: FontWeight.w800),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
