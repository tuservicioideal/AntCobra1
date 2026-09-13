import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config/theme.dart';
import '../models/caso_model.dart';
import '../models/client_model.dart';
import '../services/auth_service.dart';
import '../services/caso_service.dart';
import '../services/firestore_service.dart';
import '../utils/caso_problema.dart';
import '../utils/responsive.dart';
import 'client_detail_screen.dart';

/// Detalle de un caso: ficha, etapa, comentarios y timeline.
class CasoDetailScreen extends StatefulWidget {
  final String casoId;
  final CasoModel? initialCaso;

  const CasoDetailScreen({
    super.key,
    required this.casoId,
    this.initialCaso,
  });

  @override
  State<CasoDetailScreen> createState() => _CasoDetailScreenState();
}

class _CasoDetailScreenState extends State<CasoDetailScreen> {
  final _casoService = CasoService();
  final _firestore = FirestoreService();
  final _commentCtrl = TextEditingController();
  CasoModel? _caso;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _caso = widget.initialCaso;
    _load();
  }

  @override
  void dispose() {
    _commentCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final c = await _casoService.getCaso(widget.casoId);
      if (mounted) {
        setState(() {
          _caso = c;
          _loading = false;
          if (c == null) _error = 'Caso no encontrado';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = '$e';
        });
      }
    }
  }

  Future<void> _moveEtapa(String nueva) async {
    final caso = _caso;
    if (caso == null) return;
    String motivo = '';
    if (isEtapaCerrada(nueva)) {
      final ctrl = TextEditingController();
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('Mover a ${casoEtapaLabel(nueva)}'),
          content: TextField(
            controller: ctrl,
            decoration: const InputDecoration(
              labelText: 'Motivo (opcional)',
              border: OutlineInputBorder(),
            ),
            maxLines: 3,
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Confirmar'),
            ),
          ],
        ),
      );
      if (ok != true) return;
      motivo = ctrl.text.trim();
      ctrl.dispose();
    }

    if (!mounted) return;
    final auth = context.read<AuthService>();
    setState(() => _saving = true);
    try {
      await _casoService.moveEtapa(
        casoId: caso.id,
        nuevaEtapa: nueva,
        uid: auth.profile?.uid ?? auth.firebaseUser?.uid ?? '',
        nombre: auth.profile?.nombre ?? '',
        motivo: motivo,
      );
      await _load();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Movido a ${casoEtapaLabel(nueva)}')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _sendComment() async {
    final text = _commentCtrl.text.trim();
    if (text.isEmpty || _caso == null) return;
    final auth = context.read<AuthService>();
    setState(() => _saving = true);
    try {
      await _casoService.addComentario(
        casoId: _caso!.id,
        texto: text,
        uid: auth.profile?.uid ?? auth.firebaseUser?.uid ?? '',
        nombre: auth.profile?.nombre ?? '',
      );
      _commentCtrl.clear();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _openClientFicha() async {
    final caso = _caso;
    if (caso == null || caso.campaniaId.isEmpty || caso.clienteId.isEmpty) {
      return;
    }
    setState(() => _saving = true);
    try {
      final section = caso.seccionKey.isNotEmpty ? caso.seccionKey : caso.seccion;
      final loaded = await _firestore.getClient(
        campaignId: caso.campaniaId,
        section: section,
        clientId: caso.clienteId,
      );
      ClientModel client;
      if (loaded != null) {
        client = loaded;
      } else {
        client = ClientModel(
          id: caso.clienteId,
          campaignId: caso.campaniaId,
          codigoCliente: caso.clienteCodigo,
          nombreCompleto: caso.clienteNombre,
          numeroDocumento: caso.clienteDni,
          telefonoMovil: caso.telefono,
          direccion: caso.direccion,
          distrito: caso.distrito,
          seccion: section,
          seccionKey: section,
          importeDeudaAsignada: caso.deudaAsignada,
          importeDeudaPendiente: caso.deudaPendiente,
          campanaBanco: caso.campanaBanco,
        );
      }
      if (!mounted) return;
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ClientDetailScreen(
            client: client,
            campaignId: caso.campaniaId,
            section: section,
            readOnly: true,
          ),
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('No se pudo abrir ficha: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _openMaps() async {
    final caso = _caso;
    if (caso?.gpsLatitud == null || caso?.gpsLongitud == null) return;
    final uri = Uri.parse(
      'https://www.google.com/maps/search/?api=1&query=${caso!.gpsLatitud},${caso.gpsLongitud}',
    );
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    final caso = _caso;
    final fmt = DateFormat('dd/MM/yyyy HH:mm');

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: Text(
          caso?.clienteNombre.isNotEmpty == true
              ? caso!.clienteNombre
              : 'Detalle del caso',
        ),
      ),
      body: _loading && caso == null
          ? const Center(child: CircularProgressIndicator())
          : _error != null && caso == null
              ? Center(child: Text(_error!))
              : caso == null
                  ? const SizedBox.shrink()
                  : Align(
                      alignment: Alignment.topCenter,
                      child: ConstrainedBox(
                        constraints: BoxConstraints(
                          maxWidth: context.isExpanded
                              ? ResponsiveBreakpoints.contentMax
                              : double.infinity,
                        ),
                        child: ListView(
                          padding: const EdgeInsets.all(16),
                          children: [
                            _headerCard(caso, fmt),
                            const SizedBox(height: 12),
                            _etapaCard(caso),
                            const SizedBox(height: 12),
                            _actionsRow(),
                            const SizedBox(height: 16),
                            _comentariosSection(),
                            const SizedBox(height: 16),
                            _movimientosSection(fmt),
                          ],
                        ),
                      ),
                    ),
    );
  }

  Widget _headerCard(CasoModel caso, DateFormat fmt) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _chip(caso.tipoLabel, AppTheme.getStatusColor(caso.tipo)),
              _chip(caso.etapaLabel, AppTheme.primary),
              if (!caso.abierto)
                _chip('Cerrado', AppTheme.textMuted),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            caso.clienteNombre,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'DNI ${caso.clienteDni.isEmpty ? '—' : caso.clienteDni}'
            '${caso.clienteCodigo.isNotEmpty ? ' · Cód. ${caso.clienteCodigo}' : ''}',
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
          ),
          if (caso.telefono.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text('Tel: ${caso.telefono}',
                style: const TextStyle(fontSize: 13)),
          ],
          if (caso.direccion.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              '${caso.direccion}${caso.distrito.isNotEmpty ? ', ${caso.distrito}' : ''}',
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
            ),
          ],
          const SizedBox(height: 8),
          Text(
            'Deuda: S/ ${caso.deudaPendiente.toStringAsFixed(2)}'
            ' (asig. ${caso.deudaAsignada.toStringAsFixed(2)})',
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
          ),
          const SizedBox(height: 8),
          Text(
            'Gestor: ${caso.gestorNombre.isEmpty ? '—' : caso.gestorNombre}'
            '${caso.seccion.isNotEmpty ? ' · ${caso.seccion}' : ''}',
            style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
          ),
          if (caso.fechaApertura != null)
            Text(
              'Apertura: ${fmt.format(caso.fechaApertura!)}',
              style: const TextStyle(fontSize: 12, color: AppTheme.textMuted),
            ),
          if (caso.notaOrigen.isNotEmpty) ...[
            const SizedBox(height: 10),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.primaryLight,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                'Nota del gestor: ${caso.notaOrigen}',
                style: const TextStyle(fontSize: 13),
              ),
            ),
          ],
          if (caso.gpsLatitud != null && caso.gpsLongitud != null) ...[
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: _openMaps,
              icon: const Icon(Icons.map_outlined, size: 18),
              label: Text(
                'GPS ${caso.gpsLatitud!.toStringAsFixed(5)}, '
                '${caso.gpsLongitud!.toStringAsFixed(5)}',
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _etapaCard(CasoModel caso) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Mover etapa',
            style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: casoEtapas
                .where((e) => e != caso.etapa)
                .map(
                  (e) => ActionChip(
                    label: Text(casoEtapaLabel(e)),
                    onPressed: _saving ? null : () => _moveEtapa(e),
                    backgroundColor: AppTheme.primaryLight,
                  ),
                )
                .toList(),
          ),
        ],
      ),
    );
  }

  Widget _actionsRow() {
    return OutlinedButton.icon(
      onPressed: _saving ? null : _openClientFicha,
      icon: const Icon(Icons.person_search_outlined),
      label: const Text('Ver ficha de cartera (solo lectura)'),
    );
  }

  Widget _comentariosSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Comentarios',
          style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
        ),
        const SizedBox(height: 8),
        StreamBuilder<List<CasoComentario>>(
          stream: _casoService.streamComentarios(widget.casoId),
          builder: (context, snap) {
            final list = snap.data ?? [];
            if (list.isEmpty) {
              return const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: Text(
                  'Sin comentarios aún.',
                  style: TextStyle(color: AppTheme.textMuted, fontSize: 13),
                ),
              );
            }
            return Column(
              children: list
                  .map(
                    (c) => Container(
                      width: double.infinity,
                      margin: const EdgeInsets.only(bottom: 8),
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: AppTheme.surface,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: AppTheme.border),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            c.nombre.isEmpty ? 'Usuario' : c.nombre,
                            style: const TextStyle(
                              fontWeight: FontWeight.w600,
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(c.texto, style: const TextStyle(fontSize: 13)),
                        ],
                      ),
                    ),
                  )
                  .toList(),
            );
          },
        ),
        const SizedBox(height: 8),
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                controller: _commentCtrl,
                minLines: 1,
                maxLines: 3,
                decoration: const InputDecoration(
                  hintText: 'Agregar comentario…',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(
              onPressed: _saving ? null : _sendComment,
              icon: const Icon(Icons.send),
            ),
          ],
        ),
      ],
    );
  }

  Widget _movimientosSection(DateFormat fmt) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Histororial de movimientos',
          style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
        ),
        const SizedBox(height: 8),
        StreamBuilder<List<CasoMovimiento>>(
          stream: _casoService.streamMovimientos(widget.casoId),
          builder: (context, snap) {
            final list = snap.data ?? [];
            if (list.isEmpty) {
              return const Text(
                'Sin movimientos.',
                style: TextStyle(color: AppTheme.textMuted, fontSize: 13),
              );
            }
            return Column(
              children: list.map((m) {
                final de = m.de.isEmpty ? '—' : casoEtapaLabel(m.de);
                final a = casoEtapaLabel(m.a);
                final when = m.fecha != null ? fmt.format(m.fecha!) : '';
                return ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.swap_vert, size: 20),
                  title: Text('$de → $a', style: const TextStyle(fontSize: 13)),
                  subtitle: Text(
                    [
                      if (m.nombre.isNotEmpty) m.nombre,
                      if (m.motivo.isNotEmpty) m.motivo,
                      if (when.isNotEmpty) when,
                    ].join(' · '),
                    style: const TextStyle(fontSize: 11),
                  ),
                );
              }).toList(),
            );
          },
        ),
      ],
    );
  }

  Widget _chip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
