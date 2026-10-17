import 'dart:convert';
import 'dart:io';
import 'dart:ui';

import 'package:edebou/core/api/api_error.dart';
import 'package:edebou/core/api/business_code.dart';
import 'package:edebou/core/errors/error_messages.dart';
import 'package:edebou/l10n/app_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

/// Codes de la section « Codes d'erreur métier » de docs/api.md (colonne 1 du tableau).
Set<String> documentedCodes() {
  final doc = File('../docs/api.md').readAsStringSync();
  final start = doc.indexOf("## Codes d'erreur métier");
  expect(start, greaterThan(0), reason: 'section introuvable dans docs/api.md');
  final end = doc.indexOf('\n---', start);
  final section = doc.substring(start, end == -1 ? doc.length : end);
  final codes = <String>{};
  for (final line in section.split('\n')) {
    if (!line.startsWith('| `')) continue;
    final firstCell = line.split('|')[1].replaceAll(RegExp(r'\([^)]*\)'), ''); // enlève « (product, requested…) »
    if (firstCell.trim() == '`code`') continue; // ligne d'en-tête
    codes.addAll(RegExp(r'`([a-z_]+)`').allMatches(firstCell).map((m) => m.group(1)!));
  }
  return codes;
}

void main() {
  group('docs/api.md ↔ application', () {
    test('le tableau de la documentation est bien lu', () {
      expect(documentedCodes().length, greaterThan(20));
      expect(documentedCodes(), containsAll(['insufficient_stock', 'credit_limit_exceeded', 'last_manager']));
    });

    test('chaque code documenté est connu de l\'application', () {
      final known = BusinessCode.values.where((c) => c != BusinessCode.unknown).map((c) => c.wire).toSet();
      expect(documentedCodes().difference(known), isEmpty, reason: 'codes documentés mais absents de BusinessCode');
    });

    test('chaque code de l\'application est documenté', () {
      final known = BusinessCode.values.where((c) => c != BusinessCode.unknown).map((c) => c.wire).toSet();
      expect(known.difference(documentedCodes()), isEmpty, reason: 'codes de BusinessCode absents de docs/api.md');
    });

    test('chaque code du serveur (backend) est documenté', () {
      // Garde-fou contre une dérive doc ↔ serveur : tous les BusinessError('…') du backend.
      final backend = Directory('../backend');
      if (!backend.existsSync()) return;
      final found = <String>{};
      final re = RegExp(r"BusinessError\(\s*'([a-z_]+)'");
      for (final f in backend.listSync(recursive: true).whereType<File>()) {
        if (!f.path.endsWith('.py') || f.path.contains('.venv') || f.path.contains('test')) continue;
        found.addAll(re.allMatches(f.readAsStringSync()).map((m) => m.group(1)!));
      }
      expect(found, isNotEmpty);
      expect(found.difference(documentedCodes()), isEmpty, reason: 'codes du serveur absents de docs/api.md');
    });
  });

  group('messages traduits', () {
    for (final locale in const [Locale('fr'), Locale('ar')]) {
      test('${locale.languageCode} : chaque code métier a un message non vide', () {
        final l10n = lookupAppLocalizations(locale);
        for (final code in BusinessCode.values) {
          final text = businessMessage(
            l10n,
            BusinessError(code: code, rawCode: code.wire, context: const {'product': 'Eau', 'available': 12, 'held': 3, 'current': 7}),
          );
          expect(text.trim(), isNotEmpty, reason: '$code');
          expect(text, isNot(contains('{')), reason: 'marqueur non remplacé pour $code');
        }
      });

      test('${locale.languageCode} : chaque type d\'erreur a un message', () {
        final l10n = lookupAppLocalizations(locale);
        final errors = <ApiError>[
          const NetworkError(),
          const NetworkError(timeout: true),
          const UnauthorizedError(),
          const ForbiddenError(),
          const NotFoundError(),
          const ThrottledError(),
          const ServerError(500),
          const ValidationError({}),
          const UnknownError(),
          const BusinessError(code: BusinessCode.unknown, rawCode: 'x'),
        ];
        final messages = errors.map((e) => errorMessage(l10n, e)).toList();
        expect(messages.every((m) => m.trim().isNotEmpty), isTrue);
      });
    }

    test('les chiffres du contexte apparaissent dans le message', () {
      final l10n = lookupAppLocalizations(const Locale('fr'));
      final text = errorMessage(
        l10n,
        const BusinessError(
          code: BusinessCode.insufficientStock,
          rawCode: 'insufficient_stock',
          context: {'product': 'Eau minérale', 'available': 269},
        ),
      );
      expect(text, allOf(contains('Eau minérale'), contains('269')));
    });

    test('le detail français du serveur n\'est jamais affiché', () {
      final l10n = lookupAppLocalizations(const Locale('ar'));
      final text = errorMessage(
        l10n,
        const BusinessError(code: BusinessCode.overpaid, rawCode: 'overpaid', detail: 'Le montant payé dépasse le total.'),
      );
      expect(text, isNot(contains('Le montant')));
    });
  });

  group('fichiers de traduction', () {
    Map<String, dynamic> load(String lang) =>
        jsonDecode(File('lib/l10n/app_$lang.arb').readAsStringSync()) as Map<String, dynamic>;

    Set<String> keys(Map<String, dynamic> arb) => arb.keys.where((k) => !k.startsWith('@')).toSet();

    test('français et arabe ont exactement les mêmes clés', () {
      final fr = keys(load('fr')), ar = keys(load('ar'));
      expect(fr.difference(ar), isEmpty, reason: 'clés manquantes en arabe');
      expect(ar.difference(fr), isEmpty, reason: 'clés en trop en arabe');
    });

    test('aucune traduction vide', () {
      for (final lang in ['fr', 'ar']) {
        final arb = load(lang);
        for (final k in keys(arb).where((k) => k != '@@locale')) {
          expect((arb[k] as String).trim(), isNotEmpty, reason: '$lang/$k');
        }
      }
    });

    test('les marqueurs {…} sont les mêmes dans les deux langues', () {
      final fr = load('fr'), ar = load('ar');
      final re = RegExp(r'\{(\w+)\}');
      for (final k in keys(fr)) {
        Set<String> marks(Map<String, dynamic> m) => re.allMatches(m[k] as String).map((x) => x.group(1)!).toSet();
        expect(marks(ar), marks(fr), reason: k);
      }
    });

    test('l\'arabe contient bien de l\'arabe', () {
      final ar = load('ar');
      final arabic = RegExp(r'[؀-ۿ]');
      final translated = keys(ar).where((k) => k != '@@locale' && arabic.hasMatch(ar[k] as String));
      expect(translated.length, greaterThan(keys(ar).length - 6)); // sauf noms propres (Edebou, Français…)
    });
  });

  test('aucun texte écrit en dur dans les écrans (tout passe par les fichiers .arb)', () {
    final patterns = {
      'Text("…")': RegExp(r'''\bText\(\s*['"]'''),
      'labelText': RegExp(r'''labelText:\s*['"]'''),
      'hintText': RegExp(r'''hintText:\s*['"]'''),
      'helperText': RegExp(r'''helperText:\s*['"]'''),
      'errorText': RegExp(r'''errorText:\s*['"]'''),
      'tooltip': RegExp(r'''tooltip:\s*['"]'''),
      'semanticsLabel': RegExp(r'''semanticsLabel:\s*['"]'''),
    };
    final offenders = <String>[];
    for (final f in Directory('lib').listSync(recursive: true).whereType<File>()) {
      final path = f.path.replaceAll('\\', '/');
      if (!path.endsWith('.dart') || path.contains('lib/l10n/')) continue;
      final lines = f.readAsLinesSync();
      for (var i = 0; i < lines.length; i++) {
        if (lines[i].trimLeft().startsWith('//')) continue;
        patterns.forEach((name, re) {
          if (re.hasMatch(lines[i])) offenders.add('$path:${i + 1} [$name] ${lines[i].trim()}');
        });
      }
    }
    expect(offenders, isEmpty, reason: 'textes en dur :\n${offenders.join('\n')}');
  });
}
