import 'package:flutter/material.dart';
import '../../config/theme.dart';
import '../../models/client_model.dart';

/// Muestra otras cuentas/deudas del mismo DNI y totales consolidados.
class ClientDetailDebtsSection extends StatelessWidget {
  final ClientModel currentClient;
  final List<ClientModel> relatedAccounts;
  final bool loading;

  const ClientDetailDebtsSection({
    super.key,
    required this.currentClient,
    required this.relatedAccounts,
    this.loading = false,
  });

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 12),
        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }

    final siblings = relatedAccounts
        .where((c) => c.id != currentClient.id)
        .toList();
    if (relatedAccounts.length <= 1 && siblings.isEmpty) {
      return const SizedBox.shrink();
    }

    final totalPend = relatedAccounts.fold<double>(
      0,
      (s, c) => s + c.importeDeudaPendiente,
    );
    final totalAsig = relatedAccounts.fold<double>(
      0,
      (s, c) => s + c.importeDeudaAsignada,
    );

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.account_balance_wallet_outlined,
                    size: 18, color: AppTheme.primaryColor),
                const SizedBox(width: 8),
                Text(
                  'Deudas del cliente (DNI)',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                    color: Colors.grey.shade800,
                  ),
                ),
                const Spacer(),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    '${relatedAccounts.length} cuenta${relatedAccounts.length == 1 ? '' : 's'}',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.primaryColor,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: _totalCell(
                    'Total asignada',
                    'S/ ${totalAsig.toStringAsFixed(2)}',
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _totalCell(
                    'Total pendiente',
                    'S/ ${totalPend.toStringAsFixed(2)}',
                    highlight: true,
                  ),
                ),
              ],
            ),
            if (siblings.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(
                'Otras cuentas',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey.shade600,
                ),
              ),
              const SizedBox(height: 6),
              ...siblings.map(_accountTile),
            ],
          ],
        ),
      ),
    );
  }

  Widget _totalCell(String label, String value, {bool highlight = false}) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: highlight
            ? Colors.red.shade50
            : Colors.grey.shade50,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 14,
              color: highlight ? Colors.red.shade700 : Colors.grey.shade800,
            ),
          ),
        ],
      ),
    );
  }

  Widget _accountTile(ClientModel c) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  c.codigoCliente,
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 12,
                  ),
                ),
                Text(
                  'Sección ${c.seccionKey} · ${c.estadoGestion}',
                  style: TextStyle(fontSize: 10, color: Colors.grey.shade600),
                ),
              ],
            ),
          ),
          Text(
            'S/ ${c.importeDeudaPendiente.toStringAsFixed(0)}',
            style: TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 12,
              color: Colors.grey.shade800,
            ),
          ),
        ],
      ),
    );
  }
}
