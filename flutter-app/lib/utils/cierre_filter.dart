import '../models/client_model.dart';
import 'excel_date.dart';

enum CierreFilterMode { none, byDate, byDays }

/// Filtro de cierre de ciclo por cuenta (fecha programada o días restantes).
class CierreFilter {
  final CierreFilterMode mode;
  final DateTime? dateFrom; // inclusive
  final DateTime? dateTo; // inclusive
  final int? maxDias; // 0 = hoy, N = faltan 0..N
  final bool vencidos; // dias < 0

  const CierreFilter({
    this.mode = CierreFilterMode.none,
    this.dateFrom,
    this.dateTo,
    this.maxDias,
    this.vencidos = false,
  });

  static const none = CierreFilter();

  bool get isActive => mode != CierreFilterMode.none;

  factory CierreFilter.byDateRange({
    required DateTime from,
    required DateTime to,
  }) {
    final a = dateOnly(from);
    final b = dateOnly(to);
    return CierreFilter(
      mode: CierreFilterMode.byDate,
      dateFrom: a.isBefore(b) ? a : b,
      dateTo: a.isBefore(b) ? b : a,
    );
  }

  factory CierreFilter.bySingleDate(DateTime day) {
    final d = dateOnly(day);
    return CierreFilter(
      mode: CierreFilterMode.byDate,
      dateFrom: d,
      dateTo: d,
    );
  }

  factory CierreFilter.withinDays(int maxDias) {
    return CierreFilter(
      mode: CierreFilterMode.byDays,
      maxDias: maxDias < 0 ? 0 : maxDias,
    );
  }

  factory CierreFilter.onlyVencidos() {
    return const CierreFilter(
      mode: CierreFilterMode.byDays,
      vencidos: true,
    );
  }

  /// Clave estable para invalidar caches de filtrado.
  String get cacheKey {
    if (!isActive) return '';
    if (mode == CierreFilterMode.byDate) {
      return 'date:${_iso(dateFrom)}:${_iso(dateTo)}';
    }
    if (vencidos) return 'days:vencidos';
    return 'days:$maxDias';
  }

  static String _iso(DateTime? d) {
    if (d == null) return '';
    final x = dateOnly(d);
    final m = x.month.toString().padLeft(2, '0');
    final day = x.day.toString().padLeft(2, '0');
    return '${x.year}-$m-$day';
  }
}

/// Resuelve la fecha de cierre programada de una cuenta.
///
/// Prioridad: `fecha_cierre_dt` → parseo de `fecha_cierre` →
/// `fecha_asignacion` + (duracionDias − 1).
DateTime? resolveFechaCierre(
  ClientModel client, {
  int duracionDias = 59,
}) {
  final fromDt = parseExcelFecha(client.fechaCierreDt);
  if (fromDt != null) return fromDt;

  final fromStr = parseExcelFecha(client.fechaCierre);
  if (fromStr != null) return fromStr;

  final asignacion = parseExcelFecha(client.fechaAsignacion);
  if (asignacion == null) return null;

  final duracion = duracionDias > 0 ? duracionDias : 59;
  return asignacion.add(Duration(days: duracion - 1));
}

/// Días restantes hasta el cierre (negativo = vencido). Null si no hay fecha.
int? diasParaCerrar(
  ClientModel client, {
  required DateTime now,
  int duracionDias = 59,
}) {
  final cierre = resolveFechaCierre(client, duracionDias: duracionDias);
  if (cierre == null) return null;
  return dateOnly(cierre).difference(dateOnly(now)).inDays;
}

bool matchesCierreFilter(
  ClientModel client,
  CierreFilter filter, {
  required DateTime now,
  int duracionDias = 59,
}) {
  if (!filter.isActive) return true;

  final cierre = resolveFechaCierre(client, duracionDias: duracionDias);
  if (cierre == null) return false;

  if (filter.mode == CierreFilterMode.byDate) {
    final from = filter.dateFrom;
    final to = filter.dateTo;
    if (from == null || to == null) return false;
    final d = dateOnly(cierre);
    return !d.isBefore(dateOnly(from)) && !d.isAfter(dateOnly(to));
  }

  // byDays
  final dias = dateOnly(cierre).difference(dateOnly(now)).inDays;
  if (filter.vencidos) return dias < 0;
  final max = filter.maxDias ?? 0;
  return dias >= 0 && dias <= max;
}

List<ClientModel> applyCierreFilter(
  List<ClientModel> clients,
  CierreFilter filter, {
  required DateTime now,
  int duracionDias = 59,
}) {
  if (!filter.isActive) return clients;
  return clients
      .where(
        (c) => matchesCierreFilter(
          c,
          filter,
          now: now,
          duracionDias: duracionDias,
        ),
      )
      .toList();
}

/// Ordena por fecha de cierre ascendente (más urgente primero).
/// Sin fecha al final.
List<ClientModel> sortClientsByCierre(
  List<ClientModel> clients, {
  int duracionDias = 59,
}) {
  final copy = List<ClientModel>.from(clients);
  copy.sort((a, b) {
    final ca = resolveFechaCierre(a, duracionDias: duracionDias);
    final cb = resolveFechaCierre(b, duracionDias: duracionDias);
    if (ca == null && cb == null) return 0;
    if (ca == null) return 1;
    if (cb == null) return -1;
    return ca.compareTo(cb);
  });
  return copy;
}

String cierreFilterLabel(CierreFilter filter) {
  if (!filter.isActive) return 'Cierre';
  if (filter.mode == CierreFilterMode.byDate) {
    final from = filter.dateFrom;
    final to = filter.dateTo;
    if (from == null || to == null) return 'Fecha';
    final a = _fmtShort(from);
    final b = _fmtShort(to);
    if (a == b) return a;
    return '$a–$b';
  }
  if (filter.vencidos) return 'Vencidos';
  final n = filter.maxDias ?? 0;
  if (n == 0) return 'Hoy';
  return '≤$n días';
}

String formatCierreBadge({
  required DateTime? cierre,
  required DateTime now,
}) {
  if (cierre == null) return '';
  final dias = dateOnly(cierre).difference(dateOnly(now)).inDays;
  if (dias < 0) return 'Vencido';
  if (dias == 0) return 'Hoy';
  return '${_fmtShort(cierre)} · ${dias}d';
}

/// Color semántico: 0=neutral, 1=warning(≤7), 2=urgent(≤3/hoy), 3=danger(vencido).
int cierreUrgencyLevel({
  required DateTime? cierre,
  required DateTime now,
}) {
  if (cierre == null) return 0;
  final dias = dateOnly(cierre).difference(dateOnly(now)).inDays;
  if (dias < 0) return 3;
  if (dias <= 3) return 2;
  if (dias <= 7) return 1;
  return 0;
}

String _fmtShort(DateTime d) {
  final day = d.day.toString().padLeft(2, '0');
  final month = d.month.toString().padLeft(2, '0');
  return '$day/$month';
}
