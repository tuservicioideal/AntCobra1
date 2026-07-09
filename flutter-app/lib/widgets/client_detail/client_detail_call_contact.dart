import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../config/theme.dart';
import '../../models/client_model.dart';
import '../../utils/phone_contact_launcher.dart';

/// Contact strip for call-center gestors: phone, WhatsApp, email, address (no GPS).
class ClientDetailCallContact extends StatelessWidget {
  final ClientModel client;

  const ClientDetailCallContact({super.key, required this.client});

  @override
  Widget build(BuildContext context) {
    final phone = client.telefonoMovil.trim();
    final email = client.correo.trim();

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(Icons.call, size: 18, color: AppTheme.primaryColor),
              const SizedBox(width: 8),
              const Text(
                'Contacto telefónico',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          if (phone.isNotEmpty)
            _phoneRow(context, phone)
          else
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Text(
                'Sin teléfono registrado en cartera',
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
              ),
            ),
          if (email.isNotEmpty) ...[
            const SizedBox(height: 8),
            _emailRow(context, email),
          ],
          if (client.fullAddress.isNotEmpty) ...[
            const SizedBox(height: 8),
            _infoRow(Icons.location_on_outlined, client.fullAddress),
          ],
          if (client.referencia.trim().isNotEmpty) ...[
            const SizedBox(height: 6),
            _infoRow(Icons.notes, client.referencia.trim()),
          ],
        ],
      ),
    );
  }

  Widget _phoneRow(BuildContext context, String phone) {
    return Material(
      color: AppTheme.primaryColor.withValues(alpha: 0.06),
      borderRadius: BorderRadius.circular(10),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.primaryColor.withValues(alpha: 0.12),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.phone, color: AppTheme.primaryColor, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Móvil',
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.grey.shade600,
                    ),
                  ),
                  Text(
                    phone,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                ],
              ),
            ),
            _actionIconButton(
              icon: Icons.phone,
              tooltip: 'Llamar',
              color: AppTheme.primaryColor,
              onTap: () => _dial(context, phone),
            ),
            const SizedBox(width: 4),
            _actionIconButton(
              icon: Icons.chat,
              tooltip: 'WhatsApp',
              color: const Color(0xFF25D366),
              onTap: () => _openWhatsApp(context, phone),
            ),
          ],
        ),
      ),
    );
  }

  Widget _emailRow(BuildContext context, String email) {
    return Material(
      color: Colors.blue.withValues(alpha: 0.05),
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        onTap: () => _sendEmail(context, email),
        borderRadius: BorderRadius.circular(10),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.blue.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.mail_outline, color: Colors.blue, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Correo',
                      style: TextStyle(
                        fontSize: 11,
                        color: Colors.grey.shade600,
                      ),
                    ),
                    Text(
                      email,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.send_outlined, color: Colors.blue.shade700, size: 20),
            ],
          ),
        ),
      ),
    );
  }

  Widget _actionIconButton({
    required IconData icon,
    required String tooltip,
    required Color color,
    required VoidCallback onTap,
  }) {
    return Material(
      color: color.withValues(alpha: 0.12),
      shape: const CircleBorder(),
      child: InkWell(
        onTap: onTap,
        customBorder: const CircleBorder(),
        child: Tooltip(
          message: tooltip,
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: Icon(icon, color: color, size: 20),
          ),
        ),
      ),
    );
  }

  Widget _infoRow(IconData icon, String text) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 16, color: Colors.grey.shade600),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            text,
            style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
          ),
        ),
      ],
    );
  }

  Future<void> _dial(BuildContext context, String phone) async {
    final normalized = phone.replaceAll(RegExp(r'[^\d+]'), '');
    final uri = Uri(scheme: 'tel', path: normalized);
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('No se pudo abrir el marcador para $phone')),
        );
      }
    }
  }

  Future<void> _openWhatsApp(BuildContext context, String phone) async {
    final launched = await launchWhatsApp(
      phone: phone,
      clientName: client.displayName,
    );
    if (!context.mounted || launched) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('No se pudo abrir WhatsApp. Verifique que esté instalado.'),
      ),
    );
  }

  Future<void> _sendEmail(BuildContext context, String email) async {
    final uri = Uri(
      scheme: 'mailto',
      path: email,
      queryParameters: {
        'subject': 'Gestión de cuenta — ${client.displayName}',
      },
    );
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('No se pudo abrir el correo para $email')),
        );
      }
    }
  }
}
