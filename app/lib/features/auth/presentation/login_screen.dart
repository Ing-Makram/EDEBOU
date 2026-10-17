import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_error.dart';
import '../../../core/errors/error_messages.dart';
import '../../../core/widgets/language_switcher.dart';
import '../../../l10n/app_localizations.dart';
import '../../settings/presentation/settings_screen.dart';
import '../application/auth_controller.dart';
import 'pin_pad.dart';

final _pinPattern = RegExp(r'^\d{4,6}$'); // même règle que le serveur (docs/api.md) ; lui seul fait foi

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _pin = TextEditingController();
  bool _busy = false;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _name.text = ref.read(authRepositoryProvider).lastUserName ?? '';
  }

  @override
  void dispose() {
    _name.dispose();
    _pin.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy || !_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(authControllerProvider.notifier).login(_name.text.trim(), _pin.text);
      // Succès : AuthGate affiche l'accueil, rien d'autre à faire ici.
    } on ApiError catch (e) {
      if (mounted) {
        setState(() => _error = e);
        _pin.clear();
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _openSettings() =>
      Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const SettingsScreen()));

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final expired = ref.watch(sessionNoticeProvider) == SessionNotice.expired;
    final error = _error;
    final errorText = error == null
        ? null
        : error is UnauthorizedError
            ? l10n.loginInvalidCredentials
            : errorMessage(l10n, error);

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const LanguageSwitcher(),
                        IconButton(
                          key: const Key('open_settings'),
                          tooltip: l10n.settings,
                          icon: const Icon(Icons.settings),
                          onPressed: _openSettings,
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Text(
                      l10n.loginTitle,
                      textAlign: TextAlign.center,
                      style: theme.textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 8),
                    Text(l10n.loginSubtitle, textAlign: TextAlign.center, style: theme.textTheme.titleMedium),
                    const SizedBox(height: 24),
                    if (expired) ...[
                      _Banner(key: const Key('session_expired'), text: l10n.sessionExpired),
                      const SizedBox(height: 16),
                    ],
                    TextFormField(
                      key: const Key('name_field'),
                      controller: _name,
                      enabled: !_busy,
                      textInputAction: TextInputAction.next,
                      style: theme.textTheme.titleLarge,
                      decoration: InputDecoration(labelText: l10n.nameLabel),
                      validator: (v) => (v ?? '').trim().isEmpty ? l10n.nameRequired : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      key: const Key('pin_field'),
                      controller: _pin,
                      enabled: !_busy,
                      obscureText: true,
                      keyboardType: TextInputType.number,
                      textInputAction: TextInputAction.done,
                      style: theme.textTheme.titleLarge?.copyWith(letterSpacing: 8),
                      inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)],
                      decoration: InputDecoration(labelText: l10n.pinLabel),
                      validator: (v) => _pinPattern.hasMatch(v ?? '') ? null : l10n.pinFormat,
                      onFieldSubmitted: (_) => _submit(),
                    ),
                    const SizedBox(height: 16),
                    PinPad(controller: _pin, enabled: !_busy),
                    if (errorText != null) ...[
                      const SizedBox(height: 16),
                      _Banner(key: const Key('login_error'), text: errorText, isError: true),
                      if (error is NetworkError)
                        TextButton.icon(
                          key: const Key('error_open_settings'),
                          onPressed: _openSettings,
                          icon: const Icon(Icons.settings),
                          label: Text(l10n.settings),
                        ),
                    ],
                    const SizedBox(height: 24),
                    FilledButton(
                      key: const Key('login_button'),
                      onPressed: _busy ? null : _submit,
                      child: _busy
                          ? const SizedBox(width: 28, height: 28, child: CircularProgressIndicator(strokeWidth: 3))
                          : Text(l10n.loginButton),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({super.key, required this.text, this.isError = false});

  final String text;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final color = isError ? scheme.error : scheme.primary;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        border: Border.all(color: color, width: 2),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          Icon(isError ? Icons.error_outline : Icons.info_outline, color: color, size: 32),
          const SizedBox(width: 12),
          Expanded(
            child: Text(text, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}
