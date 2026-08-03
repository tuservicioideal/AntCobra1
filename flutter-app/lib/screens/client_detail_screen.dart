import 'package:flutter/material.dart';
import '../config/theme.dart';
import '../models/client_model.dart';
import 'consulta_telegram_screen.dart';
import '../services/alert_service.dart';
import '../services/firestore_service.dart';
import '../services/document_download_service.dart';
import '../services/letter_jpg_publish_service.dart';
import '../services/letter_jpg_templates.dart';
import '../services/letter_word_service.dart';
import '../services/share_print_service.dart';
import '../utils/local_file_payload.dart';
import '../utils/open_local_file.dart';
import '../services/location_service.dart';
import '../services/campaign_service.dart';
import '../services/auth_service.dart';
import '../services/nivel_catalog_service.dart';
import '../services/etiqueta_catalog_service.dart';
import '../models/visita_historial.dart';
import '../utils/client_status_ui.dart';
import '../utils/direcciones_conocidas.dart';
import '../utils/section_utils.dart';
import '../widgets/destination_gestor_picker.dart';
import '../widgets/client_detail/client_detail_gestion_card.dart';
import '../widgets/client_detail/client_detail_gps_strip.dart';
import '../widgets/client_detail/client_detail_hero.dart';
import '../widgets/client_detail/client_detail_call_contact.dart';
import '../widgets/client_detail/client_detail_letters_section.dart';
import '../widgets/client_detail/client_detail_word_section.dart';
import '../widgets/client_detail/client_detail_location_section.dart';
import '../widgets/client_detail/client_detail_notes_section.dart';
import '../widgets/client_detail/client_detail_contact_agenda_section.dart';
import '../widgets/client_detail/client_detail_debts_section.dart';
import '../widgets/client_detail/client_detail_doxeo_section.dart';
import '../widgets/client_detail/client_detail_history_section.dart';
import '../widgets/client_detail/client_detail_tags_section.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

/// Full-screen client detail with GPS capture, status buttons, notes, and alerts.
class ClientDetailScreen extends StatefulWidget {
  final ClientModel client;
  final String campaignId;
  final String section;
  final bool embedded;
  final VoidCallback? onUpdated;

  const ClientDetailScreen({
    super.key,
    required this.client,
    required this.campaignId,
    required this.section,
    this.embedded = false,
    this.onUpdated,
  });

  @override
  State<ClientDetailScreen> createState() => _ClientDetailScreenState();
}

class _ClientDetailScreenState extends State<ClientDetailScreen> {
  final _firestoreService = FirestoreService();
  final _alertService = AlertService();
  final _locationService = LocationService();
  final _notesController = TextEditingController();
  final _contactPhoneController = TextEditingController();
  final _contactAddressController = TextEditingController();
  final _contactNoteController = TextEditingController();
  String _contactNivelConfianza = nivelConfiable;
  final _nivelCatalog = NivelCatalogService();
  final _etiquetaCatalog = EtiquetaCatalogService();
  final _downloadService = DocumentDownloadService();
  final _sharePrintService = SharePrintService();
  final _letterJpgPublishService = LetterJpgPublishService();
  final _letterWordService = LetterWordService();
  final _campaignService = CampaignService();

  bool _gpsLoading = true;
  bool _saving = false;
  bool _updated = false;
  bool _lettersLoading = false;
  bool _generatingLetter = false;
  bool _generatingWord = false;
  int _selectedWordTemplate = 1;
  LocalFilePayload? _lastWordPayload;
  bool _savingContact = false;
  bool _savingVerifiedLocation = false;
  List<CartaGenerada> _letters = [];
  late ClientModel _client;
  List<DireccionConocida> _direccionesConocidas = [];
  bool _loadingDirecciones = false;
  List<ClientModel> _relatedAccounts = [];
  bool _loadingRelated = false;
  List<VisitaHistorial> _visitHistory = [];
  bool _loadingVisitHistory = false;
  bool _savingTags = false;

  // Nivel selection state
  bool _catalogLoading = true;
  bool _catalogLoaded = false;
  String _canal = 'CAM';
  String _nivel1 = '';
  String _nivel2 = '';
  String _nivel3 = '';
  String _nivel4 = '';
  String _fechaPromesa = '';
  double _montoPromesa = 0;
  final _montoController = TextEditingController();
  bool _callModeInit = false;

  bool _isCallGestor(BuildContext context) =>
      context.read<AuthService>().profile?.isCallGestor ?? false;

