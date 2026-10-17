import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/providers.dart';
import '../../../core/settings/base_url.dart';
import '../../../core/widgets/language_switcher.dart';
import '../../../l10n/app_localizations.dart';

/// Teste une adresse sans la enregistrer. Surchargeable dans les tests.
final connectionProberProvider = Provider<Future<ConnectionStatus> Function(String baseUrl)>(
  (ref) => (url) => ApiClient(baseUrl: url).probe(),
);

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _address;
  bool _testing = false;
  ConnectionStatus? _result;

  @override
  void initState() {
    super.initState();
    _address = TextEditingController(text: ref.read(baseUrlProvider));
  }

  @override
  void dispose() {
    _address.dispose();
    super.dispose();
  }

  Future<void> _test() async {
    if (!_formKey.currentState!.validate()) return;
    final url = normalizeBaseUrl(_address.text)!;
    setState(() {
      _testing = true;
      _result = null;
    });
    final status = await ref.read(connectionProberProvider)(url);
    if (!mounted) return;
    setState(() {
      _testing = false;
      _result = status;
    });
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final url = normalizeBaseUrl(_address.text)!;
    await ref.read(baseUrlProvider.notifier).save(url);
    if (!mounted) return;
    _address.text = url;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppLocalizations.of(context).saved)));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.settingsTitle)),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(l10n.backendAddress, style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 12),
                  TextFormField(
                    key: const Key('address_field'),
                    controller: _address,
                    keyboardType: TextInputType.url,
                    textDirection: TextDirection.ltr, // une adresse web reste de gauche à droite, même en arabe
                    style: theme.textTheme.titleLarge,
                    decoration: InputDecoration(helperText: l10n.backendAddressHelp, helperMaxLines: 2),
                    validator: (v) => normalizeBaseUrl(v ?? '') == null ? l10n.addressInvalid : null,
                    onChanged: (_) => setState(() => _result = null),
                  ),
                  const SizedBox(height: 20),
                  OutlinedButton.icon(
                    key: const Key('test_connection'),
                    onPressed: _testing ? null : _test,
                    icon: _testing
                        ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 3))
                        : const Icon(Icons.wifi_find),
                    label: Text(_testing ? l10n.testing : l10n.testConnection),
                  ),
                  if (_result != null) ...[
                    const SizedBox(height: 16),
                    _ConnectionResult(status: _result!),
                  ],
                  const SizedBox(height: 16),
                  FilledButton.icon(
                    key: const Key('save_settings'),
                    onPressed: _save,
                    icon: const Icon(Icons.save),
                    label: Text(l10n.save),
                  ),
                  const Divider(height: 56, thickness: 2),
                  Text(l10n.language, style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 12),
                  const Align(alignment: AlignmentDirectional.centerStart, child: LanguageSwitcher()),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _ConnectionResult extends StatelessWidget {
  const _ConnectionResult({required this.status});

  final ConnectionStatus status;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final ok = status == ConnectionStatus.ok;
    final color = ok ? const Color(0xFF1B5E20) : Theme.of(context).colorScheme.error;
    final text = switch (status) {
      ConnectionStatus.ok => l10n.connectionOk,
      ConnectionStatus.notEdebou => l10n.connectionNotEdebou,
      ConnectionStatus.unreachable => l10n.connectionUnreachable,
      ConnectionStatus.timeout => l10n.connectionTimeout,
    };
    return Container(
      key: Key('connection_result_${status.name}'),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        border: Border.all(color: color, width: 2),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          Icon(ok ? Icons.check_circle : Icons.error_outline, color: color, size: 32),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600))),
        ],
      ),
    );
  }
}
