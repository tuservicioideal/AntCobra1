import '../models/client_model.dart';
import 'client_display_format.dart';

const String nivelConfiable = 'confiable';
const String nivelDudosa = 'dudosa';
const String nivelDescartada = 'descartada';

/// Known address/phone entry derived from bank record + contact history.
class DireccionConocida {
  final String direccion;
  final String? telefono;
  final String fuente;
  final String? fecha;
  final String eventId;
  final String nivelConfianza;
  final int orden;
  final bool oculto;
  final bool esPrincipal;
  final String tipo;

  const DireccionConocida({
    required this.direccion,
    this.telefono,
    required this.fuente,
    this.fecha,
    this.eventId = '',
    this.nivelConfianza = nivelConfiable,
    this.orden = 0,
    this.oculto = false,
    this.esPrincipal = false,
    this.tipo = 'direccion',
  });

  bool get isEditable => eventId.isNotEmpty;
  bool get isPhoneOnly => tipo == 'telefono' && direccion.isEmpty;
}

int _nivelRank(String nivel) {
  switch (nivel) {
    case nivelConfiable:
      return 0;
    case nivelDudosa:
      return 1;
    case nivelDescartada:
      return 2;
    default:
      return 1;
  }
}

String _inferTipo(Map<String, dynamic> h) {
  final tipoRaw = (h['tipo'] ?? '').toString().toLowerCase();
  if (tipoRaw == 'gps_verificado') return 'ubicacion';
  if (tipoRaw == 'telefono' || tipoRaw == 'direccion' || tipoRaw == 'ubicacion') {
    return tipoRaw;
  }
  final campo = (h['campo'] ?? '').toString().toLowerCase();
  if (campo == 'ubicacion') return 'ubicacion';
  final addr = (h['direccion_nueva'] ?? '').toString().trim();
  final phone = (h['telefono_nuevo'] ?? '').toString().trim();
  if (addr.isNotEmpty && phone.isEmpty) return 'direccion';
  if (phone.isNotEmpty && addr.isEmpty) return 'telefono';
  if (addr.isNotEmpty) return 'direccion';
  if (phone.isNotEmpty) return 'telefono';
  return 'direccion';
}

