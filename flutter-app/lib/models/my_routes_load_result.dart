/// Resultado de cargar rutas diarias del gestor.
class MyRoutesLoadResult {
  const MyRoutesLoadResult({
    required this.routes,
    this.error,
    this.warning,
  });

  final List<Map<String, dynamic>> routes;
  final String? error;
  final String? warning;

  bool get hasError => error != null && error!.isNotEmpty;
}
