import 'dart:async';

import 'package:flutter/foundation.dart' show kIsWeb;
import '../utils/responsive.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config/theme.dart';
import '../services/auth_service.dart';
import '../services/sync_status_service.dart';
import '../services/location_service.dart';
import '../services/tracking_service.dart';
import 'admin_dashboard_screen.dart';
import 'consulta_telegram_screen.dart';
import 'dashboard_screen.dart';
import 'stats_screen.dart';
import 'client_map_screen.dart';
import 'my_routes_screen.dart';
import 'profile_screen.dart';
import 'more_screen.dart';
import 'tracking_screen.dart';
import '../widgets/map_visibility_scope.dart';

/// Main app shell with bottom navigation.
/// Shows Dashboard, Stats (if allowed), Admin (if allowed).
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  static const int _gestorMyRoutesTabIndex = 2;

  int _currentIndex = 0;
  bool _gpsInitStarted = false;
  final GlobalKey<MyRoutesScreenState> _myRoutesKey = GlobalKey<MyRoutesScreenState>();

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _startGpsIfNeeded();
  }

  void _startGpsIfNeeded() {
    if (_gpsInitStarted) return;

    final auth = context.read<AuthService>();
    final user = auth.firebaseUser;
    final profile = auth.profile;
    if (user == null || profile == null) return;

    if (profile.isCallGestor) return;

    _gpsInitStarted = true;
    unawaited(_initGpsAndTracking(
      user.uid,
      profile.seccion,
      profile.nombre,
      isGestor: profile.isFieldGestor,
    ));
  }

  Future<void> _initGpsAndTracking(
    String uid,
    String seccion,
    String nombre, {
    required bool isGestor,
  }) async {
    // Solo gestores de campo necesitan GPS al arrancar la app.
    if (!isGestor) return;

    final location = LocationService();
    final tracking = context.read<TrackingService>();

    final ready = await location.ensureReady();
    if (!mounted) return;

    if (!ready) {
      _showGpsMessage(
        location.error ?? 'Active el GPS y conceda permisos de ubicación.',
        actionLabel: 'Configurar',
        onAction: () async {
          if (location.error?.contains('GPS del dispositivo') == true) {
            await location.openLocationSettings();
          } else {
            await location.openAppSettings();
          }
          if (!mounted) return;
          _gpsInitStarted = false;
          _startGpsIfNeeded();
        },
      );
      return;
    }

    // Precalentar posición para mapa y detalle de cliente
    await location.getCurrentPosition();

    if (!mounted) return;

    // Solo gestores de campo publican recorrido en ubicaciones_gestores
    if (isGestor) {
      if (!tracking.isRunning) {
        await tracking.start(
          gestorUid: uid,
          seccion: seccion,
          gestorName: nombre,
        );
      }
      if (!mounted) return;
      if (tracking.error != null) {
        _showGpsMessage(tracking.error!);
      }
    }
  }

  void _onTabSelected(int index) {
    setState(() => _currentIndex = index);
    final isGestor = context.read<AuthService>().profile?.isGestor ?? false;
    if (isGestor && index == _gestorMyRoutesTabIndex) {
      _myRoutesKey.currentState?.reload();
    }
  }

  void _showGpsMessage(
    String text, {
    String? actionLabel,
    VoidCallback? onAction,
  }) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(text),
        duration: const Duration(seconds: 6),
        action: actionLabel != null && onAction != null
            ? SnackBarAction(label: actionLabel, onPressed: onAction)
            : null,
      ),
    );
  }

  void _ensureValidTabIndex(int tabCount) {
    if (tabCount == 0 || _currentIndex < tabCount) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      setState(() => _currentIndex = 0);
    });
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();
    final syncStatus = context.watch<SyncStatusService>();
    final profile = auth.profile;

    if (profile == null) {
      debugPrint('[HomeShell] perfil null, esperando...');
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(color: AppTheme.primaryColor),
        ),
      );
    }

    debugPrint('[HomeShell] build perfil=${profile.nombre} rol=${profile.rol}');

    final isGestor = profile.isGestor;
    final isCallGestor = profile.isCallGestor;
    final canManageUsers = profile.canManageUsers;
    final canViewStats = profile.canViewStats;

    final List<_TabItem> tabs;
    if (isCallGestor) {
      tabs = <_TabItem>[
        const _TabItem(
          icon: Icons.headset_mic_outlined,
          activeIcon: Icons.headset_mic,
          label: 'Cartera',
          screen: DashboardScreen(),
        ),
        const _TabItem(
          icon: Icons.travel_explore_outlined,
          activeIcon: Icons.travel_explore,
          label: 'Consultas',
          screen: ConsultaTelegramScreen(),
        ),
        const _TabItem(
          icon: Icons.person_outline,
          activeIcon: Icons.person,
          label: 'Perfil',
          screen: ProfileScreen(),
        ),
      ];
    } else if (isGestor) {
      tabs = <_TabItem>[
        const _TabItem(
          icon: Icons.dashboard_outlined,
          activeIcon: Icons.dashboard,
          label: 'Gestión',
          screen: DashboardScreen(),
        ),
        const _TabItem(
          icon: Icons.map_outlined,
          activeIcon: Icons.map,
          label: 'Mapa',
          screen: ClientMapScreen(),
          wrapMapVisibility: true,
        ),
        _TabItem(
          icon: Icons.route_outlined,
          activeIcon: Icons.route,
          label: 'Mis rutas',
          screen: MyRoutesScreen(key: _myRoutesKey),
        ),
        const _TabItem(
          icon: Icons.travel_explore_outlined,
          activeIcon: Icons.travel_explore,
          label: 'Consultas',
          screen: ConsultaTelegramScreen(),
        ),
        const _TabItem(
          icon: Icons.person_outline,
          activeIcon: Icons.person,
          label: 'Perfil',
          screen: ProfileScreen(),
        ),
      ];
    } else if (canManageUsers) {
      // Admin / supervisor: supervisión con recorridos en tab principal.
      tabs = <_TabItem>[
        const _TabItem(
          icon: Icons.home_outlined,
          activeIcon: Icons.home,
          label: 'Inicio',
          screen: AdminDashboardScreen(),
        ),
        if (canViewStats)
          const _TabItem(
            icon: Icons.bar_chart_outlined,
            activeIcon: Icons.bar_chart,
            label: 'Estadísticas',
            screen: StatsScreen(),
          ),
        const _TabItem(
          icon: Icons.groups_outlined,
          activeIcon: Icons.groups,
          label: 'Equipo',
          screen: TrackingScreen(),
          wrapMapVisibility: true,
        ),
        const _TabItem(
          icon: Icons.person_outline,
          activeIcon: Icons.person,
          label: 'Perfil',
          screen: ProfileScreen(),
        ),
      ];
    } else {
      // Asistente: stats + hub secundario para mapa.
      tabs = <_TabItem>[
        const _TabItem(
          icon: Icons.dashboard_outlined,
          activeIcon: Icons.dashboard,
          label: 'Gestión',
          screen: DashboardScreen(),
        ),
        if (canViewStats)
          const _TabItem(
            icon: Icons.bar_chart_outlined,
            activeIcon: Icons.bar_chart,
            label: 'Estadísticas',
            screen: StatsScreen(),
          ),
        const _TabItem(
          icon: Icons.person_outline,
          activeIcon: Icons.person,
          label: 'Perfil',
          screen: ProfileScreen(),
        ),
        _TabItem(
          icon: Icons.more_horiz,
          activeIcon: Icons.more_horiz,
          label: 'Más',
          screen: MoreScreen(
            canManageUsers: false,
            canViewStats: canViewStats,
            isGestor: false,
            showTrackingInMore: false,
          ),
        ),
      ];
    }

    _ensureValidTabIndex(tabs.length);
    final safeIndex = tabs.isEmpty
        ? 0
        : _currentIndex.clamp(0, tabs.length - 1);

    final useSideNav = context.isExpanded;
    final showWebGpsHint = kIsWeb && isGestor;

    final contentStack = IndexedStack(
      index: safeIndex,
      sizing: StackFit.expand,
      children: tabs.asMap().entries.map((entry) {
        final tab = entry.value;
        return _LazyShellTab(
          key: ValueKey('shell-tab-${tab.label}'),
          tabIndex: entry.key,
          activeIndex: safeIndex,
          wrapMapVisibility: tab.wrapMapVisibility,
          screen: tab.screen,
        );
      }).toList(),
    );

    final mainColumn = Column(
      children: [
        if (syncStatus.showSyncBanner)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 16),
            color: syncStatus.isOnline ? Colors.amber.shade800 : Colors.orange.shade700,
            child: SafeArea(
              bottom: false,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    syncStatus.isOnline ? Icons.cloud_upload : Icons.wifi_off,
                    color: Colors.white,
                    size: 16,
                  ),
                  const SizedBox(width: 6),
                  Flexible(
                    child: Text(
                      syncStatus.bannerMessage,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  if (syncStatus.pendingCount > 0) ...[
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.25),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        '${syncStatus.pendingCount}',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        if (showWebGpsHint)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 16),
            color: AppTheme.primaryColor.withValues(alpha: 0.12),
            child: SafeArea(
              bottom: false,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.info_outline, color: AppTheme.primaryColor, size: 16),
                  const SizedBox(width: 6),
                  Flexible(
                    child: Text(
                      'Web: GPS y recorrido solo con esta pestaña abierta. En campo use la APK.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: AppTheme.primaryColor.withValues(alpha: 0.95),
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        Expanded(child: contentStack),
      ],
    );

    final shellBody = LayoutBuilder(
      builder: (context, constraints) {
        return Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: ResponsiveBreakpoints.contentMax,
              minHeight: constraints.maxHeight,
              maxHeight: constraints.maxHeight,
            ),
            child: mainColumn,
          ),
        );
      },
    );

    if (useSideNav) {
      return Scaffold(
        body: Row(
          children: [
            NavigationRail(
              selectedIndex: safeIndex,
              onDestinationSelected: _onTabSelected,
              labelType: NavigationRailLabelType.all,
              destinations: tabs
                  .map(
                    (t) => NavigationRailDestination(
                      icon: Icon(t.icon),
                      selectedIcon: Icon(t.activeIcon, color: AppTheme.primaryColor),
                      label: Text(t.label),
                    ),
                  )
                  .toList(),
            ),
            const VerticalDivider(width: 1),
            Expanded(child: shellBody),
          ],
        ),
      );
    }

    return Scaffold(
      body: SafeArea(child: shellBody),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.08),
              blurRadius: 12,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: NavigationBar(
          selectedIndex: safeIndex,
          onDestinationSelected: _onTabSelected,
          height: 65,
          indicatorColor: AppTheme.primaryColor.withValues(alpha: 0.12),
          destinations: tabs
              .map((t) => NavigationDestination(
                    icon: Icon(t.icon),
                    selectedIcon:
                        Icon(t.activeIcon, color: AppTheme.primaryColor),
                    label: t.label,
                  ))
              .toList(),
        ),
      ),
    );
  }
}

