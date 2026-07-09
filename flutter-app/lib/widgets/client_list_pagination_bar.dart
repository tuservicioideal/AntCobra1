import 'package:flutter/material.dart';

import '../utils/client_list_pagination.dart';

/// Compact prev/next bar for paginated client lists.
class ClientListPaginationBar extends StatelessWidget {
  const ClientListPaginationBar({
    super.key,
    required this.pagination,
    required this.onPageChanged,
    this.compact = false,
  });

  final ClientListPagination pagination;
  final ValueChanged<int> onPageChanged;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    if (!pagination.needsBar) return const SizedBox.shrink();

    final from = pagination.totalItems == 0 ? 0 : pagination.startIndex + 1;
    final to = pagination.endIndex;
    final label = '$from–$to de ${pagination.totalItems}';

    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 8 : 16,
        vertical: compact ? 4 : 8,
      ),
      child: Row(
        children: [
          TextButton.icon(
            onPressed: pagination.hasPrevious
                ? () => onPageChanged(pagination.page - 1)
                : null,
            icon: const Icon(Icons.chevron_left, size: 20),
            label: Text(compact ? '' : 'Anterior'),
            style: TextButton.styleFrom(
              padding: compact
                  ? const EdgeInsets.symmetric(horizontal: 4)
                  : null,
              minimumSize: compact ? const Size(36, 36) : null,
            ),
          ),
          Expanded(
            child: Text(
              compact
                  ? '$label · ${pagination.page + 1}/${pagination.totalPages}'
                  : '$label · Página ${pagination.page + 1} de ${pagination.totalPages}',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: compact ? 11 : 12,
                color: Colors.grey.shade700,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          TextButton.icon(
            onPressed: pagination.hasNext
                ? () => onPageChanged(pagination.page + 1)
                : null,
            icon: const Icon(Icons.chevron_right, size: 20),
            label: Text(compact ? '' : 'Siguiente'),
            style: TextButton.styleFrom(
              padding: compact
                  ? const EdgeInsets.symmetric(horizontal: 4)
                  : null,
              minimumSize: compact ? const Size(36, 36) : null,
            ),
          ),
        ],
      ),
    );
  }
}
