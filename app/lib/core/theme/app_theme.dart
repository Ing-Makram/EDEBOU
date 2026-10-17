import 'package:flutter/material.dart';

/// Thème pensé pour des utilisateurs peu à l'aise avec l'informatique :
/// contraste fort, texte grand, boutons et champs très larges (zones tactiles ≥ 64 px).
class AppTheme {
  AppTheme._();

  static const _primary = Color(0xFF0B3C6F); // bleu profond sur blanc : contraste ~11:1
  static const _error = Color(0xFFB3261E);
  static const _ink = Color(0xFF111111);

  static const double minTap = 64;

  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(seedColor: _primary, brightness: Brightness.light).copyWith(
      primary: _primary,
      onPrimary: Colors.white,
      error: _error,
      onError: Colors.white,
      surface: Colors.white,
      onSurface: _ink,
    );
    // Le thème de base n'a pas de tailles de texte tant qu'il n'est pas « localisé » : sans cela,
    // textTheme.apply(fontSizeFactor: …) échoue au démarrage.
    final base = ThemeData.localize(ThemeData(colorScheme: scheme, useMaterial3: true), Typography.englishLike2021);
    final text = base.textTheme.apply(fontSizeFactor: 1.2, bodyColor: _ink, displayColor: _ink);
    const radius = BorderRadius.all(Radius.circular(14));

    return base.copyWith(
      scaffoldBackgroundColor: const Color(0xFFF4F7FA),
      textTheme: text,
      appBarTheme: AppBarTheme(
        toolbarHeight: 72,
        backgroundColor: _primary,
        foregroundColor: Colors.white,
        titleTextStyle: text.headlineSmall?.copyWith(color: Colors.white, fontWeight: FontWeight.w700),
        // Icônes blanches sur la barre bleue (sinon gris foncé sur bleu foncé : invisibles).
        iconTheme: const IconThemeData(size: 32, color: Colors.white),
        actionsIconTheme: const IconThemeData(size: 32, color: Colors.white),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(120, minTap),
          textStyle: text.titleLarge?.copyWith(fontWeight: FontWeight.w700),
          shape: const RoundedRectangleBorder(borderRadius: radius),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(120, minTap),
          textStyle: text.titleLarge?.copyWith(fontWeight: FontWeight.w700),
          side: const BorderSide(color: _primary, width: 2),
          shape: const RoundedRectangleBorder(borderRadius: radius),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          minimumSize: const Size(88, minTap),
          textStyle: text.titleMedium?.copyWith(fontWeight: FontWeight.w600),
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(minimumSize: const Size(minTap, minTap), iconSize: 32),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
        labelStyle: text.titleMedium,
        floatingLabelStyle: text.titleMedium?.copyWith(color: _primary, fontWeight: FontWeight.w700),
        helperStyle: text.bodyMedium,
        errorStyle: text.bodyMedium?.copyWith(color: _error, fontWeight: FontWeight.w600),
        border: const OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: _ink, width: 1.5)),
        enabledBorder: const OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: _ink, width: 1.5)),
        focusedBorder: const OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: _primary, width: 3)),
        errorBorder: const OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: _error, width: 2)),
        focusedErrorBorder: const OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: _error, width: 3)),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: SegmentedButton.styleFrom(
          minimumSize: const Size(120, 56),
          textStyle: text.titleMedium?.copyWith(fontWeight: FontWeight.w700),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        contentTextStyle: text.titleMedium?.copyWith(color: Colors.white),
      ),
    );
  }
}
