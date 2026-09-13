import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/client_model.dart';
import '../models/whatsapp_plantilla.dart';
import '../services/auth_service.dart';
import '../services/whatsapp_plantilla_service.dart';
import '../widgets/adaptive_sheet.dart';
import 'phone_contact_launcher.dart';
import 'whatsapp_plantilla_renderer.dart';

/// Abre WhatsApp con plantilla elegida (o fallback si no hay ninguna).
Future<bool> openWhatsAppWithPlantilla({
  required BuildContext context,
  required ClientModel client,
  String? phone,
}) async {
  final tel = (phone ?? client.telefonoMovil).trim();
  if (tel.isEmpty) return false;

  final auth = context.read<AuthService>();
  final uid = auth.profile?.uid ?? '';
  final gestorNombre = auth.profile?.nombre ?? '';
  final values = buildWhatsAppPlaceholderMap(
    client: client,
    gestorNombre: gestorNombre,
  );

  final service = WhatsAppPlantillaService();
  List<WhatsAppPlantilla> plantillas = [];
  try {
    plantillas = await service.loadActivasParaEnvio(uid);
  } catch (_) {
    plantillas = [];
  }

  if (!context.mounted) return false;

  String message;
  if (plantillas.isEmpty) {
    message = buildWhatsAppMessage(
      clientName: client.displayName,
      values: values,
    );
  } else if (plantillas.length == 1) {
    final p = plantillas.first;
    message = renderWhatsAppPlantilla(p.cuerpo, values: values);
    await service.setLastUsedId(p.id);
  } else {
    final selected = await pickWhatsAppPlantilla(
      context: context,
      plantillas: plantillas,
      values: values,
    );
    if (!context.mounted) return false;
    if (selected == null) return false;
    message = renderWhatsAppPlantilla(selected.cuerpo, values: values);
    await service.setLastUsedId(selected.id);
  }

  return launchWhatsApp(
    phone: tel,
    clientName: client.displayName,
    message: message,
  );
}

Future<WhatsAppPlantilla?> pickWhatsAppPlantilla({
  required BuildContext context,
  required List<WhatsAppPlantilla> plantillas,
  required Map<String, String> values,
}) {
  return AdaptiveSheet.show<WhatsAppPlantilla>(
    context: context,
    builder: (ctx) {
      return SafeArea(
        child: ListView.separated(
          shrinkWrap: true,
          padding: const EdgeInsets.fromLTRB(8, 8, 8, 16),
          itemCount: plantillas.length + 1,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (context, i) {
            if (i == 0) {
              return const ListTile(
                title: Text(
                  'Elegir mensaje WhatsApp',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
              );
            }
            final p = plantillas[i - 1];
            final preview = renderWhatsAppPlantilla(p.cuerpo, values: values);
            return ListTile(
              leading: Icon(
                p.isEmpresa ? Icons.business : Icons.person_outline,
                color: p.isEmpresa
                    ? AppTheme.primaryColor
                    : const Color(0xFF25D366),
              ),
              title: Text(
                p.nombre,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              subtitle: Text(
                [
                  if (p.isEmpresa) 'Empresa',
                  if (p.predeterminada) 'Por defecto',
                  preview,
                ].join(' · '),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
              onTap: () => Navigator.pop(ctx, p),
            );
          },
        ),
      );
    },
  );
}
