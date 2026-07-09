/// Configuración del servicio de rutas por carretera (OSRM).
class RoutingConfig {
  RoutingConfig._();

  /// Servidor demo OSRM. Para producción masiva, sustituir por instancia propia.
  static const String baseUrl = 'https://router.project-osrm.org';

  static const String profile = 'driving';
  static const Duration requestTimeout = Duration(seconds: 15);

  /// Máximo de coordenadas por petición OSRM (conservador).
  static const int maxOsrmCoordinates = 25;
}
