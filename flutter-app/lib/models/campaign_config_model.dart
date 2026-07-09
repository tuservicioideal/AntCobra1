/// Campaign runtime config synced from admin-app to Firestore.
class CampaignConfigModel {
  final int duracionDias;
  final double porcentajeComisionJefe;

  const CampaignConfigModel({
    this.duracionDias = 59,
    this.porcentajeComisionJefe = 15.0,
  });

  factory CampaignConfigModel.fromMap(Map<String, dynamic>? data) {
    if (data == null || data.isEmpty) return const CampaignConfigModel();
    return CampaignConfigModel(
      duracionDias: _toInt(data['duracion_dias'], 59),
      porcentajeComisionJefe:
          _toDouble(data['porcentaje_comision_jefe'], 15.0),
    );
  }

  static int _toInt(dynamic v, int fallback) {
    if (v is num) return v.toInt();
    return int.tryParse(v?.toString() ?? '') ?? fallback;
  }

  static double _toDouble(dynamic v, double fallback) {
    if (v is num) return v.toDouble();
    return double.tryParse(v?.toString() ?? '') ?? fallback;
  }
}