  @override
  void initState() {
    super.initState();
    _client = widget.client;
    _notesController.text = _client.notaGestor;
    if (_client.montoPromesaPago > 0) {
      _montoPromesa = _client.montoPromesaPago;
      _montoController.text = _montoPromesa.toStringAsFixed(2);
    }
    if (_client.fechaPromesaPago.trim().isNotEmpty) {
      _fechaPromesa = _client.fechaPromesaPago.trim();
    }
    _contactPhoneController.text = '';
    _contactAddressController.text = '';
    _loadCatalog();
    _loadEtiquetaCatalog();
    _loadLetters();
    _loadDireccionesConocidas();
    _loadRelatedAccounts();
    _loadVisitHistory();
    _selectedWordTemplate = resolveTemplateId(_client);
  }

  Future<void> _loadEtiquetaCatalog() async {
    await _etiquetaCatalog.loadCatalogo();
    if (mounted) setState(() {});
  }

  Future<void> _loadRelatedAccounts() async {
    if (_client.numeroDocumento.trim().isEmpty) return;
    setState(() => _loadingRelated = true);
    try {
      final accounts =
          await _firestoreService.getAccountsByDocumento(_client.numeroDocumento);
      if (mounted) setState(() => _relatedAccounts = accounts);
    } catch (e) {
      debugPrint('Error cargando cuentas relacionadas: $e');
      if (mounted) {
        setState(() => _relatedAccounts = [_client]);
        _showSnackbar(
          'No se pudieron cargar otras cuentas del mismo DNI',
          isError: true,
        );
      }
    } finally {
      if (mounted) setState(() => _loadingRelated = false);
    }
  }

  Future<void> _loadVisitHistory() async {
    setState(() => _loadingVisitHistory = true);
    try {
      List<VisitaHistorial> hist;
      if (_client.numeroDocumento.trim().isNotEmpty) {
        try {
          hist = await _firestoreService.getVisitHistoryByDocumento(
            numeroDocumento: _client.numeroDocumento,
          );
        } catch (e) {
          debugPrint('Historial por DNI falló, usando cuenta actual: $e');
          hist = await _firestoreService.getVisitHistory(
            campaignId: widget.campaignId,
            section: widget.section,
            clientId: _client.id,
          );
        }
      } else {
        hist = await _firestoreService.getVisitHistory(
          campaignId: widget.campaignId,
          section: widget.section,
          clientId: _client.id,
        );
      }
      if (mounted) setState(() => _visitHistory = hist);
    } finally {
      if (mounted) setState(() => _loadingVisitHistory = false);
    }
  }

  Future<void> _saveClientTags(List<String> tags) async {
    setState(() => _savingTags = true);
    try {
      await _firestoreService.updateClientTags(
        campaignId: widget.campaignId,
        section: widget.section,
        clientId: _client.id,
        etiquetas: tags,
      );
      if (mounted) {
        setState(() => _client = _client.copyWith(etiquetas: tags));
        _markUpdated(navigateBack: false);
        _showSnackbar('Etiquetas actualizadas', isSuccess: true);
      }
    } catch (e) {
      if (mounted) _showSnackbar('Error al guardar etiquetas: $e', isError: true);
    } finally {
      if (mounted) setState(() => _savingTags = false);
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_callModeInit) return;
    _callModeInit = true;
    if (_isCallGestor(context)) {
      _canal = 'TEL';
      _gpsLoading = false;
    } else {
      _captureGps();
    }
  }

  @override
  void dispose() {
    _notesController.dispose();
    _contactPhoneController.dispose();
    _contactAddressController.dispose();
    _contactNoteController.dispose();
    _montoController.dispose();
    super.dispose();
  }

  void _markUpdated({bool navigateBack = false}) {
    _updated = true;
    widget.onUpdated?.call();
    if (!widget.embedded && navigateBack && mounted) {
      Future.delayed(const Duration(milliseconds: 800), () {
        if (mounted) Navigator.pop(context, true);
      });
    }
  }

  Future<void> _loadCatalog() async {
    final cat = await _nivelCatalog.getCatalogo();
    if (mounted) {
      setState(() {
        _catalogLoaded = cat != null;
        _catalogLoading = false;
      });
    }
  }

  Future<void> _captureGps() async {
    setState(() => _gpsLoading = true);
    await _locationService.getCurrentPosition();
    if (mounted) setState(() => _gpsLoading = false);
  }

  Future<void> _loadLetters() async {
    setState(() => _lettersLoading = true);
    final letters = await _firestoreService.getClientLetters(
      campaignId: widget.campaignId,
      clientId: _client.codigoCliente.isNotEmpty ? _client.codigoCliente : _client.id,
      section: widget.section,
    );
    if (mounted) {
      setState(() {
        _letters = letters;
        _lettersLoading = false;
      });
    }
  }

