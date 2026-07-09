import 'package:flutter/material.dart';
import '../models/notification_model.dart';
import '../services/notification_service.dart';

/// Screen that displays the user's notifications with expandable details.
class NotificationsScreen extends StatefulWidget {
  final String uid;

  const NotificationsScreen({super.key, required this.uid});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final _service = NotificationService();
  String? _expandedId;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notificaciones'),
        backgroundColor: Colors.white,
        foregroundColor: Colors.grey[900],
        elevation: 0.5,
      ),
      body: StreamBuilder<List<NotificationModel>>(
        stream: _service.streamNotifications(widget.uid),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          final notifications = snapshot.data ?? [];

          if (notifications.isEmpty) {
            return Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.notifications_none, size: 56, color: Colors.grey[300]),
                  const SizedBox(height: 12),
                  Text('No hay notificaciones',
                      style: TextStyle(color: Colors.grey[500], fontSize: 15)),
                ],
              ),
            );
          }

          return ListView.builder(
            padding: const EdgeInsets.symmetric(vertical: 8),
            itemCount: notifications.length,
            itemBuilder: (context, index) =>
                _buildNotificationCard(notifications[index]),
          );
        },
      ),
    );
  }

  Widget _buildNotificationCard(NotificationModel notif) {
    final isExpanded = _expandedId == notif.id;
    final tipoIcon = _iconForTipo(notif.tipo);
    final tipoColor = _colorForTipo(notif.tipo);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      elevation: notif.leida ? 0 : 1,
      color: notif.leida ? Colors.white : const Color(0xFFF0F0FF),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Column(
        children: [
          // Header
          InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: () => setState(() {
              _expandedId = isExpanded ? null : notif.id;
            }),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Unread dot
                  if (!notif.leida)
                    Container(
                      width: 8, height: 8,
                      margin: const EdgeInsets.only(top: 6, right: 10),
                      decoration: const BoxDecoration(
                        color: Color(0xFF6366F1),
                        shape: BoxShape.circle,
                      ),
                    )
                  else
                    const SizedBox(width: 18),

                  Icon(tipoIcon, size: 20, color: tipoColor),
                  const SizedBox(width: 8),

                  // Content
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(notif.titulo,
                            style: const TextStyle(
                                fontWeight: FontWeight.w600, fontSize: 14)),
                        if (notif.tipo == 'reparto_call' && notif.nuevasCuentasCount > 0)
                          Padding(
                            padding: const EdgeInsets.only(top: 2),
                            child: Text(
                              '${notif.nuevasCuentasCount} cuenta(s) nueva(s)',
                              style: TextStyle(
                                fontSize: 11,
                                color: Colors.green[700],
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        const SizedBox(height: 3),
                        Text(notif.mensaje,
                            style: TextStyle(
                                fontSize: 12, color: Colors.grey[600])),
                        const SizedBox(height: 4),
                        Text(notif.fechaStr,
                            style: TextStyle(
                                fontSize: 11, color: Colors.grey[400])),
                      ],
                    ),
                  ),

                  // Actions
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (!notif.leida)
                        IconButton(
                          icon: const Icon(Icons.check, size: 18),
                          color: const Color(0xFF6366F1),
                          tooltip: 'Marcar como leída',
                          onPressed: () => _service.markAsRead(notif.id),
                          constraints: const BoxConstraints(
                              minWidth: 32, minHeight: 32),
                          padding: EdgeInsets.zero,
                        ),
                      Icon(
                        isExpanded
                            ? Icons.expand_less
                            : Icons.expand_more,
                        size: 20,
                        color: Colors.grey[400],
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),

          // Expanded details
          if (isExpanded && notif.detalles.isNotEmpty)
            Container(
              margin: const EdgeInsets.fromLTRB(14, 0, 14, 14),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.grey[50],
                borderRadius: BorderRadius.circular(10),
              ),
              child: Column(
                children: notif.detalles.map(_buildDetailRow).toList(),
              ),
            ),
        ],
      ),
    );
  }

  IconData _iconForTipo(String tipo) {
    switch (tipo) {
      case 'reparto_call':
        return Icons.call_split;
      case 'base_actualizada':
        return Icons.sync;
      case 'cliente_reasignado':
        return Icons.swap_horiz;
      default:
        return Icons.notifications_outlined;
    }
  }

  Color _colorForTipo(String tipo) {
    switch (tipo) {
      case 'reparto_call':
        return const Color(0xFF6366F1);
      case 'base_actualizada':
        return Colors.blue[600]!;
      default:
        return Colors.grey[600]!;
    }
  }

  Widget _buildDetailRow(NotificationDetail detail) {
    IconData icon;
    Color color;
    switch (detail.tipo) {
      case 'nuevo':
        icon = Icons.person_add;
        color = Colors.green[600]!;
        break;
      case 'actualizado':
        icon = Icons.refresh;
        color = Colors.blue[600]!;
        break;
      case 'removido':
        icon = Icons.person_remove;
        color = Colors.red[500]!;
        break;
      default:
        icon = Icons.info_outline;
        color = Colors.grey[600]!;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${detail.nombre} (${detail.codigoCliente})',
                  style: const TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 12),
                ),
                const SizedBox(height: 2),
                Text(detail.mensaje,
                    style: TextStyle(fontSize: 11, color: Colors.grey[600])),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
