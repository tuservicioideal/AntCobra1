import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';
import '../config/theme.dart';
import '../models/user_model.dart';
import '../services/auth_service.dart';
import '../services/campaign_service.dart';
import '../services/firestore_service.dart';
import '../services/user_admin_service.dart';
import '../utils/territorial_utils.dart';
import '../utils/user_admin_utils.dart';
import '../utils/responsive.dart';
import '../widgets/multi_territorial_section_picker.dart';

/// Admin screen for user CRUD management (parity with admin-app TeamPage).
class AdminScreen extends StatefulWidget {
  const AdminScreen({super.key});

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  final _firestoreService = FirestoreService();
  final _campaignService = CampaignService();
  final _userAdminService = UserAdminService();
  final _searchController = TextEditingController();

  List<String> _availableSections = [];
  Map<String, dynamic> _catalog = {};
  bool _sectionsLoading = true;
  bool _saving = false;
  String _searchQuery = '';
  String? _roleFilter;
  int _sortColumnIndex = 0;
  bool _sortAscending = true;
  StreamSubscription<List<UserModel>>? _usersSub;
  List<UserModel> _users = [];

  @override
  void initState() {
    super.initState();
    _loadSections();
    _usersSub = _firestoreService.streamUsers().listen(
      (users) {
        if (mounted) setState(() => _users = users);
      },
      onError: (e) {
        debugPrint('Error streaming users: $e');
      },
    );
  }

  @override
  void dispose() {
    _searchController.dispose();
    _usersSub?.cancel();
    super.dispose();
  }

  Future<void> _loadSections() async {
    setState(() => _sectionsLoading = true);
    final campaignId = await _campaignService.getActiveCampaignId();
    if (campaignId != null) {
      _availableSections =
          await _campaignService.getAvailableSections(campaignId);
    } else {
      _availableSections = [];
    }
    _catalog = await _firestoreService.getEstructuraTerritorial();
    if (mounted) setState(() => _sectionsLoading = false);
  }

  List<UserModel> get _filteredUsers {
    var list = _users;
    if (_roleFilter == 'call') {
      list = list.where((u) => u.isCallGestor).toList();
    } else if (_roleFilter != null && _roleFilter!.isNotEmpty) {
      list = list.where((u) => u.rol == _roleFilter).toList();
    }
    if (_searchQuery.isEmpty) return list;
    final q = _searchQuery.toLowerCase();
    return list.where((u) {
      return u.nombre.toLowerCase().contains(q) ||
          u.email.toLowerCase().contains(q) ||
          u.seccion.toLowerCase().contains(q) ||
          u.region.toLowerCase().contains(q) ||
          u.zona.toLowerCase().contains(q);
    }).toList();
  }

  List<UserModel> _sortedUsers(List<UserModel> users) {
    final sorted = List<UserModel>.from(users);
    sorted.sort((a, b) {
      int cmp;
      switch (_sortColumnIndex) {
        case 1:
          cmp = a.email.compareTo(b.email);
        case 2:
          cmp = a.rol.compareTo(b.rol);
        case 3:
          cmp = userTerritorialLabel(a).compareTo(userTerritorialLabel(b));
        case 4:
          cmp = a.activo == b.activo ? 0 : (a.activo ? -1 : 1);
        default:
          cmp = (a.nombre.isNotEmpty ? a.nombre : a.email)
              .compareTo(b.nombre.isNotEmpty ? b.nombre : b.email);
      }
      return _sortAscending ? cmp : -cmp;
    });
    return sorted;
  }

