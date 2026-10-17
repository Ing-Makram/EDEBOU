import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

/// Faux « réseau » pour les tests : répond selon la requête, sans ouvrir de connexion.
class FakeAdapter implements HttpClientAdapter {
  FakeAdapter(this.handler);

  /// Peut renvoyer un `ResponseBody` (voir `jsonResponse`) ou lever une `DioException`.
  ResponseBody Function(RequestOptions options) handler;
  final List<RequestOptions> requests = [];

  Iterable<RequestOptions> requestsTo(String path) => requests.where((r) => r.path == path);

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    requests.add(options);
    return handler(options);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody jsonResponse(int status, [Object? body]) => ResponseBody.fromString(
      body == null ? '' : jsonEncode(body),
      status,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );

ResponseBody textResponse(int status, String body) => ResponseBody.fromString(body, status, headers: {
      Headers.contentTypeHeader: ['text/html'],
    });

DioException connectionError(RequestOptions o) =>
    DioException(requestOptions: o, type: DioExceptionType.connectionError, message: 'refused');

DioException timeoutError(RequestOptions o, [DioExceptionType type = DioExceptionType.connectionTimeout]) =>
    DioException(requestOptions: o, type: type);
