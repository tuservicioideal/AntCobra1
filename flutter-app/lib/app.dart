import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'config/theme.dart';
import 'services/auth_service.dart';
import 'screens/login_screen.dart';
import 'screens/home_shell.dart';

class RecaudoLegalApp extends StatelessWidget {
  const RecaudoLegalApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'App Recaudo Legal',
      debugShowCheckedModeBanner: kDebugMode,
      theme: AppTheme.lightTheme,
      builder: (context, child) {
        if (!kDebugMode || child == null) return child ?? const SizedBox.shrink();
        return Stack(
          children: [
            child,
            Positioned(
              top: 8,
              left: 8,
              right: 8,
              child: Consumer<AuthService>(
                builder: (context, auth, _) {
                  final screen = auth.loading
                      ? 'splash'
                      : (auth.firebaseUser != null && auth.profile == null)
                          ? 'profile-loading'
                          : (!auth.isAuthenticated)
                              ? 'login'
                              : 'home';
                  return Material(
                    elevation: 6,
                    color: Colors.black.withValues(alpha: 0.82),
                    borderRadius: BorderRadius.circular(8),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      child: Text(
                        'DEBUG · pantalla=$screen · loading=${auth.loading} · '
                        'authed=${auth.isAuthenticated} · uid=${auth.firebaseUser?.uid ?? "-"} · '
                        'perfil=${auth.profile?.nombre ?? "-"} · rol=${auth.profile?.rol ?? "-"} · '
                        'error=${auth.error ?? "-"}',
                        style: const TextStyle(color: Colors.white, fontSize: 10),
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        );
      },
      home: Consumer<AuthService>(
        builder: (context, auth, _) {
          if (auth.loading) {
            debugPrint('[App] -> Splash (bootstrap)');
            return const _SplashScreen();
          }
          if (auth.firebaseUser != null && auth.profile == null) {
            debugPrint('[App] -> ProfileLoading uid=${auth.firebaseUser?.uid}');
            return const _ProfileLoadingScreen();
          }
          if (!auth.isAuthenticated) {
            debugPrint('[App] -> Login');
            return const LoginScreen();
          }
          debugPrint('[App] -> HomeShell perfil=${auth.profile?.nombre} rol=${auth.profile?.rol}');
          return const HomeShell();
        },
      ),
    );
  }
}

class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [AppTheme.primary, AppTheme.accent],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primary.withValues(alpha: 0.3),
                    blurRadius: 20,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: const Icon(Icons.shield_rounded, color: Colors.white, size: 36),
            ),
            const SizedBox(height: 20),
            Text(
              'App Recaudo Legal',
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: 32,
              height: 32,
              child: CircularProgressIndicator(
                strokeWidth: 3,
                valueColor: AlwaysStoppedAnimation(AppTheme.primary),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ProfileLoadingScreen extends StatelessWidget {
  const _ProfileLoadingScreen();

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();
    return Scaffold(
      backgroundColor: AppTheme.background,
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(color: AppTheme.primaryColor),
              const SizedBox(height: 20),
              const Text(
                'Cargando perfil...',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
              ),
              if (auth.error != null) ...[
                const SizedBox(height: 12),
                Text(
                  auth.error!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: AppTheme.danger, fontSize: 13),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
