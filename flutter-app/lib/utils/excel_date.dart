// Parseo de fechas del Excel bancario (espejo de admin-app `date_utils.py`).

DateTime? parseExcelFecha(dynamic value) {
  if (value == null) return null;

  if (value is DateTime) {
    return DateTime(value.year, value.month, value.day);
  }

  final text = value.toString().trim();
  if (text.isEmpty) return null;
  final lower = text.toLowerCase();
  if (lower == 'none' || lower == 'null' || lower == 'nan' || lower == '-') {
    return null;
  }

  // Excel serial number (días desde 1899-12-30).
  final serial = double.tryParse(text.replaceAll(',', '.'));
  if (serial != null && serial > 30000 && serial < 60000) {
    final base = DateTime(1899, 12, 30);
    return base.add(Duration(days: serial.floor()));
  }

  // yyyy-MM-dd (ISO) o con hora.
  if (RegExp(r'^\d{4}-\d{2}-\d{2}').hasMatch(text)) {
    final iso = DateTime.tryParse(text);
    if (iso != null) return DateTime(iso.year, iso.month, iso.day);
  }

  // yyyy/MM/dd
  final slashYmd = RegExp(r'^(\d{4})/(\d{1,2})/(\d{1,2})$').firstMatch(text);
  if (slashYmd != null) {
    return DateTime(
      int.parse(slashYmd.group(1)!),
      int.parse(slashYmd.group(2)!),
      int.parse(slashYmd.group(3)!),
    );
  }

  // dd/MM/yyyy (preferido) o MM/dd/yyyy si el 2.º componente > 12.
  final slash = RegExp(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$').firstMatch(text);
  if (slash != null) {
    final a = int.parse(slash.group(1)!);
    final b = int.parse(slash.group(2)!);
    var y = int.parse(slash.group(3)!);
    if (y < 100) y += 2000;
    if (b > 12) {
      // MM/dd/yyyy inequívoco
      return DateTime(y, a, b);
    }
    // dd/MM/yyyy (formato bancario PE)
    return DateTime(y, b, a);
  }

  // dd-MM-yyyy
  final dash = RegExp(r'^(\d{1,2})-(\d{1,2})-(\d{2,4})$').firstMatch(text);
  if (dash != null) {
    final d = int.parse(dash.group(1)!);
    final m = int.parse(dash.group(2)!);
    var y = int.parse(dash.group(3)!);
    if (y < 100) y += 2000;
    return DateTime(y, m, d);
  }

  return null;
}

/// Normaliza a medianoche local (solo fecha).
DateTime dateOnly(DateTime d) => DateTime(d.year, d.month, d.day);
