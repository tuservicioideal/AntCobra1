import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// App-wide theme and color constants for App Recaudo Legal.
class AppTheme {
  AppTheme._();

  // ── Brand Colors ──
  static const Color primary = Color(0xFF4F46E5);       // Indigo-600
  static const Color primaryDark = Color(0xFF3730A3);    // Indigo-800
  static const Color primaryLight = Color(0xFFEEF2FF);   // Indigo-50
  static const Color accent = Color(0xFF7C3AED);         // Violet-600

  // ── Semantic Colors ──
  static const Color success = Color(0xFF059669);        // Emerald-600
  static const Color successLight = Color(0xFFD1FAE5);   // Emerald-100
  static const Color warning = Color(0xFFF59E0B);        // Amber-500
  static const Color warningLight = Color(0xFFFEF3C7);   // Amber-100
  static const Color danger = Color(0xFFDC2626);         // Red-600
  static const Color dangerLight = Color(0xFFFEE2E2);    // Red-100
  static const Color info = Color(0xFF3B82F6);           // Blue-500
  static const Color infoLight = Color(0xFFDBEAFE);      // Blue-100
  static const Color rose = Color(0xFFE11D48);           // Rose-600

  // ── Neutral Colors ──
  static const Color textPrimary = Color(0xFF1E293B);    // Slate-800
  static const Color textSecondary = Color(0xFF64748B);  // Slate-500
  static const Color textMuted = Color(0xFF94A3B8);      // Slate-400
  static const Color background = Color(0xFFF8FAFC);     // Slate-50
  static const Color surface = Color(0xFFFFFFFF);
  static const Color border = Color(0xFFE2E8F0);         // Slate-200
  static const Color divider = Color(0xFFF1F5F9);        // Slate-100

  // ── Status Colors ──
  static const Color statusPendiente = Color(0xFF94A3B8);
  static const Color statusHabido = Color(0xFF22C55E);
  static const Color statusVisitadoHabido = Color(0xFF22C55E);
  static const Color statusNoHabido = Color(0xFFF59E0B);
  static const Color statusVisitadoNoHabido = Color(0xFFF59E0B);
  static const Color statusInubicable = Color(0xFFEF4444);
  static const Color statusFallecido = Color(0xFFEF4444);
  static const Color statusSuplantacion = Color(0xFFE11D48);
  static const Color statusPagoNoReg = Color(0xFF3B82F6);
  static const Color statusPagoNoRegistrado = Color(0xFF3B82F6);

  // Aliases used across screens
  static const Color primaryColor = primary;
  static const Color accentColor = accent;

  // ── High Value ──
  static const Color highValue = Color(0xFFF97316);      // Orange-500
  static const double highValueThreshold = 500.0;

  /// Get a color for a given gestion status string.
  static Color getStatusColor(String estado) {
    switch (estado) {
      case 'visitado_habido':
        return statusHabido;
      case 'visitado_no_habido':
        return statusNoHabido;
      case 'fallecido_inubicable':
        return statusInubicable;
      case 'suplantacion':
        return statusSuplantacion;
      case 'pago_no_registrado':
        return statusPagoNoReg;
      case 'devolucion_pendiente':
        return const Color(0xFF7C3AED);
      case 'pendiente':
        return statusPendiente;
      default:
        return statusPendiente;
    }
  }