class _TabItem {
  final IconData icon;
  final IconData activeIcon;
  final String label;
  final Widget screen;
  final bool wrapMapVisibility;

  const _TabItem({
    required this.icon,
    required this.activeIcon,
    required this.label,
    required this.screen,
    this.wrapMapVisibility = false,
  });
}

/// Monta pestañas bajo demanda para no inicializar mapa/rutas al iniciar sesión.
class _LazyShellTab extends StatefulWidget {
  const _LazyShellTab({
    super.key,
    required this.tabIndex,
    required this.activeIndex,
    required this.wrapMapVisibility,
    required this.screen,
  });

  final int tabIndex;
  final int activeIndex;
  final bool wrapMapVisibility;
  final Widget screen;

  @override
  State<_LazyShellTab> createState() => _LazyShellTabState();
}

class _LazyShellTabState extends State<_LazyShellTab>
    with AutomaticKeepAliveClientMixin {
  bool _mountedOnce = false;

  @override
  bool get wantKeepAlive => _mountedOnce;

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final isActive = widget.tabIndex == widget.activeIndex;
    if (!isActive && !_mountedOnce) {
      return const SizedBox.expand();
    }
    _mountedOnce = true;

    Widget child = widget.screen;
    if (widget.wrapMapVisibility) {
      child = MapTabWrapper(isActive: isActive, child: child);
    }
    return child;
  }
}
