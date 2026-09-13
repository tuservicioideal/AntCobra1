import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/whatsapp_plantilla.dart';

/// Catálogo empresa (`configuracion/plantillas_whatsapp`) + personales
/// (`usuarios/{uid}/whatsapp_plantillas`).
class WhatsAppPlantillaService {
  static WhatsAppPlantillaService? _instance;
  factory WhatsAppPlantillaService() =>
      _instance ??= WhatsAppPlantillaService._();
  WhatsAppPlantillaService._();

  static const _prefsLastIdKey = 'whatsapp_plantilla_last_id';
  static const _maxNombre = 80;
  static const _maxCuerpo = 2000;

  final _db = FirebaseFirestore.instance;
  List<WhatsAppPlantilla> _empresaCache = [];

  CollectionReference<Map<String, dynamic>> _personalCol(String uid) =>
      _db.collection('usuarios').doc(uid).collection('whatsapp_plantillas');

  DocumentReference<Map<String, dynamic>> get _empresaDoc =>
      _db.collection('configuracion').doc('plantillas_whatsapp');

  // ── Empresa ──────────────────────────────────────────────

  Future<List<WhatsAppPlantilla>> loadEmpresa({
    bool force = false,
    bool soloActivas = true,
  }) async {
    if (_empresaCache.isNotEmpty && !force && soloActivas) {
      return List.unmodifiable(_empresaCache);
    }
    try {
      final snap = await _empresaDoc.get();
      if (!snap.exists) {
        _empresaCache = [];
        return [];
      }
      final data = snap.data() ?? {};
      final raw = data['plantillas'];
      if (raw is! List) {
        _empresaCache = [];
        return [];
      }
      final list = raw
          .whereType<Map>()
          .map(
            (m) => WhatsAppPlantilla.fromMap(
              m['id']?.toString() ?? '',
              Map<String, dynamic>.from(m),
              origen: 'empresa',
            ),
          )
          .where((p) => p.id.isNotEmpty)
          .toList()
        ..sort((a, b) => a.orden.compareTo(b.orden));
      _empresaCache = list.where((p) => p.activa).toList();
      if (soloActivas) return List.unmodifiable(_empresaCache);
      return list;
    } catch (_) {
      return soloActivas ? List.unmodifiable(_empresaCache) : [];
    }
  }

  Future<void> publishEmpresa(List<WhatsAppPlantilla> plantillas) async {
    final payload = plantillas.map((p) {
      if (p.nombre.trim().isEmpty) {
        throw ArgumentError('El nombre de la plantilla es obligatorio');
      }
      if (p.cuerpo.trim().isEmpty) {
        throw ArgumentError('El cuerpo del mensaje es obligatorio');
      }
      if (p.nombre.length > _maxNombre) {
        throw ArgumentError('Nombre demasiado largo (máx. $_maxNombre)');
      }
      if (p.cuerpo.length > _maxCuerpo) {
        throw ArgumentError('Mensaje demasiado largo (máx. $_maxCuerpo)');
      }
      return {
        'id': p.id,
        'nombre': p.nombre.trim(),
        'cuerpo': p.cuerpo.trim(),
        'activa': p.activa,
        'orden': p.orden,
      };
    }).toList();

    await _empresaDoc.set({
      'version': 1,
      'plantillas': payload,
      'fecha_sync': FieldValue.serverTimestamp(),
    });
    _empresaCache = plantillas.where((p) => p.activa).toList()
      ..sort((a, b) => a.orden.compareTo(b.orden));
  }

  static String newEmpresaId() =>
      'wa_emp_${DateTime.now().millisecondsSinceEpoch.toRadixString(16)}';

  // ── Personales ───────────────────────────────────────────

