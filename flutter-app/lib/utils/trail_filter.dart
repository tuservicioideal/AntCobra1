import '../models/tracking_models.dart';

/// Motivo por el que un punto GPS se descarta del dibujo del recorrido.
enum TrailRejectReason {
  badAccuracy,
}

/// Punto descartado con su motivo (auditoría / toggle "puntos crudos").
class RejectedTrailPoint {
  final TrailPoint point;
  final TrailRejectReason reason;

  const RejectedTrailPoint({required this.point, required this.reason});
}

/// Parada detectada: gestor quieto dentro de un radio durante un tiempo mínimo.
class TrailStay {
  final double lat;
  final double lng;
  final DateTime start;
  final DateTime end;
  final int pointCount;

  const TrailStay({
    required this.lat,
    required this.lng,
    required this.start,
    required this.end,
    required this.pointCount,
  });

  Duration get duration => end.difference(start);
}

/// Resultado del filtrado de un trail crudo.
class FilteredTrail {
  final List<List<TrailPoint>> segments;
  final List<TrailStay> stays;
  final List<RejectedTrailPoint> rejected;
  final List<TrailPoint> kept;
  final double km;

  const FilteredTrail({
    required this.segments,
    required this.stays,
    required this.rejected,
    required this.kept,
    required this.km,
  });

  factory FilteredTrail.empty() => const FilteredTrail(
        segments: [],
        stays: [],
        rejected: [],
        kept: [],
        km: 0,
      );

  int get pointCount => kept.length;

  List<TrailPoint> get visitPoints =>
      kept.where((p) => p.isVisit).toList(growable: false);

  /// Primer y último punto temporal del trail filtrado (todos los segmentos).
  TrailPoint? get firstPoint => kept.isEmpty ? null : kept.first;
  TrailPoint? get lastPoint => kept.isEmpty ? null : kept.last;
}

/// Limpia y segmenta puntos GPS crudos para dibujar recorridos fiables.
///
/// - Descarta `tipo=auto` con accuracy peor que [maxAccuracyMeters].
/// - Los puntos `tipo=visita` nunca se descartan.
/// - Corta el segmento ante saltos imposibles o huecos temporales.
/// - Detecta paradas (nube de puntos quietos).
class TrailFilter {
  TrailFilter({
    this.maxAccuracyMeters = 50,
    this.maxJumpSpeedKmh = 130,
    this.maxGapMinutes = 15,
    this.stayRadiusMeters = 25,
    this.stayMinMinutes = 3,
  });

  final double maxAccuracyMeters;
  final double maxJumpSpeedKmh;
  final int maxGapMinutes;
  final double stayRadiusMeters;
  final int stayMinMinutes;

  FilteredTrail filter(List<TrailPoint> raw) {
    if (raw.isEmpty) return FilteredTrail.empty();

    final rejected = <RejectedTrailPoint>[];
    final kept = <TrailPoint>[];

    for (final p in raw) {
      if (!p.isVisit &&
          p.accuracy > 0 &&
          p.accuracy > maxAccuracyMeters) {
        rejected.add(RejectedTrailPoint(
          point: p,
          reason: TrailRejectReason.badAccuracy,
        ));
        continue;
      }
      kept.add(p);
    }

    if (kept.isEmpty) {
      return FilteredTrail(
        segments: const [],
        stays: const [],
        rejected: rejected,
        kept: const [],
        km: 0,
      );
    }

    final segments = _buildSegments(kept);
    final stays = _detectStays(kept);
    final km = _segmentsKm(segments);

    return FilteredTrail(
      segments: segments,
      stays: stays,
      rejected: rejected,
      kept: kept,
      km: km,
    );
  }

  List<List<TrailPoint>> _buildSegments(List<TrailPoint> points) {
    if (points.isEmpty) return const [];
    final segments = <List<TrailPoint>>[];
    var current = <TrailPoint>[points.first];

    for (var i = 1; i < points.length; i++) {
      final prev = points[i - 1];
      final next = points[i];
      if (_shouldCut(prev, next)) {
        if (current.isNotEmpty) segments.add(current);
        current = [next];
      } else {
        current.add(next);
      }
    }
    if (current.isNotEmpty) segments.add(current);
    return segments;
  }

  bool _shouldCut(TrailPoint a, TrailPoint b) {
    final ta = _timeOf(a);
    final tb = _timeOf(b);
    if (ta != null && tb != null) {
      final gap = tb.difference(ta);
      if (gap.inMinutes >= maxGapMinutes) return true;

      final seconds = gap.inMilliseconds / 1000.0;
      if (seconds > 1) {
        final distKm = TrackingGeo.haversineKm(a.lat, a.lng, b.lat, b.lng);
        final speedKmh = distKm / (seconds / 3600.0);
        if (speedKmh > maxJumpSpeedKmh) return true;
      }
    } else {
      // Sin timestamps: cortar solo por distancia absurda (> 5 km entre puntos).
      final distKm = TrackingGeo.haversineKm(a.lat, a.lng, b.lat, b.lng);
      if (distKm > 5) return true;
    }
    return false;
  }

  List<TrailStay> _detectStays(List<TrailPoint> points) {
    if (points.length < 2) return const [];

    final stays = <TrailStay>[];
    var i = 0;
    while (i < points.length) {
      final anchor = points[i];
      final anchorTime = _timeOf(anchor);
      var j = i + 1;
      double sumLat = anchor.lat;
      double sumLng = anchor.lng;
      var count = 1;

      while (j < points.length) {
        final p = points[j];
        final distM =
            TrackingGeo.haversineKm(anchor.lat, anchor.lng, p.lat, p.lng) *
                1000;
        if (distM > stayRadiusMeters) break;
        sumLat += p.lat;
        sumLng += p.lng;
        count++;
        j++;
      }

      final endPoint = points[j - 1];
      final endTime = _timeOf(endPoint);
      if (anchorTime != null &&
          endTime != null &&
          endTime.difference(anchorTime).inMinutes >= stayMinMinutes &&
          count >= 2) {
        stays.add(TrailStay(
          lat: sumLat / count,
          lng: sumLng / count,
          start: anchorTime,
          end: endTime,
          pointCount: count,
        ));
        i = j;
      } else {
        i++;
      }
    }
    return stays;
  }

  static double _segmentsKm(List<List<TrailPoint>> segments) {
    var km = 0.0;
    for (final seg in segments) {
      km += TrackingGeo.trailKm(seg);
    }
    return km;
  }

  static DateTime? _timeOf(TrailPoint p) {
    if (p.timestamp != null) return p.timestamp!.toDate();
    if (p.fecha.isNotEmpty) {
      try {
        return DateTime.parse(p.fecha);
      } catch (_) {}
    }
    return null;
  }
}