  bool _gpsReadyFor(BuildContext context) =>
      _isCallGestor(context) || _locationService.hasPosition;

  Future<void> _updateStatus(String estado, {bool isSpecialState = false}) => _doUpdateStatus(estado, isSpecialState: isSpecialState);

  Future<void> _doUpdateStatus(String estado, {bool isSpecialState = false}) async {
    final isCall = _isCallGestor(context);
    if (!isCall && !_gpsReadyFor(context)) {
      _showSnackbar('Esperando ubicación GPS...', isError: true);
      return;
    }

    setState(() => _saving = true);

    try {
      final auth = context.read<AuthService>();

      // Update Firestore with nivel fields
      await _firestoreService.updateClientStatus(
        campaignId: widget.campaignId,
        section: widget.section,
        clientId: _client.id,
        estado: estado,
        nota: _notesController.text.trim(),
        lat: isCall ? null : _locationService.latitude,
        lng: isCall ? null : _locationService.longitude,
        nivel1: isSpecialState ? null : (_nivel1.isNotEmpty ? _nivel1 : null),
        nivel2: isSpecialState ? null : (_nivel2.isNotEmpty ? _nivel2 : null),
        nivel3: isSpecialState ? null : (_nivel3.isNotEmpty ? _nivel3 : null),
        nivel4: isSpecialState ? null : (_nivel4.isNotEmpty ? _nivel4 : null),
        canalGestion: isSpecialState
            ? null
            : ((isCall ? 'TEL' : _canal).isNotEmpty ? (isCall ? 'TEL' : _canal) : null),
        fechaPromesaPago: _fechaPromesa.isNotEmpty ? _fechaPromesa : null,
        montoPromesaPago: _montoPromesa > 0 ? _montoPromesa : null,
        gestorUid: auth.firebaseUser?.uid ?? auth.profile?.uid ?? '',
        gestorNombre: auth.profile?.nombre ?? '',
      );

      if (!isCall) {
        // Record GPS tracking point for location history (Auth UID = doc tracking)
        await _firestoreService.recordTrackingPoint(
          gestorUid: auth.firebaseUser?.uid ?? auth.profile?.uid ?? '',
          lat: _locationService.latitude!,
          lng: _locationService.longitude!,
          accuracy: _locationService.lastPosition?.accuracy,
          clientId: _client.id,
          clientName: _client.displayName,
          estado: estado,
          section: widget.section,
          gestorNombre: auth.profile?.nombre ?? '',
        );

        // Save GPS as client's verified location (for future gestors)
        await _firestoreService.saveVerifiedLocation(
          campaignId: widget.campaignId,
          section: widget.section,
          clientId: _client.id,
          lat: _locationService.latitude!,
          lng: _locationService.longitude!,
          accuracy: _locationService.lastPosition?.accuracy,
          gestorUid: auth.profile?.uid ?? '',
          gestorNombre: auth.profile?.nombre ?? '',
        );
      }

      // Create alert for special states
      if (estado == 'suplantacion' || estado == 'pago_no_registrado') {
        await _alertService.createAlert(
          tipo: estado,
          campaignId: widget.campaignId,
          section: widget.section,
          clientId: _client.id,
          clientName: _client.displayName,
          clientDni: _client.numeroDocumento,
          nota: _notesController.text.trim(),
          lat: isCall ? null : _locationService.latitude,
          lng: isCall ? null : _locationService.longitude,
          gestorEmail: auth.profile?.email ?? '',
          gestorName: auth.profile?.nombre ?? '',
        );
      }

      await _loadVisitHistory();
      _markUpdated(navigateBack: true);
      if (mounted) {
        _showSnackbar(clientStatusLabel(estado), isSuccess: true);
      }
    } catch (e) {
      _showSnackbar('Error al guardar: $e', isError: true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _loadDireccionesConocidas() async {
    setState(() => _loadingDirecciones = true);
    try {
      final hist = await _firestoreService.getContactHistory(
        campaignId: widget.campaignId,
        section: widget.section,
        clientId: _client.id,
      );
      if (mounted) {
        setState(() {
          _direccionesConocidas = collectDireccionesConocidas(_client, hist);
          _loadingDirecciones = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loadingDirecciones = false);
    }
  }

  Future<void> _confirmAndSaveVerifiedLocation() async {
    if (!_locationService.hasPosition) {
      _showSnackbar('Esperando ubicación GPS...', isError: true);
      return;
    }

    final lat = _locationService.latitude!;
    final lng = _locationService.longitude!;
    final coordText = '${lat.toStringAsFixed(5)}, ${lng.toStringAsFixed(5)}';

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Guardar ubicación actual'),
        content: Text(
          'Se anotará esta coordenada GPS como posible domicilio del cliente '
          'para mapas y próximas visitas:\n\n$coordText\n\n'
          'No cambia la dirección del banco; queda en direcciones conocidas '
          'para central y otros gestores.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Guardar'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;
    await _saveVerifiedLocation();
  }

  Future<void> _saveVerifiedLocation() async {
    if (!_locationService.hasPosition) {
      _showSnackbar('Esperando ubicación GPS...', isError: true);
      return;
    }

    setState(() => _savingVerifiedLocation = true);
    try {
      final auth = context.read<AuthService>();
      await _firestoreService.saveVerifiedLocation(
        campaignId: widget.campaignId,
        section: widget.section,
        clientId: _client.id,
        lat: _locationService.latitude!,
        lng: _locationService.longitude!,
        accuracy: _locationService.lastPosition?.accuracy,
        gestorUid: auth.profile?.uid ?? '',
        gestorNombre: auth.profile?.nombre ?? '',
        recordHistorial: true,
      );
      _markUpdated();
      await _reloadClient();
      if (mounted) {
        _showSnackbar(
          'Posible domicilio guardado. Visible en mapas y direcciones conocidas.',
          isSuccess: true,
        );
      }
    } catch (e) {
      _showSnackbar('Error al guardar ubicación: $e', isError: true);
    } finally {
      if (mounted) setState(() => _savingVerifiedLocation = false);
    }
  }

  Future<void> _openVerifiedInMaps() async {
    if (!_client.hasVerifiedLocation) return;
    final uri = Uri.parse(
      'https://www.google.com/maps?q=${_client.ubicacionVerificadaLat},${_client.ubicacionVerificadaLng}',
    );
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  String _formatVerifiedDate(String iso) {
    if (iso.isEmpty) return '';
    if (iso.length >= 16) {
      return iso.substring(0, 16).replaceFirst('T', ' ');
    }
    return iso;
  }

  Future<void> _reloadClient() async {
    final fresh = await _firestoreService.getClient(
      campaignId: widget.campaignId,
      section: widget.section,
      clientId: _client.id,
    );
    if (fresh != null && mounted) {
      setState(() {
        _client = fresh;
        _notesController.text = fresh.notaGestor;
      });
      await _loadDireccionesConocidas();
    }
  }

  void _fillAddressWithGps() {
    if (!_locationService.hasPosition) {
      _showSnackbar('Esperando ubicación GPS...', isError: true);
      return;
    }
    final lat = _locationService.latitude!;
    final lng = _locationService.longitude!;
    _contactAddressController.text =
        'GPS: ${lat.toStringAsFixed(5)}, ${lng.toStringAsFixed(5)}';
  }

  Future<void> _updateContactEntry(
    DireccionConocida entry, {
    String? nivelConfianza,
    int? orden,
    bool? oculto,
    bool? esPrincipal,
  }) async {
    if (!entry.isEditable) return;
    try {
      if (esPrincipal == true) {
        for (final other in _direccionesConocidas.where((d) => d.isEditable)) {
          if (other.eventId != entry.eventId && other.esPrincipal) {
            await _firestoreService.updateContactEntry(
              campaignId: widget.campaignId,
              section: widget.section,
              clientId: _client.id,
              eventId: other.eventId,
              esPrincipal: false,
            );
          }
        }
      }
      await _firestoreService.updateContactEntry(
        campaignId: widget.campaignId,
        section: widget.section,
        clientId: _client.id,
        eventId: entry.eventId,
        nivelConfianza: nivelConfianza,
        orden: orden,
        oculto: oculto,
        esPrincipal: esPrincipal,
      );
      _markUpdated();
      await _loadDireccionesConocidas();
    } catch (e) {
      _showSnackbar('Error al actualizar contacto: $e', isError: true);
    }
  }

  Future<void> _reorderContactEntry(DireccionConocida entry, int delta) async {
    if (!entry.isEditable) return;
    final activas = _direccionesConocidas
        .where((d) => d.isEditable && !d.oculto)
        .toList();
    final idx = activas.indexWhere((d) => d.eventId == entry.eventId);
    if (idx < 0) return;
    final newIdx = idx + delta;
    if (newIdx < 0 || newIdx >= activas.length) return;
    final other = activas[newIdx];
    try {
      await _firestoreService.updateContactEntry(
        campaignId: widget.campaignId,
        section: widget.section,
        clientId: _client.id,
        eventId: entry.eventId,
        orden: other.orden,
      );
      await _firestoreService.updateContactEntry(
        campaignId: widget.campaignId,
        section: widget.section,
        clientId: _client.id,
        eventId: other.eventId,
        orden: entry.orden,
      );
      _markUpdated();
      await _loadDireccionesConocidas();
    } catch (e) {
      _showSnackbar('Error al reordenar: $e', isError: true);
    }
  }

  Future<bool> _saveContactUpdate() async {
    final newPhone = _contactPhoneController.text.trim();
    final newAddress = _contactAddressController.text.trim();
    final note = _contactNoteController.text.trim();
    if (note.isEmpty) {
      _showSnackbar('Debe ingresar una nota.', isError: true);
      return false;
    }
    if (newPhone.isEmpty && newAddress.isEmpty) {
      _showSnackbar('Indique al menos un teléfono o una dirección observada.', isError: true);
      return false;
    }
    setState(() => _savingContact = true);
    try {
      final auth = context.read<AuthService>();
      await _firestoreService.updateClientContactData(
        campaignId: widget.campaignId,
        section: widget.section,
        clientId: _client.id,
        direccionNueva: newAddress,
        telefonoNuevo: newPhone,
        direccionAnterior: _client.direccion,
        telefonoAnterior: _client.telefonoMovil,
        notaCambio: note,
        editorUid: auth.profile?.uid ?? '',
        editorNombre: auth.profile?.nombre ?? '',
        editorEmail: auth.profile?.email ?? '',
        editorRol: auth.profile?.rol ?? '',
        lat: _locationService.latitude,
        lng: _locationService.longitude,
        nivelConfianza: _contactNivelConfianza,
        orden: _direccionesConocidas.where((d) => d.isEditable).length,
      );
      _markUpdated();
      _contactNoteController.clear();
      _contactAddressController.clear();
      _contactPhoneController.clear();
      await _reloadClient();
      _showSnackbar(
        'Contacto registrado. Se guarda para futuras campañas.',
        isSuccess: true,
      );
      return true;
    } catch (e) {
      _showSnackbar('Error al registrar nota: $e', isError: true);
      return false;
    } finally {
      if (mounted) setState(() => _savingContact = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final client = _client;
    final isCall = _isCallGestor(context);
    final isGestor = context.read<AuthService>().profile?.isGestor ?? false;
    final gpsReady = _gpsReadyFor(context);

    final body = _saving
        ? const Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                CircularProgressIndicator(color: AppTheme.primaryColor),
                SizedBox(height: 16),
                Text('Guardando...'),
              ],
            ),
          )
        : SingleChildScrollView(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ClientDetailHero(client: client),
                ClientDetailDebtsSection(
                  currentClient: client,
                  relatedAccounts: _relatedAccounts.isNotEmpty
                      ? _relatedAccounts
                      : [client],
                  loading: _loadingRelated,
                ),
                ClientDetailTagsSection(
                  client: client,
                  catalogService: _etiquetaCatalog,
                  saving: _savingTags,
                  onSave: _saveClientTags,
                ),
                ClientDetailDoxeoSection(client: client),
                ClientDetailHistorySection(
                  visitas: _visitHistory,
                  loading: _loadingVisitHistory,
                  showCombinedLabel: client.numeroDocumento.isNotEmpty,
                ),
                if (isCall) ClientDetailCallContact(client: client),
                if (isCall)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: ClientDetailContactAgendaSection(
                      direcciones: _direccionesConocidas,
                      loading: _loadingDirecciones,
                      onUpdateEntry: _updateContactEntry,
                      onReorderEntry: _reorderContactEntry,
                    ),
                  ),
                if (!isCall)
                  ClientDetailGpsStrip(
                    gpsLoading: _gpsLoading,
                    gpsReady: gpsReady,
                    gpsError: _locationService.error,
                    client: client,
                    verifiedDateFormatted:
                        _formatVerifiedDate(client.ubicacionVerificadaFecha),
                    savingVerifiedLocation: _savingVerifiedLocation,
                    saving: _saving,
                    onRetry: _captureGps,
                    onOpenSettings:
                        _locationService.error?.contains('Configuración') ==
                                    true ||
                                _locationService.error?.contains('bloqueado') ==
                                    true
                            ? () => _locationService.openAppSettings()
                            : null,
                    onSaveVerified: _confirmAndSaveVerifiedLocation,
                    onOpenVerifiedMaps: _openVerifiedInMaps,
                  ),
                if (isGestor)
                  ClientDetailGestionCard(
                    catalogLoading: _catalogLoading,
                    catalogLoaded: _catalogLoaded,
                    nivelCatalog: _nivelCatalog,
                    canal: _canal,
                    nivel1: _nivel1,
                    nivel2: _nivel2,
                    nivel3: _nivel3,
                    nivel4: _nivel4,
                    fechaPromesa: _fechaPromesa,
                    montoController: _montoController,
                    deudaPendiente: client.importeDeudaPendiente,
                    gpsReady: gpsReady,
                    saving: _saving,
                    lockCanalToTel: isCall,
                    requireGps: !isCall,
                    onCanalChanged: (c) => setState(() {
                      _canal = c;
                      _nivel1 = '';
                      _nivel2 = '';
                      _nivel3 = '';
                      _nivel4 = '';
                    }),
                    onNivel1Changed: (v) => setState(() {
                      _nivel1 = v;
                      _nivel2 = '';
                      _nivel3 = '';
                      _nivel4 = '';
                    }),
                    onNivel2Changed: (v) => setState(() {
                      _nivel2 = v;
                      _nivel3 = '';
                      _nivel4 = '';
                    }),
                    onNivel3Changed: (v) => setState(() {
                      _nivel3 = v;
                      _nivel4 = '';
                    }),
                    onNivel4Changed: (v) => setState(() => _nivel4 = v),
                    onPickFechaPromesa: _pickFechaPromesa,
                    onMontoChanged: (v) => _montoPromesa = v,
                    onRegister: _onRegisterGestion,
                    onSpecialStatus: isCall ? (_, __) {} : _confirmSpecialStatus,
                    canRequestReturn: !isCall && _client.isPendiente,
                    onRequestReturn:
                        !isCall && _client.isPendiente ? _confirmReturnRequest : null,
                  ),
                if (!isCall)
                  ClientDetailLocationSection(
                    client: client,
                    direcciones: _direccionesConocidas,
                    loadingDirecciones: _loadingDirecciones,
                    gpsLoading: _gpsLoading,
                    gpsReady: gpsReady,
                    gpsError: _locationService.error,
                    currentLat: _locationService.latitude,
                    currentLng: _locationService.longitude,
                    savingGpsAnnotation: _savingVerifiedLocation,
                    saving: _saving,
                    onOpenClientMaps: client.hasCoordinates
                        ? () => _openClientInMaps(client)
                        : null,
                    onOpenVerifiedMaps: client.hasVerifiedLocation
                        ? _openVerifiedInMaps
                        : null,
                    onSaveGpsAnnotation: _confirmAndSaveVerifiedLocation,
                    onRetryGps: _captureGps,
                    onUpdateContactEntry: _updateContactEntry,
                    onReorderContactEntry: _reorderContactEntry,
                  ),
                if (!isCall)
                  ClientDetailWordSection(
                    generating: _generatingWord,
                    selectedTemplate: _selectedWordTemplate,
                    onTemplateChanged: (v) =>
                        setState(() => _selectedWordTemplate = v),
                    onGenerate: _generateLetterWord,
                    lastGeneratedPath: _lastWordPayload?.name,
                    onWordAction: _lastWordPayload == null
                        ? null
                        : _onWordFileAction,
                  ),
                ClientDetailNotesSection(
                  notesController: _notesController,
                  contactPhoneController: _contactPhoneController,
                  contactAddressController: _contactAddressController,
                  contactNoteController: _contactNoteController,
                  savingContact: _savingContact,
                  gpsReady: gpsReady,
                  nivelConfianza: _contactNivelConfianza,
                  onNivelConfianzaChanged: (v) =>
                      setState(() => _contactNivelConfianza = v),
                  onFillAddressWithGps: isCall ? null : _fillAddressWithGps,
                  onSaveContact: _saveContactUpdate,
                ),
                if (!isCall) _buildZoneEditButton(client),
                const SizedBox(height: 16),
              ],
            ),
          );

    if (widget.embedded) {
      return body;
    }

    return PopScope(
      canPop: true,
      onPopInvokedWithResult: (didPop, _) {
        if (didPop && _updated) {
          // Will pass true via Navigator.pop
        }
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(heroAppBarTitle(client)),
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
            onPressed: () => Navigator.pop(context, _updated),
          ),
          actions: [
            IconButton(
              icon: const Icon(Icons.travel_explore, color: Colors.white),
              tooltip: 'Consultar por Telegram',
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => ConsultaTelegramScreen(
                      initialClient: _client,
                      campaignId: widget.campaignId,
                    ),
                  ),
                );
              },
            ),
          ],
        ),
        body: body,
      ),
    );
  }

  Future<void> _pickFechaPromesa() async {
    final date = await showDatePicker(
      context: context,
      initialDate: DateTime.now().add(const Duration(days: 3)),
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 90)),
    );
    if (date != null && mounted) {
      setState(() => _fechaPromesa = date.toIso8601String().split('T')[0]);
    }
  }

  void _onRegisterGestion() {
    _confirmStatus(
      _mapNivelToEstado(_nivel1),
      'Nivel: $_nivel1 > $_nivel2 > $_nivel3 > $_nivel4',
    );
  }

  Future<void> _generateLetterWord() async {
    setState(() => _generatingWord = true);
    try {
      final auth = context.read<AuthService>();
      final campaignData =
          await _campaignService.getCampaignData(widget.campaignId);
      final campaignName = campaignData?['nombre']?.toString() ?? '';
      final payload = await _letterWordService.generateWordForClient(
        client: _client,
        templateId: _selectedWordTemplate,
        gestorName: auth.profile?.nombre ?? '',
        gestorPhone: auth.profile?.telefono ?? '',
        campaignName: campaignName,
      );
      if (mounted) {
        setState(() => _lastWordPayload = payload);
        _showSnackbar('Carta Word generada localmente.');
      }
    } catch (e) {
      if (mounted) {
        _showSnackbar('Error generando Word: $e', isError: true);
      }
    } finally {
      if (mounted) setState(() => _generatingWord = false);
    }
  }

  Future<void> _onWordFileAction(String action) async {
    final payload = _lastWordPayload;
    if (payload == null) return;
    try {
      if (action == 'abrir') {
        await openLocalFile(payload);
      } else if (action == 'compartir') {
        await _sharePrintService.sharePayload(payload);
      }
    } catch (e) {
      _showSnackbar('Error con carta Word: $e', isError: true);
    }
  }

  Future<void> _generateLetterJpg() async {
    setState(() => _generatingLetter = true);
    try {
      final auth = context.read<AuthService>();
      await _letterJpgPublishService.ensureLetterJpg(
        context: context,
        client: _client,
        campaignId: widget.campaignId,
        section: widget.section,
        gestorName: auth.profile?.nombre ?? '',
        gestorPhone: auth.profile?.telefono ?? '',
      );
      await _loadLetters();
      if (mounted) {
        _showSnackbar('Carta JPG generada y publicada.');
      }
    } catch (e) {
      if (mounted) {
        _showSnackbar('Error generando carta: $e', isError: true);
      }
    } finally {
      if (mounted) setState(() => _generatingLetter = false);
    }
  }

  Future<void> _onLetterMenuAction(CartaGenerada letter, String value) async {
    try {
      final payload = await _downloadService.downloadLetter(letter);
      if (value == 'abrir') {
        await _downloadService.openLetter(letter);
      } else if (value == 'compartir') {
        await _sharePrintService.sharePayload(payload);
      } else if (value == 'imprimir') {
        await _sharePrintService.printImagePayload(payload);
      }
    } catch (e) {
      _showSnackbar('Error con carta: $e', isError: true);
    }
  }

  Future<void> _openClientInMaps(ClientModel client) async {
    if (!client.hasCoordinates) return;
    final uri = Uri.parse(
      'https://www.google.com/maps?q=${client.latitude},${client.longitude}',
    );
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  Widget _buildZoneEditButton(ClientModel client) {
    final auth = context.read<AuthService>();
    if (!auth.isAdmin && !auth.isSupervisor) {
      return const SizedBox.shrink();
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: OutlinedButton.icon(
        onPressed: () => _showZoneEditDialog(client),
        icon: const Icon(Icons.edit_location_alt_outlined, size: 18),
        label: Text(
          'Cambiar Zona (${widget.section})',
          style: const TextStyle(fontSize: 13),
        ),
        style: OutlinedButton.styleFrom(
          foregroundColor: AppTheme.primaryColor,
          side: BorderSide(color: AppTheme.primaryColor.withValues(alpha: 0.3)),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
        ),
      ),
    );
  }

  Future<void> _showZoneEditDialog(ClientModel client) async {
    final gestores = await _firestoreService.getGestoresActivos();
    final sections =
        await _firestoreService.resolveDestinationSections(widget.campaignId);
    final options = buildDestinationOptions(
      gestores: gestores,
      destinationSections: sections,
    );
    final filtered = options
        .where((o) => o.sectionKey != widget.section)
        .toList();

    if (filtered.isEmpty) {
      _showSnackbar('No hay secciones destino disponibles', isError: true);
      return;
    }

    if (!mounted) return;

    final selected = await showDestinationPickerDialog(
      context: context,
      options: filtered,
      initialSectionKey: filtered.first.sectionKey,
      title: 'Cambiar Zona / Sección',
    );

    if (selected == null || !mounted) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Confirmar cambio de zona'),
        content: Text(
          '¿Mover a "${client.displayName}" de\n'
          '${sectionDisplayLabel(widget.section)} → ${sectionDisplayLabel(selected)}?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Confirmar'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    final auth = context.read<AuthService>();
    final result = await _firestoreService.updateClientZone(
      campaignId: widget.campaignId,
      currentSectionKey: widget.section,
      clientId: _client.id,
      newSectionKey: selected,
      adminEmail: auth.profile?.email ?? '',
      adminName: auth.profile?.nombre ?? '',
      motivo: 'edicion_manual',
    );

    if (result['success'] == true) {
      _showSnackbar(
        'Zona actualizada a ${sectionDisplayLabel(selected)}',
        isSuccess: true,
      );
      _markUpdated(navigateBack: true);
    } else {
      _showSnackbar('Error: ${result['error']}', isError: true);
    }
  }

  String _mapNivelToEstado(String nivel1) {
    switch (nivel1) {
      case 'Contacto efectivo':
        return 'visitado_habido';
      case 'Contacto no efectivo':
      case 'No contacto':
        return 'visitado_no_habido';
      default:
        return 'visitado_habido';
    }
  }

  void _confirmSpecialStatus(String estado, String label) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Confirmar Estado Especial'),
        content: Text('¿Marcar como "$label"?\n\n'
            'Esto generará una alerta a central y registrará la ubicación GPS.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () {
              Navigator.pop(ctx);
              _updateStatus(estado, isSpecialState: true);
            },
            child: const Text('Confirmar',
                style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  static const _returnMotivos = [
    ('zona_inaccesible', 'Zona inaccesible'),
    ('ruta_bloqueada', 'Ruta bloqueada'),
    ('riesgo_seguridad', 'Riesgo de seguridad'),
    ('otro', 'Otro'),
  ];

  Future<void> _confirmReturnRequest() async {
    if (!_locationService.hasPosition) {
      _showSnackbar('Esperando ubicación GPS...', isError: true);
      return;
    }
    if (!_client.isPendiente) {
      _showSnackbar('Solo clientes pendientes pueden devolverse.', isError: true);
      return;
    }

    var motivo = _returnMotivos.first.$1;
    final notaController = TextEditingController(text: _notesController.text.trim());

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text('Devolver cliente'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Indique por qué no puede visitar a este cliente. '
                  'Central revisará y reasignará a otro gestor.',
                  style: TextStyle(fontSize: 13),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: motivo,
                  decoration: const InputDecoration(
                    labelText: 'Motivo',
                    border: OutlineInputBorder(),
                  ),
                  items: _returnMotivos
                      .map((e) => DropdownMenuItem(value: e.$1, child: Text(e.$2)))
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setDialogState(() => motivo = v);
                  },
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: notaController,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: 'Detalle (obligatorio)',
                    hintText: 'Describa el impedimento de acceso…',
                    border: OutlineInputBorder(),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF7C3AED)),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Devolver', style: TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );

    final nota = notaController.text.trim();
    notaController.dispose();
    if (confirmed != true || !mounted) return;
    if (nota.length < 10) {
      _showSnackbar('La nota debe tener al menos 10 caracteres.', isError: true);
      return;
    }

    setState(() => _saving = true);
    try {
      final auth = context.read<AuthService>();
      await _firestoreService.requestClientReturn(
        campaignId: widget.campaignId,
        section: widget.section,
        clientId: _client.id,
        motivo: motivo,
        nota: nota,
        lat: _locationService.latitude!,
        lng: _locationService.longitude!,
        gestorUid: auth.firebaseUser?.uid ?? auth.profile?.uid ?? '',
        gestorNombre: auth.profile?.nombre ?? '',
        gestorEmail: auth.profile?.email ?? '',
      );

      await _alertService.createAlert(
        tipo: 'zona_inaccesible_devolucion',
        campaignId: widget.campaignId,
        section: widget.section,
        clientId: _client.id,
        clientName: _client.displayName,
        clientDni: _client.numeroDocumento,
        nota: nota,
        lat: _locationService.latitude,
        lng: _locationService.longitude,
        gestorEmail: auth.profile?.email ?? '',
        gestorName: auth.profile?.nombre ?? '',
      );

      _markUpdated(navigateBack: true);
      if (mounted) {
        _showSnackbar('Devolución solicitada a central', isSuccess: true);
      }
    } catch (e) {
      _showSnackbar('Error al devolver: $e', isError: true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _confirmStatus(String estado, String label) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Confirmar Gestión'),
        content: Text('$label\n\n'
            'Esta acción registrará la ubicación GPS actual.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              _updateStatus(estado);
            },
            child: const Text('Confirmar'),
          ),
        ],
      ),
    );
  }

  void _showSnackbar(String message, {bool isError = false, bool isSuccess = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError
            ? Colors.red.shade600
            : isSuccess
                ? Colors.green.shade600
                : null,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        margin: const EdgeInsets.all(12),
      ),
    );
  }
}