  /// Light theme data
  static ThemeData get lightTheme {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primary,
        brightness: Brightness.light,
      ).copyWith(
        primary: primary,
        secondary: accent,
        surface: surface,
        error: danger,
      ),
      scaffoldBackgroundColor: background,
    );

    final textTheme = _buildTextTheme(base.textTheme);

    return base.copyWith(
      // No heredar Inter en iconos Material (evita cuadros "tofu" en Icon/NavigationBar).
      iconTheme: const IconThemeData(),
      primaryIconTheme: const IconThemeData(color: Colors.white),
      textTheme: textTheme,
      appBarTheme: AppBarTheme(
        backgroundColor: primary,
        foregroundColor: Colors.white,
        elevation: 0,
        scrolledUnderElevation: 1,
        centerTitle: false,
        titleTextStyle: textTheme.titleLarge?.copyWith(color: Colors.white),
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: border),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          textStyle: textTheme.labelLarge,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          side: const BorderSide(color: border),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: background,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: primary, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: danger),
        ),
        hintStyle: textTheme.bodyMedium?.copyWith(color: textMuted),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: surface,
        selectedItemColor: primary,
        unselectedItemColor: textMuted,
        type: BottomNavigationBarType.fixed,
        elevation: 8,
      ),
      dividerTheme: const DividerThemeData(color: divider, thickness: 1),
      chipTheme: ChipThemeData(
        backgroundColor: background,
        selectedColor: primaryLight,
        labelStyle: textTheme.bodyMedium?.copyWith(
          fontSize: 13,
          fontWeight: FontWeight.w500,
        ),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        side: const BorderSide(color: border),
      ),
    );
  }

  static TextTheme _buildTextTheme(TextTheme base) {
    if (kIsWeb) {
      return GoogleFonts.interTextTheme(base).copyWith(
        headlineLarge: GoogleFonts.inter(
          fontSize: 28,
          fontWeight: FontWeight.w800,
          color: textPrimary,
        ),
        headlineMedium: GoogleFonts.inter(
          fontSize: 22,
          fontWeight: FontWeight.w700,
          color: textPrimary,
        ),
        titleLarge: GoogleFonts.inter(
          fontSize: 18,
          fontWeight: FontWeight.w700,
          color: textPrimary,
        ),
        titleMedium: GoogleFonts.inter(
          fontSize: 16,
          fontWeight: FontWeight.w600,
          color: textPrimary,
        ),
        bodyLarge: GoogleFonts.inter(
          fontSize: 16,
          fontWeight: FontWeight.w400,
          color: textPrimary,
        ),
        bodyMedium: GoogleFonts.inter(
          fontSize: 14,
          fontWeight: FontWeight.w400,
          color: textSecondary,
        ),
        bodySmall: GoogleFonts.inter(
          fontSize: 12,
          fontWeight: FontWeight.w400,
          color: textMuted,
        ),
        labelLarge: GoogleFonts.inter(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: textPrimary,
        ),
        labelSmall: GoogleFonts.inter(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: textMuted,
          letterSpacing: 0.5,
        ),
      );
    }

    return base.copyWith(
      headlineLarge: base.headlineLarge?.copyWith(
        fontSize: 28,
        fontWeight: FontWeight.w800,
        color: textPrimary,
      ),
      headlineMedium: base.headlineMedium?.copyWith(
        fontSize: 22,
        fontWeight: FontWeight.w700,
        color: textPrimary,
      ),
      titleLarge: base.titleLarge?.copyWith(
        fontSize: 18,
        fontWeight: FontWeight.w700,
        color: textPrimary,
      ),
      titleMedium: base.titleMedium?.copyWith(
        fontSize: 16,
        fontWeight: FontWeight.w600,
        color: textPrimary,
      ),
      bodyLarge: base.bodyLarge?.copyWith(
        fontSize: 16,
        fontWeight: FontWeight.w400,
        color: textPrimary,
      ),
      bodyMedium: base.bodyMedium?.copyWith(
        fontSize: 14,
        fontWeight: FontWeight.w400,
        color: textSecondary,
      ),
      bodySmall: base.bodySmall?.copyWith(
        fontSize: 12,
        fontWeight: FontWeight.w400,
        color: textMuted,
      ),
      labelLarge: base.labelLarge?.copyWith(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        color: textPrimary,
      ),
      labelSmall: base.labelSmall?.copyWith(
        fontSize: 11,
        fontWeight: FontWeight.w600,
        color: textMuted,
        letterSpacing: 0.5,
      ),
    );
  }
}
