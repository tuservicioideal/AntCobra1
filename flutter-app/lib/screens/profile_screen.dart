import 'package:flutter/material.dart';

import 'package:provider/provider.dart';

import '../config/theme.dart';

import '../models/gestor_stats.dart';

import '../services/auth_service.dart';

import '../services/campana_banco_filter_notifier.dart';

import '../services/connectivity_service.dart';

import '../services/gestor_stats_service.dart';

import '../services/campaign_service.dart';

import '../services/app_update_service.dart';

import '../widgets/campana_banco_filter_bar.dart';

import '../widgets/gestor_profile_stats_panel.dart';

import '../widgets/admin/admin_quick_action_tile.dart';

import 'admin_screen.dart';
import 'reassignment_screen.dart';

import 'client_map_screen.dart';

import 'more_screen.dart';

import 'client_search_screen.dart';
import 'stats_screen.dart';



class ProfileScreen extends StatefulWidget {

  const ProfileScreen({super.key});



  @override

  State<ProfileScreen> createState() => _ProfileScreenState();

}



class _ProfileScreenState extends State<ProfileScreen> {

  final _statsService = GestorStatsService();

  final _campaignService = CampaignService();



  bool _statsLoading = false;

  GestorStats? _stats;

  String? _statsError;

  bool _noCampaignOrSections = false;

  Map<String, dynamic>? _campaignData;

  CampanaBancoFilterNotifier? _campanaFilterNotifier;

  bool _checkingUpdate = false;

  String? _updateProgressMsg;



  @override

  void initState() {

    super.initState();

    WidgetsBinding.instance.addPostFrameCallback((_) {

      _loadStats();

      _loadCampaignSummary();

    });

  }



  @override

  void didChangeDependencies() {

    super.didChangeDependencies();

    final notifier = context.read<CampanaBancoFilterNotifier>();

    if (_campanaFilterNotifier != notifier) {

      _campanaFilterNotifier?.removeListener(_onCampanaFilterChanged);

      _campanaFilterNotifier = notifier;

      _campanaFilterNotifier!.addListener(_onCampanaFilterChanged);

    }

  }



  void _onCampanaFilterChanged() {

    _loadStats();

  }



  @override

  void dispose() {

    _campanaFilterNotifier?.removeListener(_onCampanaFilterChanged);

    super.dispose();

  }



  Future<void> _loadCampaignSummary() async {

    final profile = context.read<AuthService>().profile;

    if (profile == null || profile.isGestor) return;



    final campaignId = await _campaignService.getActiveCampaignId();

    if (campaignId == null || !mounted) return;

    final data = await _campaignService.getCampaignData(campaignId);

    if (!mounted) return;

    setState(() => _campaignData = data);

  }



  Future<void> _loadStats() async {

    final profile = context.read<AuthService>().profile;

    if (profile == null || !profile.isGestor) return;



    setState(() {

      _statsLoading = true;

      _statsError = null;

      _noCampaignOrSections = false;

    });



    try {

      final allClients =
          await _statsService.loadActiveClientsForProfile(profile);
      if (mounted) {
        context.read<CampanaBancoFilterNotifier>().updateAvailable(allClients);
      }

      final campanaFilter =
          context.read<CampanaBancoFilterNotifier>().selected;

      final stats = await _statsService.loadForProfile(
        profile,
        campanaBancoFilter: campanaFilter,
      );

      if (!mounted) return;

      setState(() {

        _stats = stats;

        _noCampaignOrSections = stats == null;

        _statsLoading = false;

      });

    } catch (e) {

      if (!mounted) return;

      setState(() {

        _statsError = 'No se pudieron cargar las estadísticas. Desliza para reintentar.';

        _statsLoading = false;

      });

    }

  }



  void _openFullStats() {

    Navigator.of(context).push(

      MaterialPageRoute<void>(builder: (_) => const StatsScreen()),

    );

  }



  @override

