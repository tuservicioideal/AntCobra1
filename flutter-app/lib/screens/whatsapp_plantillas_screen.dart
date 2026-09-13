import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/whatsapp_plantilla.dart';
import '../services/auth_service.dart';
import '../services/whatsapp_plantilla_service.dart';
import '../utils/whatsapp_plantilla_renderer.dart';
import '../widgets/adaptive_sheet.dart';

/// CRUD de plantillas WhatsApp: personales (todos) y empresa (admin/supervisor).
class WhatsAppPlantillasScreen extends StatefulWidget {
  const WhatsAppPlantillasScreen({super.key});

  @override
  State<WhatsAppPlantillasScreen> createState() =>
      _WhatsAppPlantillasScreenState();
}

class _WhatsAppPlantillasScreenState extends State<WhatsAppPlantillasScreen>
    with SingleTickerProviderStateMixin {
  final _service = WhatsAppPlantillaService();
  late TabController _tabs;
  List<WhatsAppPlantilla> _personales = [];
  List<WhatsAppPlantilla> _empresa = [];
  bool _loading = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    _tabs.addListener(() {
      if (!_tabs.indexIsChanging) setState(() {});
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final uid = context.read<AuthService>().profile?.uid ?? '';
    final personales = await _service.loadPersonales(uid);
    final empresa = await _service.loadEmpresa(force: true, soloActivas: false);
    if (!mounted) return;
    setState(() {
      _personales = personales;
      _empresa = empresa;
      _loading = false;
    });
  }

  Future<void> _openEditor({
    WhatsAppPlantilla? existing,
    required bool isEmpresa,
  }) async {
    final canManage = context.read<AuthService>().canManageUsers;
    if (isEmpresa && !canManage) return;

    final nombreCtrl = TextEditingController(text: existing?.nombre ?? '');
    final cuerpoCtrl = TextEditingController(text: existing?.cuerpo ?? '');
    var activa = existing?.activa ?? true;
    var predeterminada = existing?.predeterminada ?? false;
    final sample = sampleWhatsAppPlaceholders();

    final saved = await AdaptiveSheet.show<bool>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModal) {
            void insertVar(String key) {
              final tag = '{$key}';
              final text = cuerpoCtrl.text;
              final sel = cuerpoCtrl.selection;
              final start = sel.isValid ? sel.start : text.length;
              final end = sel.isValid ? sel.end : text.length;
              final next = text.replaceRange(start, end, tag);
              cuerpoCtrl.value = TextEditingValue(
                text: next,
                selection: TextSelection.collapsed(offset: start + tag.length),
              );
              setModal(() {});
            }

            final preview = renderWhatsAppPlantilla(
              cuerpoCtrl.text,
              values: sample,
            );

            return SafeArea(
              child: SingleChildScrollView(
                padding: EdgeInsets.only(
                  left: 16,
                  right: 16,
                  top: 16,
                  bottom: MediaQuery.of(ctx).viewInsets.bottom + 16,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      existing == null
                          ? (isEmpresa
                              ? 'Nueva plantilla empresa'
                              : 'Nuevo mensaje')
                          : (isEmpresa
                              ? 'Editar plantilla empresa'
                              : 'Editar mensaje'),
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: nombreCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Nombre corto',
                        border: OutlineInputBorder(),
                        hintText: 'Ej. Primer contacto',
                      ),
                      maxLength: 80,
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: cuerpoCtrl,
                      onChanged: (_) => setModal(() {}),
                      maxLines: 5,
                      maxLength: 2000,
                      decoration: const InputDecoration(
                        labelText: 'Mensaje',
                        border: OutlineInputBorder(),
                        alignLabelWithHint: true,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Insertar dato del cliente',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: Colors.grey.shade700,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: whatsappPlantillaVariables.map((v) {
                        return ActionChip(
                          label: Text(
                            '{$v}',
                            style: const TextStyle(fontSize: 12),
                          ),
                          onPressed: () => insertVar(v),
                          visualDensity: VisualDensity.compact,
                        );
                      }).toList(),
                    ),
                    const SizedBox(height: 12),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.grey.shade100,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: Colors.grey.shade300),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Vista previa',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                              color: Colors.grey.shade600,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            preview,
                            style: const TextStyle(fontSize: 13),
                          ),
                        ],
                      ),
                    ),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Activa'),
                      value: activa,
                      onChanged: (v) => setModal(() => activa = v),
                    ),
                    if (!isEmpresa)
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Usar por defecto'),
                        subtitle: const Text(
                          'Se elige primero al abrir WhatsApp',
                        ),
                        value: predeterminada,
                        onChanged: (v) => setModal(() => predeterminada = v),
                      ),
                    const SizedBox(height: 8),
                    FilledButton(
                      onPressed: () => Navigator.pop(ctx, true),
                      child: const Text('Guardar'),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );

    if (saved != true || !mounted) return;

    final nombre = nombreCtrl.text.trim();
    final cuerpo = cuerpoCtrl.text.trim();
    if (nombre.isEmpty || cuerpo.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Nombre y mensaje son obligatorios')),
      );
      return;
    }

    setState(() => _saving = true);
    try {
      if (isEmpresa) {
        final id = existing?.id.isNotEmpty == true
            ? existing!.id
            : WhatsAppPlantillaService.newEmpresaId();
        final next = List<WhatsAppPlantilla>.from(_empresa);
        final item = WhatsAppPlantilla(
          id: id,
          nombre: nombre,
          cuerpo: cuerpo,
          activa: activa,
          orden: existing?.orden ?? next.length,
          origen: 'empresa',
        );
        final idx = next.indexWhere((p) => p.id == id);
        if (idx >= 0) {
          next[idx] = item;
        } else {
          next.add(item);
        }
        next.sort((a, b) => a.orden.compareTo(b.orden));
        await _service.publishEmpresa(next);
        if (mounted) setState(() => _empresa = next);
      } else {
        final uid = context.read<AuthService>().profile?.uid ?? '';
        final savedItem = await _service.savePersonal(
          uid,
          WhatsAppPlantilla(
            id: existing?.id ?? '',
            nombre: nombre,
            cuerpo: cuerpo,
            activa: activa,
            orden: existing?.orden ?? _personales.length,
            predeterminada: predeterminada,
            origen: 'personal',
          ),
        );
        if (!mounted) return;
        setState(() {
          final idx = _personales.indexWhere((p) => p.id == savedItem.id);
          if (idx >= 0) {
            _personales[idx] = savedItem;
          } else {
            _personales.add(savedItem);
          }
          if (predeterminada) {
            _personales = _personales
                .map(
                  (p) => p.id == savedItem.id
                      ? p
                      : p.copyWith(predeterminada: false),
                )
                .toList();
          }
          _personales.sort((a, b) => a.orden.compareTo(b.orden));
        });
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Plantilla guardada')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error al guardar: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _deletePersonal(WhatsAppPlantilla p) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Eliminar mensaje'),
        content: Text('¿Eliminar "${p.nombre}"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Eliminar'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    final uid = context.read<AuthService>().profile?.uid ?? '';
    setState(() => _saving = true);
    try {
      await _service.deletePersonal(uid, p.id);
      if (mounted) {
        setState(() => _personales.removeWhere((x) => x.id == p.id));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('No se pudo eliminar: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _deactivateEmpresa(WhatsAppPlantilla p) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Desactivar plantilla'),
        content: Text('¿Desactivar "${p.nombre}"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Desactivar'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    setState(() => _saving = true);
    try {
      final next = _empresa
          .map((x) => x.id == p.id ? x.copyWith(activa: false) : x)
          .toList();
      await _service.publishEmpresa(next);
      if (mounted) setState(() => _empresa = next);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _list({
    required List<WhatsAppPlantilla> items,
    required bool isEmpresa,
    required bool canEdit,
  }) {
    if (_loading) {
      return const Center(
        child: CircularProgressIndicator(color: AppTheme.primaryColor),
      );
    }
    if (items.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.chat_bubble_outline,
                size: 48,
                color: Colors.grey.shade400,
              ),
              const SizedBox(height: 12),
              Text(
                isEmpresa
                    ? (canEdit
                        ? 'No hay plantillas de empresa. Crea la primera.'
                        : 'Aún no hay plantillas de empresa publicadas.')
                    : 'Crea tus mensajes automáticos para WhatsApp.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey.shade700),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 88),
        itemCount: items.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (context, i) {
          final p = items[i];
          final preview = renderWhatsAppPlantilla(
            p.cuerpo,
            values: sampleWhatsAppPlaceholders(),
          );
          return Card(
            child: ListTile(
              contentPadding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
              title: Row(
                children: [
                  Expanded(
                    child: Text(
                      p.nombre,
                      style: TextStyle(
                        fontWeight: FontWeight.w700,
                        decoration:
                            p.activa ? null : TextDecoration.lineThrough,
                      ),
                    ),
                  ),
                  if (p.predeterminada)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: AppTheme.primaryColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: const Text(
                        'Default',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.primaryColor,
                        ),
                      ),
                    ),
                ],
              ),
              subtitle: Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  [
                    if (!p.activa) 'Inactiva',
                    preview,
                  ].where((s) => s.isNotEmpty).join(' · '),
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
                ),
              ),
              trailing: canEdit
                  ? PopupMenuButton<String>(
                      onSelected: (v) {
                        if (v == 'edit') {
                          _openEditor(existing: p, isEmpresa: isEmpresa);
                        } else if (v == 'delete' && !isEmpresa) {
                          _deletePersonal(p);
                        } else if (v == 'deactivate' &&
                            isEmpresa &&
                            p.activa) {
                          _deactivateEmpresa(p);
                        }
                      },
                      itemBuilder: (_) => [
                        const PopupMenuItem(
                          value: 'edit',
                          child: Text('Editar'),
                        ),
                        if (isEmpresa && p.activa)
                          const PopupMenuItem(
                            value: 'deactivate',
                            child: Text('Desactivar'),
                          ),
                        if (!isEmpresa)
                          const PopupMenuItem(
                            value: 'delete',
                            child: Text('Eliminar'),
                          ),
                      ],
                    )
                  : null,
              onTap: canEdit
                  ? () => _openEditor(existing: p, isEmpresa: isEmpresa)
                  : null,
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final canManage = context.watch<AuthService>().canManageUsers;
    final isEmpresaTab = _tabs.index == 1;
    final showFab = !isEmpresaTab || canManage;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Mensajes WhatsApp'),
        bottom: TabBar(
          controller: _tabs,
          onTap: (_) => setState(() {}),
          tabs: const [
            Tab(text: 'Mis mensajes'),
            Tab(text: 'Empresa'),
          ],
        ),
        actions: [
          if (_saving)
            const Padding(
              padding: EdgeInsets.all(16),
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              ),
            )
          else
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _load,
              tooltip: 'Actualizar',
            ),
        ],
      ),
      floatingActionButton: showFab
          ? FloatingActionButton.extended(
              onPressed: _saving
                  ? null
                  : () => _openEditor(isEmpresa: isEmpresaTab),
              icon: const Icon(Icons.add),
              label: Text(isEmpresaTab ? 'Nueva empresa' : 'Nuevo'),
              backgroundColor: AppTheme.primaryColor,
            )
          : null,
      body: TabBarView(
        controller: _tabs,
        children: [
          _list(items: _personales, isEmpresa: false, canEdit: true),
          _list(
            items: _empresa,
            isEmpresa: true,
            canEdit: canManage,
          ),
        ],
      ),
    );
  }
}