/// Build deduplicated list: bank address, reference, then field updates.
List<DireccionConocida> collectDireccionesConocidas(
  ClientModel cliente,
  List<Map<String, dynamic>> historialContacto, {
  bool incluirOcultos = false,
}) {
  final seen = <String>{};
  final out = <DireccionConocida>[];

  String entryKey(String direccion, String? telefono) =>
      '${direccion.trim().toLowerCase()}|${(telefono ?? '').trim()}';

  void pushEntry({
    required String direccion,
    String? telefono,
    required String fuente,
    String? fecha,
    String eventId = '',
    String nivelConfianza = nivelConfiable,
    int orden = 0,
    bool oculto = false,
    bool esPrincipal = false,
    String tipo = 'direccion',
  }) {
    final d = direccion.trim();
    final t = telefono?.trim();
    if (d.isEmpty && (t == null || t.isEmpty)) return;
    if (oculto && !incluirOcultos) return;
    final key = entryKey(d.isNotEmpty ? d : (t ?? ''), t);
    if (seen.contains(key)) return;
    seen.add(key);
    out.add(DireccionConocida(
      direccion: d,
      telefono: t?.isNotEmpty == true ? t : null,
      fuente: fuente,
      fecha: fecha,
      eventId: eventId,
      nivelConfianza: nivelConfianza,
      orden: orden,
      oculto: oculto,
      esPrincipal: esPrincipal,
      tipo: tipo,
    ));
  }

  pushEntry(
    direccion: cliente.direccion,
    telefono: cliente.telefonoMovil,
    fuente: 'Registro banco (principal)',
    esPrincipal: true,
    nivelConfianza: nivelConfiable,
    orden: -1,
  );
  if (!referenceRedundant(cliente.direccion, cliente.referencia)) {
    pushEntry(
      direccion: cliente.referencia,
      fuente: 'Referencia de ubicación',
    );
  }

  final historialSorted = [...historialContacto];
  historialSorted.sort((a, b) {
    final pa = a['es_principal'] == true ? 0 : 1;
    final pb = b['es_principal'] == true ? 0 : 1;
    if (pa != pb) return pa.compareTo(pb);
    final na = _nivelRank((a['nivel_confianza'] ?? nivelConfiable).toString());
    final nb = _nivelRank((b['nivel_confianza'] ?? nivelConfiable).toString());
    if (na != nb) return na.compareTo(nb);
    final oa = int.tryParse('${a['orden'] ?? 0}') ?? 0;
    final ob = int.tryParse('${b['orden'] ?? 0}') ?? 0;
    if (oa != ob) return oa.compareTo(ob);
    final fa = (a['fecha'] ?? a['fecha_evento'] ?? '').toString();
    final fb = (b['fecha'] ?? b['fecha_evento'] ?? '').toString();
    return fb.compareTo(fa);
  });

  for (final h in historialSorted) {
    if (h['oculto'] == true && !incluirOcultos) continue;
    final tipo = _inferTipo(h);
    var d = (h['direccion_nueva'] ?? h['direccion'] ?? '').toString().trim();
    if (d.isEmpty && tipo == 'ubicacion') {
      final gps = h['gps'];
      if (gps is Map) {
        final lat = gps['latitude'] ?? gps['lat'];
        final lng = gps['longitude'] ?? gps['lng'];
        if (lat != null && lng != null) {
          d = 'GPS: $lat, $lng';
        }
      }
    }
    final t = (h['telefono_nuevo'] ?? h['telefono'] ?? '').toString().trim();
    if (d.isEmpty && t.isEmpty) continue;
    final nota = (h['nota'] ?? '').toString().trim();
    final quien = (h['usuario_nombre'] ?? h['usuario_email'] ?? '').toString().trim();
    final tipoRaw = (h['tipo'] ?? '').toString();
    final tipoLabel = tipoRaw == 'gps_verificado'
        ? 'Ubicación GPS verificada'
        : tipoRaw == 'principal'
            ? 'Actualización principal'
            : 'Nota de campo';
    final fuente = [
      nota.isNotEmpty ? nota : tipoLabel,
      if (quien.isNotEmpty) '· $quien',
    ].join(' ');
    final fecha = (h['fecha'] ?? h['fecha_evento'] ?? '').toString();
    final fechaShort =
        fecha.length >= 16 ? fecha.substring(0, 16).replaceFirst('T', ' ') : fecha;
    pushEntry(
      direccion: d,
      telefono: t.isNotEmpty ? t : null,
      fuente: fuente,
      fecha: fechaShort.isNotEmpty ? fechaShort : null,
      eventId: (h['event_id'] ?? h['id'] ?? '').toString(),
      nivelConfianza: (h['nivel_confianza'] ?? nivelConfiable).toString(),
      orden: int.tryParse('${h['orden'] ?? 0}') ?? 0,
      oculto: h['oculto'] == true,
      esPrincipal: h['es_principal'] == true,
      tipo: tipo,
    );
  }

  out.sort((a, b) {
    if (a.esPrincipal != b.esPrincipal) return a.esPrincipal ? -1 : 1;
    final na = _nivelRank(a.nivelConfianza);
    final nb = _nivelRank(b.nivelConfianza);
    if (na != nb) return na.compareTo(nb);
    return a.orden.compareTo(b.orden);
  });

  return out;
}

String nivelConfianzaLabel(String nivel) {
  switch (nivel) {
    case nivelConfiable:
      return 'Confiable';
    case nivelDudosa:
      return 'Dudosa';
    case nivelDescartada:
      return 'Descartada';
    default:
      return 'Confiable';
  }
}