  Widget build(BuildContext context) {

    final auth = context.watch<AuthService>();

    final connectivity = context.watch<ConnectivityService>();

    final campanaFilterNotifier = context.watch<CampanaBancoFilterNotifier>();

    final profile = auth.profile;

    final user = auth.firebaseUser;



    if (profile == null) {

      return const Scaffold(

        body: Center(

          child: CircularProgressIndicator(color: AppTheme.primaryColor),

        ),

      );

    }



    final allSections = <String>{

      ...profile.secciones,

      if (profile.seccion.isNotEmpty) profile.seccion,

    }.toList()

      ..sort();



    final showGestorStats = profile.isGestor;



    return Scaffold(

      appBar: AppBar(

        title: const Text('Perfil'),

      ),

      body: RefreshIndicator(

        onRefresh: () async {

          await auth.refreshProfile();

          if (showGestorStats) await _loadStats();

          if (!showGestorStats) await _loadCampaignSummary();

        },

        color: AppTheme.primaryColor,

        child: ListView(

          physics: const AlwaysScrollableScrollPhysics(),

          padding: const EdgeInsets.all(16),

          children: [

            Card(

              child: Padding(

                padding: const EdgeInsets.all(16),

                child: Row(

                  children: [

                    CircleAvatar(

                      radius: 28,

                      backgroundColor: AppTheme.primaryColor.withValues(alpha: 0.12),

                      child: Text(

                        profile.initials,

                        style: const TextStyle(

                          color: AppTheme.primaryColor,

                          fontWeight: FontWeight.w800,

                          fontSize: 18,

                        ),

                      ),

                    ),

                    const SizedBox(width: 12),

                    Expanded(

                      child: Column(

                        crossAxisAlignment: CrossAxisAlignment.start,

                        children: [

                          Text(

                            profile.nombre.isNotEmpty ? profile.nombre : 'Sin nombre',

                            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),

                          ),

                          const SizedBox(height: 2),

                          Text(

                            profile.email.isNotEmpty ? profile.email : (user?.email ?? 'Sin correo'),

                            style: TextStyle(color: Colors.grey.shade600, fontSize: 13),

                          ),

                          const SizedBox(height: 6),

                          _RoleChip(role: profile.rol),

                        ],

                      ),

                    ),

                  ],

                ),

              ),

            ),

            if (showGestorStats) ...[

              const SizedBox(height: 10),

              CampanaBancoFilterBar(
                available: campanaFilterNotifier.available,
                selected: campanaFilterNotifier.selected,
                onSelected: campanaFilterNotifier.select,
              ),

              if (_statsLoading && _stats == null)

                const Card(

                  child: Padding(

                    padding: EdgeInsets.all(24),

                    child: Center(

                      child: CircularProgressIndicator(color: AppTheme.primaryColor),

                    ),

                  ),

                )

              else if (_noCampaignOrSections)

                Card(

                  child: Padding(

                    padding: const EdgeInsets.all(14),

                    child: Text(

                      'No hay campaña activa o secciones asignadas para calcular tu avance.',

                      style: TextStyle(color: Colors.grey.shade600, fontSize: 13),

                    ),

                  ),

                )

              else if (_stats != null)

                GestorProfileStatsPanel(

                  stats: _stats!,

                  loading: _statsLoading,

                  errorMessage: _statsError,

                  onRefresh: _loadStats,

                  onViewFullStats: _openFullStats,

                )

              else if (_statsError != null)

                Card(

                  child: Padding(

                    padding: const EdgeInsets.all(14),

                    child: Column(

                      crossAxisAlignment: CrossAxisAlignment.start,

                      children: [

                        Text(_statsError!, style: TextStyle(color: Colors.orange.shade800, fontSize: 13)),

                        TextButton(onPressed: _loadStats, child: const Text('Reintentar')),

                      ],

                    ),

                  ),

                ),

            ],

            if (!showGestorStats) ...[

              const SizedBox(height: 10),

              if (_campaignData != null)

                Card(

                  child: Padding(

                    padding: const EdgeInsets.all(14),

                    child: Row(

                      children: [

                        Container(

                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),

                          decoration: BoxDecoration(

                            color: AppTheme.primaryColor,

                            borderRadius: BorderRadius.circular(8),

                          ),

                          child: Text(

                            'Tramo ${(_campaignData!['tramo_actual'] as num?)?.toInt() ?? 1}',

                            style: const TextStyle(

                              color: Colors.white,

                              fontWeight: FontWeight.bold,

                              fontSize: 13,

                            ),

                          ),

                        ),

                        const SizedBox(width: 10),

                        Text(

                          'Día ${(_campaignData!['dia_campaña'] as num?)?.toInt() ?? 1} de campaña',

                          style: TextStyle(

                            color: Colors.grey.shade700,

                            fontWeight: FontWeight.w500,

                            fontSize: 13,

                          ),

                        ),

                      ],

                    ),

                  ),

                ),

              const SizedBox(height: 10),

              Card(

                child: Column(

                  crossAxisAlignment: CrossAxisAlignment.start,

                  children: [

                    const Padding(

                      padding: EdgeInsets.fromLTRB(16, 14, 16, 0),

                      child: Text(

                        'Accesos rápidos',

                        style: TextStyle(fontWeight: FontWeight.w700),

                      ),

                    ),

                    AdminQuickActionTile(

                      icon: Icons.bar_chart_outlined,

                      title: 'Estadísticas completas',

                      subtitle: 'KPIs, finanzas y ranking del equipo',

                      onTap: () => Navigator.of(context).push(

                        MaterialPageRoute<void>(

                          builder: (_) => const StatsScreen(),

                        ),

                      ),

                    ),

                    const Divider(height: 1),

                    AdminQuickActionTile(

                      icon: Icons.map_outlined,

                      title: 'Mapa de clientes',

                      subtitle: 'Vista territorial de toda la campaña',

                      onTap: () => Navigator.of(context).push(

                        MaterialPageRoute<void>(

                          builder: (_) => const ClientMapScreen(),

                        ),

                      ),

                    ),

                    if (profile.canViewStats && !profile.isGestor) ...[

                      const Divider(height: 1),

                      AdminQuickActionTile(

                        icon: Icons.search,

                        title: 'Buscar cliente',

                        subtitle: 'Nombre, DNI, código o teléfono',

                        onTap: () => Navigator.of(context).push(

                          MaterialPageRoute<void>(

                            builder: (_) => const ClientSearchScreen(),

                          ),

                        ),

                      ),

                    ],

                    if (profile.canManageUsers) ...[

                      const Divider(height: 1),

                      AdminQuickActionTile(

                        icon: Icons.swap_horiz,

                        title: 'Reasignar / Devoluciones',

                        subtitle: 'Transferir clientes entre gestores y call',

                        onTap: () => Navigator.of(context).push(

                          MaterialPageRoute<void>(

                            builder: (_) => const ReassignmentScreen(),

                          ),

                        ),

                      ),

                      const Divider(height: 1),

                      AdminQuickActionTile(

                        icon: Icons.admin_panel_settings_outlined,

                        title: 'Usuarios y roles',

                        subtitle: 'Administrar cuentas del equipo',

                        onTap: () => Navigator.of(context).push(

                          MaterialPageRoute<void>(

                            builder: (_) => const AdminScreen(),

                          ),

                        ),

                      ),

                    ],

                    if (profile.canViewStats && !profile.canManageUsers) ...[

                      const Divider(height: 1),

                      AdminQuickActionTile(

                        icon: Icons.more_horiz,

                        title: 'Más módulos',

                        subtitle: 'Accesos adicionales',

                        onTap: () => Navigator.of(context).push(

                          MaterialPageRoute<void>(

                            builder: (_) => MoreScreen(

                              canManageUsers: false,

                              canViewStats: profile.canViewStats,

                              showTrackingInMore: false,

                            ),

                          ),

                        ),

                      ),

                    ],

                  ],

                ),

              ),

            ],

            const SizedBox(height: 10),

            Card(

              child: Padding(

                padding: const EdgeInsets.all(14),

                child: Column(

                  crossAxisAlignment: CrossAxisAlignment.start,

                  children: [

                    const Text('Datos de cuenta', style: TextStyle(fontWeight: FontWeight.w700)),

                    const SizedBox(height: 10),

                    _InfoRow(label: 'UID', value: profile.uid),

                    _InfoRow(label: 'Teléfono', value: profile.telefono.isNotEmpty ? profile.telefono : 'No registrado'),

                    _InfoRow(label: 'Región', value: profile.region.isNotEmpty ? profile.region : 'No definida'),

                    _InfoRow(label: 'Zona', value: profile.zona.isNotEmpty ? profile.zona : 'No definida'),

                    _InfoRow(label: 'Estado', value: profile.activo ? 'Activo' : 'Inactivo'),

                    _InfoRow(label: 'Conectividad', value: connectivity.isOnline ? 'En línea' : 'Sin conexión'),

                  ],

                ),

              ),

            ),

            const SizedBox(height: 10),

            Card(

              child: Padding(

                padding: const EdgeInsets.all(14),

                child: Column(

                  crossAxisAlignment: CrossAxisAlignment.start,

                  children: [

                    const Text('Secciones asignadas', style: TextStyle(fontWeight: FontWeight.w700)),

                    const SizedBox(height: 10),

                    if (allSections.isEmpty)

                      Text('No hay secciones asignadas.', style: TextStyle(color: Colors.grey.shade600, fontSize: 13))

                    else

                      Wrap(

                        spacing: 8,

                        runSpacing: 8,

                        children: allSections

                            .map(

                              (s) => Container(

                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),

                                decoration: BoxDecoration(

                                  color: AppTheme.primaryColor.withValues(alpha: 0.08),

                                  borderRadius: BorderRadius.circular(999),

                                  border: Border.all(color: AppTheme.primaryColor.withValues(alpha: 0.24)),

                                ),

                                child: Text(

                                  s,

                                  style: const TextStyle(

                                    fontWeight: FontWeight.w600,

                                    color: AppTheme.primaryColor,

                                    fontSize: 12,

                                  ),

                                ),

                              ),

                            )

                            .toList(),

                      ),

                  ],

                ),

              ),

            ),

            const SizedBox(height: 10),

            Card(

              child: Column(

                children: [

                  ListTile(

                    leading: const Icon(Icons.refresh),

                    title: const Text('Actualizar perfil'),

                    subtitle: const Text('Vuelve a leer tus datos desde Firebase'),

                    onTap: () async {

                      await auth.refreshProfile();

                      if (showGestorStats) await _loadStats();

                      if (!context.mounted) return;

                      ScaffoldMessenger.of(context).showSnackBar(

                        const SnackBar(content: Text('Perfil actualizado')),

                      );

                    },

                  ),

                  if (supportsApkSelfUpdate) ...[

                    const Divider(height: 1),

                    ListTile(

                      leading: _checkingUpdate

                          ? const SizedBox(

                              width: 24,

                              height: 24,

                              child: CircularProgressIndicator(strokeWidth: 2),

                            )

                          : const Icon(Icons.system_update),

                      title: const Text('Actualizar app'),

                      subtitle: Text(

                        _updateProgressMsg ??

                            'Busca e instala la última versión del APK',

                      ),

                      enabled: !_checkingUpdate,

                      onTap: _checkingUpdate ? null : () => _onCheckAppUpdate(context),

                    ),

                  ],

                  const Divider(height: 1),

                  ListTile(

                    leading: Icon(Icons.logout, color: Colors.red.shade600),

                    title: Text('Cerrar sesión', style: TextStyle(color: Colors.red.shade600)),

                    onTap: () => _showLogoutDialog(context, auth),

                  ),

                ],

              ),

            ),

          ],

        ),

      ),

    );

  }



  Future<void> _onCheckAppUpdate(BuildContext context) async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() {
      _checkingUpdate = true;
      _updateProgressMsg = 'Consultando servidor…';
    });
    final service = AppUpdateService();
    try {
      final current = await service.currentVersion();
      final info = await service.fetchLatest();
      if (!mounted) return;
      if (info.version.isEmpty) {
        messenger.showSnackBar(
          const SnackBar(content: Text('Manifiesto de versión inválido')),
        );
        return;
      }
      if (!info.isNewerThan(current)) {
        messenger.showSnackBar(
          SnackBar(
            content: Text(
              'Ya tienes la última versión ($current). Servidor: ${info.version}',
            ),
          ),
        );
        return;
      }
      final notes = info.notes.isEmpty ? '(Sin notas)' : info.notes;
      final confirm = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Actualización disponible'),
          content: Text(
            'Hay una nueva versión: ${info.version}\n'
            'Tu versión: $current\n\n'
            '$notes\n\n¿Descargar e instalar ahora?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Descargar'),
            ),
          ],
        ),
      );
      if (confirm != true || !mounted) return;

      final result = await service.downloadUpdate(
        info,
        progress: (msg, frac) {
          if (!mounted) return;
          setState(() => _updateProgressMsg = msg);
        },
      );
      if (!mounted) return;
      if (!result.success || result.apkPath == null) {
        messenger.showSnackBar(
          SnackBar(content: Text(result.message)),
        );
        return;
      }
      final open = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Descarga completa'),
          content: Text(
            '${result.message}\n\n'
            '¿Abrir el instalador ahora?\n'
            '(Android puede pedir permiso para instalar apps)',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Después'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Instalar'),
            ),
          ],
        ),
      );
      if (open == true && result.apkPath != null) {
        final ok = await service.openInstaller(result.apkPath!);
        if (!ok && mounted) {
          messenger.showSnackBar(
            const SnackBar(
              content: Text(
                'No se pudo abrir el instalador. Revisa el permiso de instalar apps.',
              ),
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
          SnackBar(content: Text('No se pudo actualizar: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _checkingUpdate = false;
          _updateProgressMsg = null;
        });
      }
    }
  }

  void _showLogoutDialog(BuildContext context, AuthService auth) {

    showDialog(

      context: context,

      builder: (ctx) => AlertDialog(

        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),

        title: const Text('Cerrar sesión'),

        content: const Text('¿Desea cerrar sesión en este dispositivo?'),

        actions: [

          TextButton(

            onPressed: () => Navigator.pop(ctx),

            child: const Text('Cancelar'),

          ),

          ElevatedButton(

            onPressed: () {

              Navigator.pop(ctx);

              context.read<CampanaBancoFilterNotifier>().clearAll();

              auth.signOut();

            },

            style: ElevatedButton.styleFrom(backgroundColor: Colors.red.shade600),

            child: const Text('Cerrar sesión'),

          ),

        ],

      ),

    );

  }

}



class _InfoRow extends StatelessWidget {

  final String label;

  final String value;

  const _InfoRow({required this.label, required this.value});



  @override

  Widget build(BuildContext context) {

    return Padding(

      padding: const EdgeInsets.symmetric(vertical: 4),

      child: Row(

        children: [

          SizedBox(

            width: 104,

            child: Text(

              label,

              style: TextStyle(color: Colors.grey.shade600, fontSize: 12),

            ),

          ),

          Expanded(

            child: Text(

              value,

              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),

            ),

          ),

        ],

      ),

    );

  }

}



class _RoleChip extends StatelessWidget {

  final String role;

  const _RoleChip({required this.role});



  @override

  Widget build(BuildContext context) {

    final normalized = role.toLowerCase();

    final color = normalized == 'admin'

        ? Colors.deepPurple

        : normalized == 'supervisor'

            ? Colors.indigo

            : normalized == 'asistente'

                ? Colors.teal

                : AppTheme.primaryColor;

    return Container(

      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),

      decoration: BoxDecoration(

        color: color.withValues(alpha: 0.12),

        borderRadius: BorderRadius.circular(999),

      ),

      child: Text(

        normalized.toUpperCase(),

        style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w700),

      ),

    );

  }

}

