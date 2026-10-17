import 'package:edebou/core/settings/base_url.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('normalizeBaseUrl', () {
    test('adresses valides', () {
      expect(normalizeBaseUrl('http://127.0.0.1:8000'), 'http://127.0.0.1:8000');
      expect(normalizeBaseUrl('https://depot.local'), 'https://depot.local');
      expect(normalizeBaseUrl('http://localhost:8000/'), 'http://localhost:8000');
      expect(normalizeBaseUrl('http://192.168.1.20:8000///'), 'http://192.168.1.20:8000');
    });

    test('espaces autour retirés, http ajouté si absent', () {
      expect(normalizeBaseUrl('  192.168.1.20:8000  '), 'http://192.168.1.20:8000');
      expect(normalizeBaseUrl('depot-pc:8000/'), 'http://depot-pc:8000');
    });

    test('adresses refusées', () {
      for (final bad in ['', '   ', 'ftp://x', 'http://', 'http://:8000', 'http://a b', 'http://x?y=1', 'http://x#f', 'http://u:p@x']) {
        expect(normalizeBaseUrl(bad), isNull, reason: bad);
      }
    });
  });
}
