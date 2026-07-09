import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../services/auth_service.dart';
import '../services/etiqueta_catalog_service.dart';

const _presetColors = [
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
  '#EC4899', '#06B6D4', '#84CC16', '#F97316', '#6366F1',
];

/// CRUD del catálogo global de etiquetas (admin / supervisor).
class EtiquetasAdminScreen extends StatefulWidget {
  const EtiquetasAdminScreen({super.key});

  @override
  State<EtiquetasAdminScreen> createState() => _EtiquetasAdminScreenState();
}

class _EtiquetasAdminScreenState extends State<EtiquetasAdminScreen> {
  final _catalog = EtiquetaCatalogService();
  List<EtiquetaDef> _items = [];
  bool _loading = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final list = await _catalog.loadCatalogoAdmin(force: true);
    if (mounted) {
      setState(() {
        _items = list;
        _loading = false;
      });
    }
  }

  Future<void> _persist() async {
    setState(() => _saving = true);
    try {
      await _catalog.publishCatalogo(_items);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Catálogo publicado correctamente')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error al publicar: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _openEditor({EtiquetaDef? existing}) async {
    final nombreCtrl = TextEditingController(text: existing?.nombre ?? '');
    final descCtrl = TextEditingController(text: existing?.descripcion ?? '');
    final ordenCtrl = TextEditingController(
      text: '${existing?.orden ?? _items.length}',
    );
    var colorHex = existing?.colorHex ?? '#3B82F6';
    var activa = existing?.activa ?? true;

    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModal) {
            return Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 16,
                bottom: MediaQuery.of(ctx).viewInsets.bottom + 16,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    existing == null ? 'Nueva etiqueta' : 'Editar etiqueta',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: nombreCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Nombre',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    children: _presetColors.map((hex) {
                      final selected = colorHex == hex;
                      return GestureDetector(
                        onTap: () => setModal(() => colorHex = hex),
                        child: Container(
                          width: 32,
                          height: 32,
                          decoration: BoxDecoration(
                            color: _colorFromHex(hex),
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: selected ? Colors.black : Colors.transparent,
                              width: 2,
                            ),
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: ordenCtrl,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Orden',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: descCtrl,
                    maxLines: 2,
                    decoration: const InputDecoration(
                      labelText: 'Descripción (opcional)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Activa'),
                    value: activa,
                    onChanged: (v) => setModal(() => activa = v),
                  ),
                  FilledButton(
                    onPressed: () => Navigator.pop(ctx, true),
                    child: const Text('Guardar'),
                  ),
                ],
              ),
            );
          },
        );
      },
    );

    if (saved != true || !mounted) return;

    final nombre = nombreCtrl.text.trim();
    if (nombre.isEmpty) return;

    final orden = int.tryParse(ordenCtrl.text.trim()) ?? 0;
    final color = _colorFromHex(colorHex);

    setState(() {
      if (existing != null) {
        final idx = _items.indexWhere((e) => e.id == existing.id);
        if (idx >= 0) {
          _items[idx] = existing.copyWith(
            nombre: nombre,
            color: color,
            descripcion: descCtrl.text.trim(),
            activa: activa,
            orden: orden,
          );
        }
      } else {
        _items.add(EtiquetaDef(
          id: EtiquetaCatalogService.newEtiquetaId(),
          nombre: nombre,
          color: color,
          descripcion: descCtrl.text.trim(),
          activa: activa,
          orden: orden,
        ));
      }
      _items.sort((a, b) => a.orden.compareTo(b.orden));
    });

    await _persist();
  }

  Color _colorFromHex(String hex) {
    try {
      final h = hex.replaceFirst('#', '');
      return Color(int.parse('FF$h', radix: 16));
    } catch (_) {
      return const Color(0xFF3B82F6);
    }
  }

  Future<void> _deactivate(EtiquetaDef tag) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Desactivar etiqueta'),
        content: Text('¿Desactivar "${tag.nombre}"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Desactivar')),
        ],
      ),
    );
    if (ok != true) return;

    setState(() {
      final idx = _items.indexWhere((e) => e.id == tag.id);
      if (idx >= 0) _items[idx] = tag.copyWith(activa: false);
    });
    await _persist();
  }

  @override
  Widget build(BuildContext context) {
    final canManage = context.watch<AuthService>().canManageUsers;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Etiquetas de seguimiento'),
        actions: [
          if (_saving)
            const Padding(
              padding: EdgeInsets.all(16),
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
              ),
            )
          else
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _load,
            ),
        ],
      ),
      floatingActionButton: canManage
          ? FloatingActionButton.extended(
              onPressed: _saving ? null : () => _openEditor(),
              icon: const Icon(Icons.add),
              label: const Text('Nueva'),
              backgroundColor: AppTheme.primaryColor,
            )
          : null,
      body: !canManage
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Solo administradores y supervisores pueden gestionar etiquetas.',
                  textAlign: TextAlign.center,
                ),
              ),
            )
          : _loading
              ? const Center(child: CircularProgressIndicator(color: AppTheme.primaryColor))
              : _items.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.label_off_outlined, size: 48, color: Colors.grey.shade400),
                          const SizedBox(height: 12),
                          const Text('No hay etiquetas. Crea la primera.'),
                        ],
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.separated(
                        padding: const EdgeInsets.fromLTRB(12, 12, 12, 88),
                        itemCount: _items.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 8),
                        itemBuilder: (context, i) {
                          final tag = _items[i];
                          return Card(
                            child: ListTile(
                              leading: CircleAvatar(
                                backgroundColor: tag.color.withValues(alpha: 0.2),
                                child: Icon(Icons.label, color: tag.color, size: 20),
                              ),
                              title: Text(
                                tag.nombre,
                                style: TextStyle(
                                  decoration: tag.activa ? null : TextDecoration.lineThrough,
                                ),
                              ),
                              subtitle: Text(
                                [
                                  if (!tag.activa) 'Inactiva',
                                  if (tag.descripcion.isNotEmpty) tag.descripcion,
                                  'Orden ${tag.orden}',
                                ].where((s) => s.isNotEmpty).join(' · '),
                              ),
                              trailing: PopupMenuButton<String>(
                                onSelected: (v) {
                                  if (v == 'edit') {
                                    _openEditor(existing: tag);
                                  } else if (v == 'deactivate' && tag.activa) {
                                    _deactivate(tag);
                                  }
                                },
                                itemBuilder: (_) => [
                                  const PopupMenuItem(value: 'edit', child: Text('Editar')),
                                  if (tag.activa)
                                    const PopupMenuItem(
                                      value: 'deactivate',
                                      child: Text('Desactivar'),
                                    ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
