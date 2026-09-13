import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/caso_model.dart';
import '../services/auth_service.dart';
import '../services/caso_service.dart';
import '../utils/caso_problema.dart';
import '../utils/responsive.dart';
import 'caso_detail_screen.dart';

/// Embudo kanban de casos de problema (resolutor / admin / supervisor).
class CasosFunnelScreen extends StatefulWidget {
  const CasosFunnelScreen({super.key});

  @override
  State<CasosFunnelScreen> createState() => _CasosFunnelScreenState();
}

class _CasosFunnelScreenState extends State<CasosFunnelScreen> {
  final _casoService = CasoService();
  String? _tipoFilter;
  String _mobileEtapa = 'nuevo';

  @override
  Widget build(BuildContext context) {
    final canManage =
        context.watch<AuthService>().profile?.canManageCasos ?? false;
    if (!canManage) {
      return const Scaffold(
        body: Center(child: Text('Sin permiso para ver el embudo de casos.')),
      );
    }

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Embudo de casos'),
        actions: [
          PopupMenuButton<String?>(
            tooltip: 'Filtrar tipo',
            initialValue: _tipoFilter,
            onSelected: (v) => setState(() => _tipoFilter = v),
            itemBuilder: (_) => [
              const PopupMenuItem(value: null, child: Text('Todos los tipos')),
              ...casoTipos.map(
                (t) => PopupMenuItem(
                  value: t,
                  child: Text(casoTipoLabel(t)),
                ),
              ),
            ],
            icon: Icon(
              Icons.filter_list,
              color: _tipoFilter != null ? AppTheme.warning : Colors.white,
            ),
          ),
        ],
      ),
      body: StreamBuilder<List<CasoModel>>(
        stream: _casoService.streamAll(limit: 400),
        builder: (context, snap) {
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }
          if (!snap.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          var casos = snap.data!;
          if (_tipoFilter != null) {
            casos = casos.where((c) => c.tipo == _tipoFilter).toList();
          }
          if (context.isCompact) {
            return _mobileLayout(casos);
          }
          return _desktopKanban(casos);
        },
      ),
    );
  }

  Widget _mobileLayout(List<CasoModel> casos) {
    final filtered =
        casos.where((c) => c.etapa == _mobileEtapa).toList();
    return Column(
      children: [
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
          child: Row(
            children: casoEtapas.map((e) {
              final count = casos.where((c) => c.etapa == e).length;
              final selected = e == _mobileEtapa;
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  label: Text('${casoEtapaLabel(e)} ($count)'),
                  selected: selected,
                  onSelected: (_) => setState(() => _mobileEtapa = e),
                ),
              );
            }).toList(),
          ),
        ),
        Expanded(
          child: filtered.isEmpty
              ? const Center(
                  child: Text(
                    'Sin casos en esta etapa',
                    style: TextStyle(color: AppTheme.textMuted),
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: filtered.length,
                  itemBuilder: (_, i) => _CasoCard(
                    caso: filtered[i],
                    onTap: () => _openDetail(filtered[i]),
                    onMove: (etapa) => _quickMove(filtered[i], etapa),
                  ),
                ),
        ),
      ],
    );
  }

  Widget _desktopKanban(List<CasoModel> casos) {
    final height = MediaQuery.sizeOf(context).height - 140;
    return Align(
      alignment: Alignment.topCenter,
      child: SizedBox(
        height: height.clamp(360, 900),
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: casoEtapas.map((etapa) {
              final col = casos.where((c) => c.etapa == etapa).toList();
              return Container(
                width: 280,
                margin: const EdgeInsets.only(right: 10),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              casoEtapaLabel(etapa),
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                                fontSize: 13,
                              ),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: AppTheme.primaryLight,
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Text(
                              '${col.length}',
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                                fontSize: 12,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Divider(height: 1),
                    Expanded(
                      child: col.isEmpty
                          ? const Padding(
                              padding: EdgeInsets.all(16),
                              child: Text(
                                'Vacío',
                                style: TextStyle(
                                  color: AppTheme.textMuted,
                                  fontSize: 12,
                                ),
                              ),
                            )
                          : ListView.builder(
                              padding: const EdgeInsets.all(8),
                              itemCount: col.length,
                              itemBuilder: (_, i) => _CasoCard(
                                caso: col[i],
                                onTap: () => _openDetail(col[i]),
                                onMove: (e) => _quickMove(col[i], e),
                              ),
                            ),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
        ),
      ),
    );
  }

  void _openDetail(CasoModel caso) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => CasoDetailScreen(
          casoId: caso.id,
          initialCaso: caso,
        ),
      ),
    );
  }

  Future<void> _quickMove(CasoModel caso, String etapa) async {
    final auth = context.read<AuthService>();
    try {
      await _casoService.moveEtapa(
        casoId: caso.id,
        nuevaEtapa: etapa,
        uid: auth.profile?.uid ?? auth.firebaseUser?.uid ?? '',
        nombre: auth.profile?.nombre ?? '',
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }
}

class _CasoCard extends StatelessWidget {
  final CasoModel caso;
  final VoidCallback onTap;
  final ValueChanged<String> onMove;

  const _CasoCard({
    required this.caso,
    required this.onTap,
    required this.onMove,
  });

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.getStatusColor(caso.tipo);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(color: AppTheme.border),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      caso.clienteNombre.isEmpty ? 'Sin nombre' : caso.clienteNombre,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 13,
                      ),
                    ),
                  ),
                  PopupMenuButton<String>(
                    icon: const Icon(Icons.more_vert, size: 18),
                    tooltip: 'Mover etapa',
                    onSelected: onMove,
                    itemBuilder: (_) => casoEtapas
                        .where((e) => e != caso.etapa)
                        .map(
                          (e) => PopupMenuItem(
                            value: e,
                            child: Text(casoEtapaLabel(e)),
                          ),
                        )
                        .toList(),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  caso.tipoLabel,
                  style: TextStyle(
                    color: color,
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'DNI ${caso.clienteDni.isEmpty ? '—' : caso.clienteDni}',
                style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
              ),
              Text(
                'S/ ${caso.deudaPendiente.toStringAsFixed(2)}'
                '${caso.gestorNombre.isNotEmpty ? ' · ${caso.gestorNombre}' : ''}',
                style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
