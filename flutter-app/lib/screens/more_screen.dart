import 'package:flutter/material.dart';
import '../utils/responsive.dart';
import 'admin_screen.dart';
import 'etiquetas_admin_screen.dart';
import 'client_map_screen.dart';
import 'my_routes_screen.dart';
import 'tracking_screen.dart';

class MoreScreen extends StatelessWidget {
  final bool canManageUsers;
  final bool canViewStats;
  final bool isGestor;
  final bool showTrackingInMore;

  const MoreScreen({
    super.key,
    required this.canManageUsers,
    required this.canViewStats,
    this.isGestor = false,
    this.showTrackingInMore = true,
  });

  @override
  Widget build(BuildContext context) {
    final modules = <_ModuleInfo>[
      _ModuleInfo(
        icon: Icons.map_outlined,
        title: 'Mapa de clientes',
        subtitle: 'Visualizar y seleccionar clientes en mapa',
        page: const ClientMapScreen(),
      ),
      if (isGestor)
        _ModuleInfo(
          icon: Icons.route_outlined,
          title: 'Mis rutas',
          subtitle: 'Consultar rutas guardadas',
          page: const MyRoutesScreen(),
        ),
      if (canManageUsers && showTrackingInMore)
        _ModuleInfo(
          icon: Icons.location_on_outlined,
          title: 'Recorridos en campo',
          subtitle: 'Posición en vivo, trazas y rutas del equipo',
          page: const TrackingScreen(),
        ),
      if (canManageUsers)
        _ModuleInfo(
          icon: Icons.admin_panel_settings_outlined,
          title: 'Administración',
          subtitle: 'Usuarios y roles',
          page: const AdminScreen(),
        ),
      if (canManageUsers)
        _ModuleInfo(
          icon: Icons.label_outline,
          title: 'Etiquetas',
          subtitle: 'Catálogo global para gestores',
          page: const EtiquetasAdminScreen(),
        ),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text('Más módulos')),
      body: context.isExpanded
          ? GridView.builder(
              padding: const EdgeInsets.all(16),
              gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: context.screenWidth >= 1200 ? 3 : 2,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 1.6,
              ),
              itemCount: modules.length,
              itemBuilder: (context, index) {
                final module = modules[index];
                return _ModuleCard(
                  icon: module.icon,
                  title: module.title,
                  subtitle: module.subtitle,
                  onTap: () => _open(context, module.page),
                );
              },
            )
          : ListView(
              padding: const EdgeInsets.all(12),
              children: [
                const SizedBox(height: 4),
                ...modules.map(
                  (module) => _ModuleTile(
                    icon: module.icon,
                    title: module.title,
                    subtitle: module.subtitle,
                    onTap: () => _open(context, module.page),
                  ),
                ),
                if (!canViewStats)
                  const Padding(
                    padding: EdgeInsets.only(top: 12),
                    child: Text(
                      'Algunos módulos dependen del rol asignado.',
                      style: TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                  ),
              ],
            ),
    );
  }

  void _open(BuildContext context, Widget page) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => page),
    );
  }
}

class _ModuleInfo {
  final IconData icon;
  final String title;
  final String subtitle;
  final Widget page;

  const _ModuleInfo({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.page,
  });
}

class _ModuleCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _ModuleCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        mouseCursor: SystemMouseCursors.click,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: 28),
              const Spacer(),
              Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              Text(
                subtitle,
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ModuleTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _ModuleTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Icon(icon),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }
}
