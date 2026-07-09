import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'config/firebase_config.dart';
import 'services/auth_service.dart';
import 'services/campana_banco_filter_notifier.dart';
import 'services/connectivity_service.dart';
import 'services/location_service.dart';
import 'services/sync_status_service.dart';
import 'services/tracking_service.dart';
import 'services/route_refresh_service.dart';
import 'app.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  if (!kIsWeb) {
    GoogleFonts.config.allowRuntimeFetching = false;
  }

  FlutterError.onError = (details) {
    FlutterError.presentError(details);
    debugPrint('FlutterError: ${details.exceptionAsString()}');
  };

  ErrorWidget.builder = (FlutterErrorDetails details) {
    return Material(
      color: const Color(0xFFF8FAFC),
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Color(0xFFDC2626)),
              const SizedBox(height: 16),
              const Text(
                'Error al mostrar la pantalla',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              Text(
                details.exceptionAsString(),
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
              ),
            ],
          ),
        ),
      ),
    );
  };

  if (!kIsWeb) {
    await SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
    ]);
    SystemChrome.setSystemUIOverlayStyle(
      const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
      ),
    );
  }

  // Initialize Firebase
  await Firebase.initializeApp(
    options: FirebaseConfig.currentPlatform,
  );

  // Enable Firestore offline persistence (enabled by default on mobile)

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthService()),
        ChangeNotifierProvider(create: (_) => CampanaBancoFilterNotifier()),
        ChangeNotifierProvider(create: (_) => ConnectivityService()),
        ChangeNotifierProvider(create: (_) => TrackingService()),
        ChangeNotifierProvider(create: (_) => LocationService()),
        ChangeNotifierProxyProvider2<ConnectivityService, TrackingService,
            SyncStatusService>(
          create: (ctx) => SyncStatusService(
            ctx.read<ConnectivityService>(),
            ctx.read<TrackingService>(),
          ),
          update: (_, connectivity, tracking, previous) =>
              previous ?? SyncStatusService(connectivity, tracking),
        ),
        ChangeNotifierProvider(create: (_) => RouteRefreshService()),
      ],
      child: const RecaudoLegalApp(),
    ),
  );
}
