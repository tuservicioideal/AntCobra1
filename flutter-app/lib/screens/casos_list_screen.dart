import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/caso_model.dart';
import '../services/auth_service.dart';
import '../services/caso_service.dart';
import '../utils/caso_problema.dart';
import 'caso_detail_screen.dart';

/// Lista filtrable de todos los casos (resolutor).
class CasosListScreen extends StatefulWidget {
  const CasosListScreen({super.key});

  @override
  State<CasosListScreen> createState() => _CasosListScreenState();
}

class _CasosListScreenState extends State<CasosListScreen> {
  final _casoService = CasoService();
  final _searchCtrl = TextEditingController();
  String? _tipoFilter;
  String? _etapaFilter;
  String _query = '';

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final canManage =
        context.watch<AuthService>().profile?.canManageCasos ?? false;
    if (!canManage) {
      return const Scaffold(
        body: Center(child: Text('Sin permiso para ver casos.')),
      );
    }

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(title: const Text('Casos')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
            child: TextField(
              controller: _searchCtrl,
              decoration: InputDecoration(
                hintText: 'Buscar nombre, DNI, gestor…',
                prefixIcon: const Icon(Icons.search),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
                isDense: true,
                filled: true,
                fillColor: AppTheme.surface,
              ),
              onChanged: (v) => setState(() => _query = v.trim().toLowerCase()),
            ),
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
            child: Row(
              children: [
                FilterChip(
                  label: const Text('Todos'),
                  selected: _tipoFilter == null && _etapaFilter == null,
                  onSelected: (_) => setState(() {
                    _tipoFilter = null;
                    _etapaFilter = null;
                  }),
                ),
                const SizedBox(width: 6),
                ...casoTipos.map(
                  (t) => Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: FilterChip(
                      label: Text(casoTipoLabel(t)),
                      selected: _tipoFilter == t,
                      onSelected: (sel) => setState(() {
                        _tipoFilter = sel ? t : null;
                      }),
                    ),
                  ),
                ),
              ],
            ),
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
            child: Row(
              children: casoEtapas
                  .map(
                    (e) => Padding(
                      padding: const EdgeInsets.only(right: 6),
                      child: FilterChip(
                        label: Text(casoEtapaLabel(e)),
                        selected: _etapaFilter == e,
                        onSelected: (sel) => setState(() {
                          _etapaFilter = sel ? e : null;
                        }),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ),
          Expanded(
            child: StreamBuilder<List<CasoModel>>(
              stream: _casoService.streamAll(limit: 500),
              builder: (context, snap) {
                if (snap.hasError) {
                  return Center(child: Text('Error: ${snap.error}'));
                }
                if (!snap.hasData) {
                  return const Center(child: CircularProgressIndicator());
                }
                var list = snap.data!;
                if (_tipoFilter != null) {
                  list = list.where((c) => c.tipo == _tipoFilter).toList();
                }
                if (_etapaFilter != null) {
                  list = list.where((c) => c.etapa == _etapaFilter).toList();
                }
                if (_query.isNotEmpty) {
                  list = list.where((c) {
                    final blob = [
                      c.clienteNombre,
                      c.clienteDni,
                      c.gestorNombre,
                      c.clienteCodigo,
                      c.tipoLabel,
                    ].join(' ').toLowerCase();
                    return blob.contains(_query);
                  }).toList();
                }
                if (list.isEmpty) {
                  return const Center(
                    child: Text(
                      'No hay casos con estos filtros',
                      style: TextStyle(color: AppTheme.textMuted),
                    ),
                  );
                }
                return ListView.separated(
                  padding: const EdgeInsets.fromLTRB(12, 0, 12, 16),
                  itemCount: list.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 6),
                  itemBuilder: (_, i) {
                    final c = list[i];
                    return ListTile(
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                        side: const BorderSide(color: AppTheme.border),
                      ),
                      tileColor: AppTheme.surface,
                      title: Text(
                        c.clienteNombre.isEmpty ? 'Sin nombre' : c.clienteNombre,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      subtitle: Text(
                        '${c.tipoLabel} · ${c.etapaLabel}\n'
                        'DNI ${c.clienteDni.isEmpty ? '—' : c.clienteDni}'
                        '${c.gestorNombre.isNotEmpty ? ' · ${c.gestorNombre}' : ''}',
                      ),
                      isThreeLine: true,
                      trailing: Icon(
                        c.abierto ? Icons.circle : Icons.check_circle,
                        size: 14,
                        color: c.abierto ? AppTheme.warning : AppTheme.success,
                      ),
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => CasoDetailScreen(
                              casoId: c.id,
                              initialCaso: c,
                            ),
                          ),
                        );
                      },
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
