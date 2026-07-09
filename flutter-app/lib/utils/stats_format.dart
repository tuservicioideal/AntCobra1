import 'package:intl/intl.dart';

String formatMoneyCompact(double value) {
  if (value >= 1000000) {
    return 'S/${(value / 1000000).toStringAsFixed(1)}M';
  }
  if (value >= 1000) {
    return 'S/${(value / 1000).toStringAsFixed(1)}K';
  }
  return 'S/${value.toStringAsFixed(0)}';
}

String formatMoneyFull(double value) {
  final fmt = NumberFormat.currency(locale: 'es_PE', symbol: 'S/ ', decimalDigits: 2);
  return fmt.format(value);
}

String formatPct(double value, {int decimals = 1}) {
  return '${value.toStringAsFixed(decimals)}%';
}
