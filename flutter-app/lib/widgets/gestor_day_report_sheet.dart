import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:latlong2/latlong.dart';

import '../config/theme.dart';
import '../models/client_model.dart';
import '../models/tracking_models.dart';
import '../utils/trail_analysis.dart';
import '../utils/trail_filter.dart';

/// Panel con el reporte diario de un gestor en campo (sheet o dialog).
class GestorDayReportSheet extends StatelessWidget {
  const GestorDayReportSheet({
    super.key,
    required this.gestorNombre,
    required this.fechaDia,
    required this.filtered,
    required this.proximity,
    required this.onFocusPoint,
  });

  final String gestorNombre;
  final String fechaDia;
  final FilteredTrail filtered;
  final List<ClientProximityResult> proximity;
  final void Function(LatLng point) onFocusPoint;

  @override
  Widget build(BuildContext context) {
    final timeFmt = DateFormat('HH:mm');
    final visits = filtered.visitPoints;
    final managed = proximity.where((p) => p.wasManaged).toList();
    final nearby = proximity.where((p) => p.passedNearby).toList();
    final withCoords = proximity.length;
    final coveragePct =
        withCoords > 0 ? (managed.length / withCoords * 100) : 0.0;

    DateTime? first;
    DateTime? last;
    if (filtered.firstPoint != null) {
      first = filtered.firstPoint!.timestamp?.toDate() ??
          DateTime.tryParse(filtered.firstPoint!.fecha);
    }
    if (filtered.lastPoint != null) {
      last = filtered.lastPoint!.timestamp?.toDate() ??
          DateTime.tryParse(filtered.lastPoint!.fecha);
    }
    final activeLabel = (first != null && last != null)
        ? '${timeFmt.format(first)} – ${timeFmt.format(last)}'
        : 'Sin datos';

    final maxH = MediaQuery.sizeOf(context).height * 0.85;

    return SafeArea(
      child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: maxH),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.grey.shade300,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 8, 4),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Reporte del día',
                          style: Theme.of(context).textTheme.titleMedium
                              ?.copyWith(fontWeight: FontWeight.w700),
                        ),
                        Text(
                          '$gestorNombre · $fechaDia',
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey.shade600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
            ),
            Flexible(
              child: ListView(
                shrinkWrap: true,
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                children: [
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      _KpiChip(
                        label: 'Km',
                        value: filtered.km.toStringAsFixed(1),
                        color: AppTheme.primaryColor,
                      ),
                      _KpiChip(
                        label: 'Activo',
                        value: activeLabel,
                        color: AppTheme.info,
                      ),
                      _KpiChip(
                        label: 'Paradas',
                        value: '${filtered.stays.length}',
                        color: AppTheme.warning,
                      ),
                      _KpiChip(
                        label: 'Gestiones',
                        value: '${visits.length}',
                        color: AppTheme.success,
                      ),
                      _KpiChip(
                        label: 'Cobertura',
                        value:
                            '${managed.length}/$withCoords (${coveragePct.toStringAsFixed(0)}%)',
                        color: AppTheme.accent,
                      ),
                      _KpiChip(
                        label: 'Sin gestionar',
                        value: '${nearby.length}',
                        color: AppTheme.danger,
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  Text(
                    'Timeline de gestiones',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const SizedBox(height: 8),
                  if (visits.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Text(
                        'Sin gestiones registradas este día',
                        style: TextStyle(color: Colors.grey.shade500),
                      ),
                    )
                  else
                    ...visits.map((v) {
                      final t = v.timestamp?.toDate() ??
                          DateTime.tryParse(v.fecha);
                      final client = _findClient(v);
                      final homeDist = client != null
                          ? TrailAnalysis.visitToHomeDistanceMeters(v, client)
                          : null;
                      final farFromHome =
                          homeDist != null && homeDist > 150;
                      return Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        child: ListTile(
                          leading: CircleAvatar(
                            backgroundColor: AppTheme.getStatusColor(v.estado)
                                .withValues(alpha: 0.2),
                            child: Icon(
                              Icons.location_on,
                              color: AppTheme.getStatusColor(v.estado),
                              size: 20,
                            ),
                          ),
                          title: Text(
                            v.cliente.isNotEmpty
                                ? v.cliente
                                : (client?.displayName ?? 'Cliente'),
                            style: const TextStyle(
                              fontWeight: FontWeight.w600,
                              fontSize: 13,
                            ),
                          ),
                          subtitle: Text(
                            [
                              if (t != null) timeFmt.format(t),
                              if (v.estado.isNotEmpty) v.estado,
                              if (homeDist != null)
                                '${homeDist.toStringAsFixed(0)} m del domicilio'
                                    '${farFromHome ? ' ⚠' : ''}',
                            ].join(' · '),
                            style: TextStyle(
                              fontSize: 11,
                              color: farFromHome
                                  ? AppTheme.danger
                                  : Colors.grey.shade600,
                            ),
                          ),
                          trailing: const Icon(Icons.my_location, size: 18),
                          onTap: () {
                            Navigator.pop(context);
                            onFocusPoint(LatLng(v.lat, v.lng));
                          },
                        ),
                      );
                    }),
                  const SizedBox(height: 16),
                  Text(
                    'Pasó cerca sin gestionar',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Clientes a ≤80 m del recorrido sin visita registrada',
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.grey.shade500,
                    ),
                  ),
                  const SizedBox(height: 8),
                  if (nearby.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Text(
                        'Ningún acercamiento sin gestión',
                        style: TextStyle(color: Colors.grey.shade500),
                      ),
                    )
                  else
                    ...nearby.map((r) {
                      final t = r.closestPoint?.timestamp?.toDate() ??
                          (r.closestPoint != null
                              ? DateTime.tryParse(r.closestPoint!.fecha)
                              : null);
                      return Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        child: ListTile(
                          leading: CircleAvatar(
                            backgroundColor:
                                AppTheme.warning.withValues(alpha: 0.2),
                            child: const Icon(
                              Icons.near_me,
                              color: AppTheme.warning,
                              size: 20,
                            ),
                          ),
                          title: Text(
                            r.client.displayName,
                            style: const TextStyle(
                              fontWeight: FontWeight.w600,
                              fontSize: 13,
                            ),
                          ),
                          subtitle: Text(
                            [
                              if (t != null) timeFmt.format(t),
                              '${r.minDistanceMeters.toStringAsFixed(0)} m',
                              if (r.client.direccion.isNotEmpty)
                                r.client.direccion,
                            ].join(' · '),
                            style: TextStyle(
                              fontSize: 11,
                              color: Colors.grey.shade600,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                          trailing: const Icon(Icons.my_location, size: 18),
                          onTap: () {
                            Navigator.pop(context);
                            onFocusPoint(LatLng(
                              r.client.latitude,
                              r.client.longitude,
                            ));
                          },
                        ),
                      );
                    }),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  ClientModel? _findClient(TrailPoint visit) {
    for (final r in proximity) {
      if (visit.clienteId.isNotEmpty &&
          (visit.clienteId == r.client.id ||
              visit.clienteId == r.client.codigoCliente)) {
        return r.client;
      }
      if (visit.cliente.isNotEmpty &&
          visit.cliente.toLowerCase() ==
              r.client.displayName.toLowerCase()) {
        return r.client;
      }
    }
    return null;
  }
}

class _KpiChip extends StatelessWidget {
  const _KpiChip({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 10,
              color: color,
              fontWeight: FontWeight.w600,
            ),
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
