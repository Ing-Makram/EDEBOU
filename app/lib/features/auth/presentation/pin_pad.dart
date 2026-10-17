import 'package:flutter/material.dart';

import '../../../l10n/app_localizations.dart';

/// Clavier numérique à gros boutons pour saisir le PIN au doigt. Écrit dans le même contrôleur
/// que le champ PIN : le clavier physique continue de fonctionner.
///
/// Toujours affiché de gauche à droite (1-2-3 en haut), même en arabe : c'est la disposition
/// universelle des claviers numériques.
class PinPad extends StatelessWidget {
  const PinPad({super.key, required this.controller, this.maxLength = 6, this.enabled = true});

  final TextEditingController controller;
  final int maxLength;
  final bool enabled;

  void _set(String text) {
    controller.value = TextEditingValue(text: text, selection: TextSelection.collapsed(offset: text.length));
  }

  void _digit(String d) {
    if (controller.text.length < maxLength) _set(controller.text + d);
  }

  void _backspace() {
    final t = controller.text;
    if (t.isNotEmpty) _set(t.substring(0, t.length - 1));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    Widget digit(String d) => _PadKey(
          key: Key('pin_key_$d'),
          onPressed: enabled ? () => _digit(d) : null,
          child: Text(d),
        );

    return Directionality(
      textDirection: TextDirection.ltr,
      child: GridView.count(
        crossAxisCount: 3,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        mainAxisSpacing: 10,
        crossAxisSpacing: 10,
        childAspectRatio: 2.2,
        children: [
          for (final d in ['1', '2', '3', '4', '5', '6', '7', '8', '9']) digit(d),
          _PadKey(
            key: const Key('pin_clear'),
            onPressed: enabled ? () => _set('') : null,
            child: const Icon(Icons.clear, size: 32),
          ),
          digit('0'),
          _PadKey(
            key: const Key('pin_backspace'),
            tooltip: l10n.pinBackspace,
            onPressed: enabled ? _backspace : null,
            child: const Icon(Icons.backspace_outlined, size: 32),
          ),
        ],
      ),
    );
  }
}

class _PadKey extends StatelessWidget {
  const _PadKey({super.key, required this.child, required this.onPressed, this.tooltip});

  final Widget child;
  final VoidCallback? onPressed;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final button = FilledButton.tonal(
      onPressed: onPressed,
      style: FilledButton.styleFrom(
        textStyle: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700),
      ),
      child: child,
    );
    return tooltip == null ? button : Tooltip(message: tooltip!, child: button);
  }
}
