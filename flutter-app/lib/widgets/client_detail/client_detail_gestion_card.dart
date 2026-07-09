import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../config/theme.dart';
import '../../services/nivel_catalog_service.dart';
import '../../utils/gestion_monto_rules.dart';

/// Management result form: channel, nivel dropdowns, register, special states.
class ClientDetailGestionCard extends StatelessWidget {
  final bool catalogLoading;
  final bool catalogLoaded;
  final NivelCatalogService nivelCatalog;
  final String canal;
  final String nivel1;
  final String nivel2;
  final String nivel3;
  final String nivel4;
  final String fechaPromesa;
  final TextEditingController montoController;
  final double deudaPendiente;
  final bool gpsReady;
  final bool saving;
  final ValueChanged<String> onCanalChanged;
  final ValueChanged<String> onNivel1Changed;
  final ValueChanged<String> onNivel2Changed;
  final ValueChanged<String> onNivel3Changed;
  final ValueChanged<String> onNivel4Changed;
  final VoidCallback onPickFechaPromesa;
  final ValueChanged<double> onMontoChanged;
  final VoidCallback onRegister;
  final void Function(String estado, String label) onSpecialStatus;
  final VoidCallback? onRequestReturn;
  final bool canRequestReturn;
  final bool lockCanalToTel;
  final bool requireGps;

  const ClientDetailGestionCard({
    super.key,
    required this.catalogLoading,
    required this.catalogLoaded,
    required this.nivelCatalog,
    required this.canal,
    required this.nivel1,
    required this.nivel2,
    required this.nivel3,
    required this.nivel4,
    required this.fechaPromesa,
    required this.montoController,
    required this.deudaPendiente,
    required this.gpsReady,
    required this.saving,
    required this.onCanalChanged,
    required this.onNivel1Changed,
    required this.onNivel2Changed,
    required this.onNivel3Changed,
    required this.onNivel4Changed,
    required this.onPickFechaPromesa,
    required this.onMontoChanged,
    required this.onRegister,
    required this.onSpecialStatus,
    this.onRequestReturn,
    this.canRequestReturn = false,
    this.lockCanalToTel = false,
    this.requireGps = true,
  });

  bool get _showMontoPanel => GestionMontoRules.requiresMontoPanel(
        n2: nivel2,
        n3: nivel3,
        n4: nivel4,
      );