  Future<List<WhatsAppPlantilla>> loadPersonales(
    String uid, {
    bool soloActivas = false,
  }) async {
    if (uid.isEmpty) return [];
    try {
      final snap = await _personalCol(uid).orderBy('orden').get();
      final list = snap.docs
          .map(
            (d) => WhatsAppPlantilla.fromMap(
              d.id,
              d.data(),
              origen: 'personal',
            ),
          )
          .toList();
      if (soloActivas) return list.where((p) => p.activa).toList();
      return list;
    } catch (_) {
      // Si falta índice compuesto, fallback sin orderBy.
      try {
        final snap = await _personalCol(uid).get();
        final list = snap.docs
            .map(
              (d) => WhatsAppPlantilla.fromMap(
                d.id,
                d.data(),
                origen: 'personal',
              ),
            )
            .toList()
          ..sort((a, b) => a.orden.compareTo(b.orden));
        if (soloActivas) return list.where((p) => p.activa).toList();
        return list;
      } catch (_) {
        return [];
      }
    }
  }

  Future<WhatsAppPlantilla> savePersonal(
    String uid,
    WhatsAppPlantilla plantilla,
  ) async {
    if (uid.isEmpty) throw ArgumentError('uid requerido');
    final nombre = plantilla.nombre.trim();
    final cuerpo = plantilla.cuerpo.trim();
    if (nombre.isEmpty) {
      throw ArgumentError('El nombre de la plantilla es obligatorio');
    }
    if (cuerpo.isEmpty) {
      throw ArgumentError('El cuerpo del mensaje es obligatorio');
    }
    if (nombre.length > _maxNombre) {
      throw ArgumentError('Nombre demasiado largo (máx. $_maxNombre)');
    }
    if (cuerpo.length > _maxCuerpo) {
      throw ArgumentError('Mensaje demasiado largo (máx. $_maxCuerpo)');
    }

    final col = _personalCol(uid);
    final id = plantilla.id.isNotEmpty ? plantilla.id : col.doc().id;
    final ref = col.doc(id);

    if (plantilla.predeterminada) {
      await _clearPredeterminada(uid, exceptId: id);
    }

    final data = {
      ...plantilla.copyWith(id: id, nombre: nombre, cuerpo: cuerpo).toMap(),
      'updated_at': FieldValue.serverTimestamp(),
    };
    final existing = await ref.get();
    if (!existing.exists) {
      data['created_at'] = FieldValue.serverTimestamp();
    }
    await ref.set(data, SetOptions(merge: true));
    return plantilla.copyWith(id: id, nombre: nombre, cuerpo: cuerpo);
  }

  Future<void> deletePersonal(String uid, String id) async {
    if (uid.isEmpty || id.isEmpty) return;
    await _personalCol(uid).doc(id).delete();
  }

  Future<void> _clearPredeterminada(
    String uid, {
    required String exceptId,
  }) async {
    final snap = await _personalCol(uid)
        .where('predeterminada', isEqualTo: true)
        .get();
    final batch = _db.batch();
    for (final d in snap.docs) {
      if (d.id == exceptId) continue;
      batch.update(d.reference, {'predeterminada': false});
    }
    if (snap.docs.any((d) => d.id != exceptId)) {
      await batch.commit();
    }
  }

  /// Activas personales + empresa, ordenadas: predeterminada, última usada, resto.
  Future<List<WhatsAppPlantilla>> loadActivasParaEnvio(String uid) async {
    final personales = await loadPersonales(uid, soloActivas: true);
    final empresa = await loadEmpresa(soloActivas: true);
    final combined = [...personales, ...empresa];
    final lastId = await getLastUsedId();
    combined.sort((a, b) {
      final aPred = a.predeterminada ? 0 : 1;
      final bPred = b.predeterminada ? 0 : 1;
      if (aPred != bPred) return aPred.compareTo(bPred);
      final aLast = (lastId != null && a.id == lastId) ? 0 : 1;
      final bLast = (lastId != null && b.id == lastId) ? 0 : 1;
      if (aLast != bLast) return aLast.compareTo(bLast);
      if (a.isPersonal != b.isPersonal) return a.isPersonal ? -1 : 1;
      return a.orden.compareTo(b.orden);
    });
    return combined;
  }

  Future<String?> getLastUsedId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_prefsLastIdKey);
  }

  Future<void> setLastUsedId(String id) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefsLastIdKey, id);
  }

  void clearEmpresaCache() => _empresaCache = [];
}
