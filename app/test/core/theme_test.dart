import 'package:edebou/core/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Rapport de contraste WCAG entre deux couleurs (1 à 21).
double contrast(Color a, Color b) {
  final l1 = a.computeLuminance(), l2 = b.computeLuminance();
  final hi = l1 > l2 ? l1 : l2, lo = l1 > l2 ? l2 : l1;
  return (hi + 0.05) / (lo + 0.05);
}

void main() {
  final theme = AppTheme.light();

  test('texte principal sur fond : contraste AAA (≥ 7)', () {
    expect(contrast(theme.colorScheme.onSurface, theme.scaffoldBackgroundColor), greaterThanOrEqualTo(7));
    expect(contrast(theme.colorScheme.onSurface, theme.colorScheme.surface), greaterThanOrEqualTo(7));
  });

  test('boutons principaux : texte blanc sur bleu, contraste AAA (≥ 7)', () {
    expect(contrast(theme.colorScheme.onPrimary, theme.colorScheme.primary), greaterThanOrEqualTo(7));
  });

  test('barre d\'application : titre ET icônes lisibles (régression : icônes gris foncé sur bleu foncé)', () {
    final bar = theme.appBarTheme;
    final background = bar.backgroundColor!;
    expect(contrast(bar.titleTextStyle!.color!, background), greaterThanOrEqualTo(7));
    expect(bar.iconTheme!.color, isNotNull, reason: 'icône de retour sans couleur explicite');
    expect(contrast(bar.iconTheme!.color!, background), greaterThanOrEqualTo(7));
    expect(bar.actionsIconTheme!.color, isNotNull, reason: 'icônes réglages/déconnexion sans couleur explicite');
    expect(contrast(bar.actionsIconTheme!.color!, background), greaterThanOrEqualTo(7));
  });

  test('messages d\'erreur lisibles sur fond blanc (≥ 4,5)', () {
    expect(contrast(theme.colorScheme.error, Colors.white), greaterThanOrEqualTo(4.5));
  });

  test('zones tactiles : boutons ≥ 64 px de haut, icônes de barre ≥ 64 px', () {
    expect(AppTheme.minTap, greaterThanOrEqualTo(64));
    expect(theme.filledButtonTheme.style!.minimumSize!.resolve({})!.height, greaterThanOrEqualTo(64));
    expect(theme.outlinedButtonTheme.style!.minimumSize!.resolve({})!.height, greaterThanOrEqualTo(64));
    expect(theme.iconButtonTheme.style!.minimumSize!.resolve({})!.shortestSide, greaterThanOrEqualTo(64));
  });

  test('texte agrandi : le corps de texte est plus grand que la valeur Material par défaut', () {
    final standard = ThemeData.localize(ThemeData(useMaterial3: true), Typography.englishLike2021).textTheme;
    expect(theme.textTheme.bodyLarge!.fontSize!, greaterThan(standard.bodyLarge!.fontSize!));
    expect(theme.textTheme.titleLarge!.fontSize!, greaterThan(standard.titleLarge!.fontSize!));
  });
}