  bool get _showFecha => GestionMontoRules.showFechaField(n2: nivel2);

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Resultado de la gestión',
            style: TextStyle(
              fontWeight: FontWeight.w600,
              fontSize: 14,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 10),
          if (catalogLoading)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            )
          else if (!catalogLoaded)
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.warningLight,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.warning.withValues(alpha: 0.3)),
              ),
              child: const Text(
                'Catálogo de niveles no disponible. Solicite al administrador que lo suba.',
                style: TextStyle(fontSize: 12),
              ),
            )
          else ...[
            if (lockCanalToTel)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
                decoration: BoxDecoration(
                  color: AppTheme.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppTheme.primary.withValues(alpha: 0.3)),
                ),
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.phone_in_talk, size: 18, color: AppTheme.primary),
                    SizedBox(width: 8),
                    Text(
                      'Gestión telefónica (Call Center)',
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 13,
                        color: AppTheme.primary,
                      ),
                    ),
                  ],
                ),
              )
            else
              Row(
                children: nivelCatalog.canales.map((c) {
                  final isSelected = canal == c;
                  return Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 3),
                      child: ElevatedButton(
                        onPressed: () => onCanalChanged(c),
                        style: ElevatedButton.styleFrom(
                          backgroundColor:
                              isSelected ? AppTheme.primary : AppTheme.divider,
                          foregroundColor:
                              isSelected ? Colors.white : AppTheme.textSecondary,
                          elevation: isSelected ? 1 : 0,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10),
                          ),
                          padding: const EdgeInsets.symmetric(vertical: 10),
                        ),
                        child: Text(
                          c == 'CAM' ? 'Campo' : 'Teléfono',
                          style: const TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 13,
                          ),
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
            const SizedBox(height: 10),
            _nivelDropdown(
              label: 'Nivel 1 — Tipo de contacto',
              value: nivel1,
              options: nivelCatalog.buildOptions(canal: canal).nivel1Opts,
              onChanged: (v) => onNivel1Changed(v ?? ''),
            ),
            if (nivel1.isNotEmpty) ...[
              const SizedBox(height: 8),
              _nivelDropdown(
                label: 'Nivel 2 — Resultado',
                value: nivel2,
                options:
                    nivelCatalog.buildOptions(canal: canal, n1: nivel1).nivel2Opts,
                onChanged: (v) => onNivel2Changed(v ?? ''),
              ),
            ],
            if (nivel2.isNotEmpty) ...[
              const SizedBox(height: 8),
              _nivelDropdown(
                label: 'Nivel 3 — Detalle',
                value: nivel3,
                options: nivelCatalog
                    .buildOptions(canal: canal, n1: nivel1, n2: nivel2)
                    .nivel3Opts,
                onChanged: (v) => onNivel3Changed(v ?? ''),
              ),
            ],
            if (nivel3.isNotEmpty) ...[
              const SizedBox(height: 8),
              _nivelDropdown(
                label: 'Nivel 4 — Sub-detalle',
                value: nivel4,
                options: nivelCatalog
                    .buildOptions(canal: canal, n1: nivel1, n2: nivel2, n3: nivel3)
                    .nivel4Opts,
                onChanged: (v) => onNivel4Changed(v ?? ''),
              ),
            ],
            if (_showMontoPanel) ...[
              const SizedBox(height: 10),
              _buildMontoPanel(showFecha: _showFecha),
            ],
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: ((requireGps && !gpsReady) ||
                        saving ||
                        nivel1.isEmpty ||
                        nivel2.isEmpty ||
                        nivel3.isEmpty ||
                        nivel4.isEmpty)
                    ? null
                    : onRegister,
                icon: const Icon(Icons.send, size: 18),
                label: const Text(
                  'Registrar gestión',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ),
          ],
          const SizedBox(height: 12),
          Row(
            children: [
              const Expanded(child: Divider()),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                child: Text(
                  'Estados especiales',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey.shade400,
                    letterSpacing: 0.8,
                  ),
                ),
              ),
              const Expanded(child: Divider()),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: _specialButton(
                  label: 'Suplantación',
                  color: AppTheme.statusSuplantacion,
                  icon: Icons.warning_amber_outlined,
                  enabled: gpsReady && !saving,
                  onTap: () => onSpecialStatus('suplantacion', 'Suplantación'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _specialButton(
                  label: 'Pago no registrado',
                  color: AppTheme.statusPagoNoRegistrado,
                  icon: Icons.money_off_outlined,
                  enabled: gpsReady && !saving,
                  onTap: () =>
                      onSpecialStatus('pago_no_registrado', 'Pago No Registrado'),
                ),
              ),
            ],
          ),
          if (canRequestReturn && onRequestReturn != null) ...[
            const SizedBox(height: 8),
            _specialButton(
              label: 'Zona inaccesible — Devolver',
              color: const Color(0xFF7C3AED),
              icon: Icons.undo_outlined,
              enabled: gpsReady && !saving,
              onTap: onRequestReturn!,
            ),
          ],
          if (!_showMontoPanel) ...[
            const SizedBox(height: 10),
            _buildOptionalMontoRow(),
          ],
        ],
      ),
    );
  }

  /// Compact monto row for special states when nivel panel is not active.
  Widget _buildOptionalMontoRow() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Importe referido (opcional)',
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: Colors.grey.shade600,
          ),
        ),
        const SizedBox(height: 6),
        TextField(
          controller: montoController,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          inputFormatters: [
            FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d{0,2}')),
          ],
          decoration: InputDecoration(
            labelText: 'Monto (S/)',
            hintText: GestionMontoRules.montoHint(deudaPendiente),
            border: const OutlineInputBorder(),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            prefixIcon: const Icon(Icons.payments_outlined, size: 18),
            isDense: true,
          ),
          onChanged: (v) => onMontoChanged(double.tryParse(v) ?? 0),
        ),
      ],
    );
  }

  Widget _buildMontoPanel({required bool showFecha}) {
    final title = GestionMontoRules.panelTitle(n2: nivel2, n3: nivel3);
    final montoLabel = GestionMontoRules.montoLabel(n2: nivel2, n3: nivel3);

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.primaryLight,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.primary.withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(Icons.account_balance_wallet_outlined,
                  size: 18, color: AppTheme.primary),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                    color: AppTheme.primary,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Opcional — puede registrar la gestión sin completar estos datos.',
            style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
          ),
          if (deudaPendiente > 0) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                _quickAmountChip(
                  '50% deuda',
                  (deudaPendiente * 0.5).toStringAsFixed(2),
                ),
                _quickAmountChip(
                  'Deuda total',
                  deudaPendiente.toStringAsFixed(2),
                ),
              ],
            ),
          ],
          const SizedBox(height: 10),
          if (showFecha)
            Row(
              children: [
                Expanded(
                  child: GestureDetector(
                    onTap: onPickFechaPromesa,
                    child: InputDecorator(
                      decoration: const InputDecoration(
                        labelText: 'Fecha promesa',
                        border: OutlineInputBorder(),
                        filled: true,
                        fillColor: Colors.white,
                        contentPadding:
                            EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                        prefixIcon: Icon(Icons.calendar_today, size: 18),
                        isDense: true,
                      ),
                      child: Text(
                        fechaPromesa.isEmpty ? 'Seleccionar' : fechaPromesa,
                        style: TextStyle(
                          fontSize: 13,
                          color: fechaPromesa.isEmpty
                              ? AppTheme.textMuted
                              : AppTheme.textPrimary,
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(child: _montoTextField(montoLabel)),
              ],
            )
          else
            _montoTextField(montoLabel),
        ],
      ),
    );
  }

  Widget _quickAmountChip(String label, String amount) {
    return ActionChip(
      label: Text(label, style: const TextStyle(fontSize: 11)),
      onPressed: () {
        montoController.text = amount;
        onMontoChanged(double.tryParse(amount) ?? 0);
      },
      backgroundColor: Colors.white,
      side: BorderSide(color: AppTheme.primary.withValues(alpha: 0.3)),
      padding: const EdgeInsets.symmetric(horizontal: 4),
    );
  }

  Widget _montoTextField(String label) {
    return TextField(
      controller: montoController,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      inputFormatters: [
        FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d{0,2}')),
      ],
      decoration: InputDecoration(
        labelText: label,
        hintText: GestionMontoRules.montoHint(deudaPendiente),
        border: const OutlineInputBorder(),
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        prefixIcon: const Icon(Icons.attach_money, size: 18),
        isDense: true,
      ),
      onChanged: (v) => onMontoChanged(double.tryParse(v) ?? 0),
    );
  }

  Widget _nivelDropdown({
    required String label,
    required String value,
    required List<String> options,
    required ValueChanged<String?> onChanged,
  }) {
    return DropdownButtonFormField<String>(
      value: value.isNotEmpty && options.contains(value) ? value : null,
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(fontSize: 12),
        border: const OutlineInputBorder(),
        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        isDense: true,
      ),
      isExpanded: true,
      items: options
          .map((opt) => DropdownMenuItem(
                value: opt,
                child: Text(opt, style: const TextStyle(fontSize: 13)),
              ))
          .toList(),
      onChanged: onChanged,
      hint: const Text('Seleccionar…', style: TextStyle(fontSize: 13)),
    );
  }

  Widget _specialButton({
    required String label,
    required Color color,
    required IconData icon,
    required bool enabled,
    required VoidCallback onTap,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: enabled ? onTap : null,
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
          decoration: BoxDecoration(
            color: enabled ? color.withValues(alpha: 0.06) : AppTheme.divider,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: enabled ? color.withValues(alpha: 0.3) : AppTheme.border,
            ),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 16, color: enabled ? color : AppTheme.textMuted),
              const SizedBox(width: 4),
              Flexible(
                child: Text(
                  label,
                  textAlign: TextAlign.center,
                  maxLines: 2,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: enabled ? color : AppTheme.textMuted,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
