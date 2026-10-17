import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../providers.dart';

/// Bascule français / arabe. L'arabe inverse tout l'écran (droite-à-gauche) car la langue de l'app change.
class LanguageSwitcher extends ConsumerWidget {
  const LanguageSwitcher({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final current = ref.watch(localeProvider).languageCode;
    return SegmentedButton<String>(
      key: const Key('language_switcher'),
      showSelectedIcon: false,
      segments: [
        ButtonSegment(value: 'fr', label: Text(l10n.languageFrench)),
        ButtonSegment(value: 'ar', label: Text(l10n.languageArabic)),
      ],
      selected: {current},
      onSelectionChanged: (s) => ref.read(localeProvider.notifier).setLanguage(s.first),
    );
  }
}