  void _showSnack(String message, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? Colors.red.shade700 : null,
      ),
    );
  }

  Future<void> _toggleActivo(UserModel user) async {
    if (user.uid.isEmpty) {
      _showSnack('Usuario sin UID válido.', isError: true);
      return;
    }
    setState(() => _saving = true);
    try {
      await _userAdminService.updateGestorUser(
        uid: user.uid,
        updates: {'activo': !user.activo},
      );
      _showSnack(user.activo ? '${user.nombre} desactivado' : '${user.nombre} activado');
    } catch (e) {
      _showSnack(e.toString().replaceFirst('Exception: ', ''), isError: true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();
    if (!auth.canManageUsers) {
      return Scaffold(
        appBar: AppBar(title: const Text('Usuarios y roles')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.lock_outline, size: 56, color: Colors.grey.shade400),
                const SizedBox(height: 16),
                Text(
                  'Acceso restringido',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Solo administradores y supervisores pueden gestionar usuarios.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.grey.shade600),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final filtered = _sortedUsers(_filteredUsers);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Usuarios y roles'),
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
            ),
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            tooltip: 'Actualizar catálogo y secciones',
            onPressed: _saving ? null : _loadSections,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _saving ? null : () => _showUserDialog(null),
        backgroundColor: AppTheme.primaryColor,
        icon: const Icon(Icons.person_add, color: Colors.white),
        label: const Text('Nuevo', style: TextStyle(color: Colors.white)),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Column(
              children: [
                TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: 'Buscar por nombre, email o sección…',
                    prefixIcon: const Icon(Icons.search, size: 20),
                    suffixIcon: _searchQuery.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear, size: 18),
                            onPressed: () {
                              _searchController.clear();
                              setState(() => _searchQuery = '');
                            },
                          )
                        : null,
                    filled: true,
                    fillColor: Colors.grey.shade50,
                  ),
                  onChanged: (v) => setState(() => _searchQuery = v),
                ),
                const SizedBox(height: 8),
                context.isExpanded
                    ? Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          _buildRoleChip(null, 'Todos'),
                          _buildRoleChip('gestor', 'Gestor'),
                          _buildRoleChip('call', 'Call'),
                          _buildRoleChip('asistente', 'Asistente'),
                          _buildRoleChip('supervisor', 'Supervisor'),
                          _buildRoleChip('admin', 'Admin'),
                        ],
                      )
                    : SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            _buildRoleChip(null, 'Todos'),
                            _buildRoleChip('gestor', 'Gestor'),
                            _buildRoleChip('call', 'Call'),
                            _buildRoleChip('asistente', 'Asistente'),
                            _buildRoleChip('supervisor', 'Supervisor'),
                            _buildRoleChip('admin', 'Admin'),
                          ],
                        ),
                      ),
              ],
            ),
          ),
          Expanded(
            child: _sectionsLoading && _users.isEmpty
                ? const Center(
                    child: CircularProgressIndicator(
                      color: AppTheme.primaryColor,
                    ),
                  )
                : RefreshIndicator(
                    onRefresh: _loadSections,
                    color: AppTheme.primaryColor,
                    child: filtered.isEmpty
                        ? ListView(
                            physics: const AlwaysScrollableScrollPhysics(),
                            children: [
                              SizedBox(
                                height:
                                    MediaQuery.sizeOf(context).height * 0.25,
                              ),
                              Center(
                                child: Column(
                                  children: [
                                    Icon(Icons.group_outlined,
                                        size: 64,
                                        color: Colors.grey.shade300),
                                    const SizedBox(height: 16),
                                    Text(
                                      _users.isEmpty
                                          ? 'No hay usuarios'
                                          : 'Sin resultados para la búsqueda',
                                      style: TextStyle(
                                          color: Colors.grey.shade500),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          )
                        : context.isExpanded
                            ? SingleChildScrollView(
                                physics: const AlwaysScrollableScrollPhysics(),
                                child: _buildUsersDataTable(filtered),
                              )
                            : ListView.builder(
                            padding: const EdgeInsets.all(16),
                            itemCount: filtered.length,
                            itemBuilder: (context, index) {
                              final user = filtered[index];
                              return _buildUserCard(user, index);
                            },
                          ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildUsersDataTable(List<UserModel> users) {
    return DataTable(
      sortColumnIndex: _sortColumnIndex,
      sortAscending: _sortAscending,
      headingRowColor: WidgetStateProperty.all(Colors.grey.shade100),
      columns: [
        DataColumn(
          label: const Text('Nombre'),
          onSort: (_, asc) => setState(() {
            _sortColumnIndex = 0;
            _sortAscending = asc;
          }),
        ),
        DataColumn(
          label: const Text('Email'),
          onSort: (_, asc) => setState(() {
            _sortColumnIndex = 1;
            _sortAscending = asc;
          }),
        ),
        DataColumn(
          label: const Text('Rol'),
          onSort: (_, asc) => setState(() {
            _sortColumnIndex = 2;
            _sortAscending = asc;
          }),
        ),
        DataColumn(
          label: const Text('Territorio'),
          onSort: (_, asc) => setState(() {
            _sortColumnIndex = 3;
            _sortAscending = asc;
          }),
        ),
        DataColumn(
          label: const Text('Estado'),
          onSort: (_, asc) => setState(() {
            _sortColumnIndex = 4;
            _sortAscending = asc;
          }),
        ),
        const DataColumn(label: Text('Acciones')),
      ],
      rows: users.map((user) {
        final territorialLabel = user.isCallGestor
            ? 'Call Center'
            : userTerritorialLabel(user);
        return DataRow(
          cells: [
            DataCell(Text(user.nombre.isNotEmpty ? user.nombre : user.email)),
            DataCell(Text(user.email)),
            DataCell(Text(user.isCallGestor ? 'Call' : user.rol)),
            DataCell(Text(territorialLabel)),
            DataCell(Text(user.activo ? 'Activo' : 'Inactivo')),
            DataCell(
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    tooltip: 'Editar',
                    icon: const Icon(Icons.edit_outlined, size: 18),
                    onPressed: _saving ? null : () => _showUserDialog(user),
                  ),
                  IconButton(
                    tooltip: user.activo ? 'Desactivar' : 'Activar',
                    icon: Icon(
                      user.activo
                          ? Icons.person_off_outlined
                          : Icons.person_outline,
                      size: 18,
                    ),
                    onPressed: _saving ? null : () => _toggleActivo(user),
                  ),
                ],
              ),
            ),
          ],
        );
      }).toList(),
    );
  }

  Widget _buildRoleChip(String? role, String label) {
    final selected = _roleFilter == role;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: FilterChip(
        label: Text(label),
        selected: selected,
        onSelected: (_) => setState(() => _roleFilter = role),
        selectedColor: AppTheme.primaryColor.withValues(alpha: 0.15),
        checkmarkColor: AppTheme.primaryColor,
      ),
    );
  }

  Widget _buildUserCard(UserModel user, int index) {
    final territorialLabel = user.isCallGestor
        ? 'Call Center'
        : userTerritorialLabel(user);

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: CircleAvatar(
          backgroundColor: _getRoleColor(user.rol).withValues(alpha: 0.12),
          child: Text(
            user.initials,
            style: TextStyle(
              fontWeight: FontWeight.bold,
              color: _getRoleColor(user.rol),
            ),
          ),
        ),
        title: Text(
          user.nombre.isNotEmpty ? user.nombre : user.email,
          style: TextStyle(
            fontWeight: FontWeight.w600,
            color: user.activo ? null : Colors.grey.shade500,
          ),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(user.email, style: const TextStyle(fontSize: 12)),
            const SizedBox(height: 4),
            Row(
              children: [
                _buildRoleBadge(user.rol),
                if (user.isCallGestor) ...[
                  const SizedBox(width: 6),
                  _buildCallBadge(),
                ],
                if (!user.activo) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.red.shade50,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      'INACTIVO',
                      style: TextStyle(
                        fontSize: 10,
                        color: Colors.red.shade700,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
                if (territorialLabel.isNotEmpty) ...[
                  const SizedBox(width: 6),
                  Flexible(
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: user.isCallGestor
                            ? Colors.cyan.shade50
                            : Colors.blue.shade50,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        territorialLabel,
                        style: TextStyle(
                          fontSize: 10,
                          color: user.isCallGestor
                              ? Colors.cyan.shade800
                              : Colors.blue.shade700,
                          fontWeight: FontWeight.w500,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
        trailing: PopupMenuButton<String>(
          onSelected: _saving ? null : (action) => _handleUserAction(action, user),
          itemBuilder: (_) => [
            PopupMenuItem(
              value: 'toggle_activo',
              child: Row(
                children: [
                  Icon(
                    user.activo
                        ? Icons.person_off_outlined
                        : Icons.person_outline,
                    size: 18,
                  ),
                  const SizedBox(width: 8),
                  Text(user.activo ? 'Desactivar' : 'Activar'),
                ],
              ),
            ),
            const PopupMenuItem(
              value: 'edit',
              child: Row(
                children: [
                  Icon(Icons.edit_outlined, size: 18),
                  SizedBox(width: 8),
                  Text('Editar'),
                ],
              ),
            ),
            const PopupMenuItem(
              value: 'delete',
              child: Row(
                children: [
                  Icon(Icons.delete_outline, size: 18, color: Colors.red),
                  SizedBox(width: 8),
                  Text('Eliminar', style: TextStyle(color: Colors.red)),
                ],
              ),
            ),
          ],
        ),
      ),
    )
        .animate()
        .fadeIn(
            delay: Duration(milliseconds: (index * 50).clamp(0, 300)),
            duration: 300.ms)
        .slideX(begin: 0.03, end: 0, duration: 300.ms);
  }

  Widget _buildCallBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.cyan.shade50,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: Colors.cyan.shade200),
      ),
      child: Text(
        'CALL',
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: Colors.cyan.shade800,
        ),
      ),
    );
  }

  Widget _buildRoleBadge(String rol) {
    final color = _getRoleColor(rol);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        rol.toUpperCase(),
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: color,
        ),
      ),
    );
  }

  Color _getRoleColor(String rol) {
    switch (rol) {
      case 'admin':
        return Colors.red.shade600;
      case 'supervisor':
        return Colors.purple.shade600;
      case 'asistente':
        return Colors.teal.shade600;
      default:
        return AppTheme.primaryColor;
    }
  }

  void _handleUserAction(String action, UserModel user) {
    if (action == 'toggle_activo') {
      _toggleActivo(user);
    } else if (action == 'edit') {
      _showUserDialog(user);
    } else if (action == 'delete') {
      _confirmDelete(user);
    }
  }

  void _confirmDelete(UserModel user) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Eliminar Usuario'),
        content: Text(
          '¿Eliminar a ${user.nombre}?\nSe borrará la cuenta de acceso y el perfil.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(ctx);
              if (user.uid.isEmpty) {
                _showSnack('Usuario sin UID válido.', isError: true);
                return;
              }
              setState(() => _saving = true);
              try {
                await _userAdminService.deleteGestorUser(user.uid);
                _showSnack('${user.nombre} eliminado');
              } catch (e) {
                _showSnack(
                  e.toString().replaceFirst('Exception: ', ''),
                  isError: true,
                );
              } finally {
                if (mounted) setState(() => _saving = false);
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red.shade600,
            ),
            child: const Text('Eliminar'),
          ),
        ],
      ),
    );
  }

  void _showUserDialog(UserModel? user) {
    final isEdit = user != null;
    final nameCtrl = TextEditingController(text: user?.nombre ?? '');
    final emailCtrl = TextEditingController(text: user?.email ?? '');
    final phoneCtrl = TextEditingController(text: user?.telefono ?? '');
    final passwordCtrl = TextEditingController();
    String selectedRole = user?.rol ?? 'gestor';
    String selectedCanal = user?.canal ?? 'campo';
    bool activo = user?.activo ?? true;
    bool obscurePassword = true;
    List<String> selectedSecciones = user != null
        ? List<String>.from(user.secciones)
        : <String>[];

    if (selectedSecciones.isEmpty && user != null) {
      final key = resolveInitialCompositeKey(user);
      if (key.isNotEmpty) selectedSecciones = [key];
    }

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) {
          final normalized = normalizeRoleCanal(selectedRole, selectedCanal);
          final showCanal = shouldShowCanalSelector(selectedRole);
          final showTerritorial =
              shouldShowTerritorialPicker(normalized.rol, normalized.canal);

          return AlertDialog(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
            title: Text(isEdit ? 'Editar Usuario' : 'Nuevo Usuario'),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: nameCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Nombre completo',
                      prefixIcon: Icon(Icons.person_outline, size: 20),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: emailCtrl,
                    readOnly: isEdit,
                    keyboardType: TextInputType.emailAddress,
                    decoration: const InputDecoration(
                      labelText: 'Correo electrónico',
                      prefixIcon: Icon(Icons.email_outlined, size: 20),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: passwordCtrl,
                    obscureText: obscurePassword,
                    decoration: InputDecoration(
                      labelText: isEdit
                          ? 'Nueva contraseña (opcional)'
                          : 'Contraseña',
                      prefixIcon: const Icon(Icons.lock_outline, size: 20),
                      suffixIcon: IconButton(
                        icon: Icon(
                          obscurePassword
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                          size: 20,
                        ),
                        onPressed: () => setDialogState(
                          () => obscurePassword = !obscurePassword,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: phoneCtrl,
                    keyboardType: TextInputType.phone,
                    decoration: const InputDecoration(
                      labelText: 'Teléfono (opcional)',
                      prefixIcon: Icon(Icons.phone_outlined, size: 20),
                    ),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    value: selectedRole,
                    decoration: const InputDecoration(
                      labelText: 'Rol',
                      prefixIcon: Icon(Icons.security_outlined, size: 20),
                    ),
                    items: const [
                      DropdownMenuItem(value: 'gestor', child: Text('Gestor')),
                      DropdownMenuItem(
                          value: 'asistente', child: Text('Asistente')),
                      DropdownMenuItem(
                          value: 'supervisor', child: Text('Supervisor')),
                      DropdownMenuItem(value: 'admin', child: Text('Admin')),
                    ],
                    onChanged: (v) => setDialogState(() {
                      selectedRole = v ?? 'gestor';
                    }),
                  ),
                  if (showCanal) ...[
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: selectedCanal,
                      decoration: const InputDecoration(
                        labelText: 'Tipo de gestor',
                        prefixIcon: Icon(Icons.headset_mic_outlined, size: 20),
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: 'campo',
                          child: Text('Campo (territorial)'),
                        ),
                        DropdownMenuItem(
                          value: 'call',
                          child: Text('Call Center (tramo 1)'),
                        ),
                      ],
                      onChanged: (v) => setDialogState(() {
                        selectedCanal = v ?? 'campo';
                      }),
                    ),
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(
                        selectedCanal == 'call'
                            ? 'Call Center: gestión telefónica sin sección territorial.'
                            : 'Campo: asignación territorial por secciones.',
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ),
                  ],
                  if (showTerritorial) ...[
                    const SizedBox(height: 12),
                    MultiTerritorialSectionPicker(
                      catalog: _catalog,
                      availableSectionKeys: _availableSections,
                      initialSecciones: selectedSecciones,
                      onSeccionesChanged: (keys) {
                        setDialogState(() => selectedSecciones = keys);
                      },
                    ),
                  ],
                  if (isEdit) ...[
                    const SizedBox(height: 8),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Usuario activo'),
                      value: activo,
                      onChanged: (v) => setDialogState(() => activo = v),
                    ),
                  ],
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Cancelar'),
              ),
              ElevatedButton(
                onPressed: () async {
                  final roleCanal =
                      normalizeRoleCanal(selectedRole, selectedCanal);
                  final validationError = validateUserForm(
                    isEdit: isEdit,
                    nombre: nameCtrl.text,
                    email: emailCtrl.text,
                    password: passwordCtrl.text,
                    rol: roleCanal.rol,
                    canal: roleCanal.canal,
                    selectedSecciones: selectedSecciones,
                  );
                  if (validationError != null) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text(validationError)),
                    );
                    return;
                  }

                  final built = buildSecciones(
                    rol: roleCanal.rol,
                    canal: roleCanal.canal,
                    secciones: selectedSecciones,
                    uid: isEdit ? user.uid : null,
                  );

                  Navigator.pop(ctx);
                  setState(() => _saving = true);

                  try {
                    if (isEdit) {
                      final updates = <String, dynamic>{
                        'nombre': nameCtrl.text.trim(),
                        'telefono': phoneCtrl.text.trim(),
                        'rol': roleCanal.rol,
                        'canal': roleCanal.canal,
                        'activo': activo,
                        'seccion': built.seccion,
                        'zona': built.zona,
                        'region': built.region,
                        'secciones': built.secciones,
                      };
                      await _userAdminService.updateGestorUser(
                        uid: user.uid,
                        updates: updates,
                        password: passwordCtrl.text.trim().isEmpty
                            ? null
                            : passwordCtrl.text.trim(),
                      );
                      _showSnack('Usuario actualizado');
                    } else {
                      await _userAdminService.createGestorUser(
                        email: emailCtrl.text,
                        password: passwordCtrl.text,
                        nombre: nameCtrl.text,
                        telefono: phoneCtrl.text,
                        seccion: built.seccion,
                        zona: built.zona,
                        region: built.region,
                        rol: roleCanal.rol,
                        canal: roleCanal.canal,
                        secciones: selectedSecciones,
                      );
                      _showSnack('Usuario creado correctamente');
                    }
                  } catch (e) {
                    _showSnack(
                      e.toString().replaceFirst('Exception: ', ''),
                      isError: true,
                    );
                  } finally {
                    if (mounted) setState(() => _saving = false);
                  }
                },
                child: Text(isEdit ? 'Guardar' : 'Crear'),
              ),
            ],
          );
        },
      ),
    );
  }
}
