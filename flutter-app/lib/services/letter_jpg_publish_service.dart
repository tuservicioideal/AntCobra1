import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/material.dart';

import '../models/client_model.dart';
import 'firestore_service.dart';
import 'letter_jpg_generator_service.dart';
import 'letter_jpg_templates.dart';

class LetterJpgPublishService {
  LetterJpgPublishService({
    FirestoreService? firestoreService,
    LetterJpgGeneratorService? generatorService,
    FirebaseFirestore? firestore,
    FirebaseStorage? storage,
    FirebaseAuth? auth,
  })  : _firestoreService = firestoreService ?? FirestoreService(),
        _generator = generatorService ?? LetterJpgGeneratorService(),
        _db = firestore ?? FirebaseFirestore.instance,
        _storage = storage ?? FirebaseStorage.instance,
        _auth = auth ?? FirebaseAuth.instance;

  final FirestoreService _firestoreService;
  final LetterJpgGeneratorService _generator;
  final FirebaseFirestore _db;
  final FirebaseStorage _storage;
  final FirebaseAuth _auth;

  Future<List<CartaGenerada>> ensureLetterJpg({
    required BuildContext context,
    required ClientModel client,
    required String campaignId,
    required String section,
    String gestorName = '',
    String gestorPhone = '',
    String campaignName = '',
    int? templateId,
  }) async {
    final clientId = client.codigoCliente.isNotEmpty ? client.codigoCliente : client.id;
    var letters = await _firestoreService.getClientLetters(
      campaignId: campaignId,
      clientId: clientId,
      section: section.isNotEmpty ? section : client.seccionKey,
    );
    if (letters.isNotEmpty) return letters;

    final uid = _auth.currentUser?.uid ?? '';
    if (uid.isEmpty) {
      throw StateError('No hay sesión activa para generar la carta.');
    }

    final cartaId = resolveTemplateId(client, numeroCarta: templateId);
    final placeholders = mapClientToPlaceholders(
      client: client,
      gestorName: gestorName,
      gestorPhone: gestorPhone,
      campaignName: campaignName,
    );
    final missing = validatePlaceholders(placeholders);
    if (missing.isNotEmpty) {
      throw StateError('Faltan datos del cliente: ${missing.join(', ')}');
    }

    final jpegBytes = await _generator.generateJpegBytes(
      context: context,
      templateId: cartaId,
      placeholders: placeholders,
    );

    final seccionKey = section.isNotEmpty ? section : client.seccionKey;
    final safeClient = sanitizeName(placeholders.nombre.isNotEmpty ? placeholders.nombre : clientId);
    final filename = 'Carta_${cartaId}_Cli${sanitizeName(clientId)}_$safeClient.jpg';
    final storagePath = 'cartas_generadas/$campaignId/$seccionKey/$uid/$filename';

    final ref = _storage.ref(storagePath);
    await ref.putData(
      jpegBytes,
      SettableMetadata(contentType: 'image/jpeg'),
    );
    final downloadUrl = await ref.getDownloadURL();

    final docId = '${campaignId}_${cartaId}_${seccionKey}_${uid}_${sanitizeName(clientId)}_jpg';
    final payload = {
      'campaign_id': campaignId,
      'numero_carta': cartaId,
      'cliente_id': clientId,
      'seccion_key': seccionKey,
      'gestor_uid': uid,
      'nombre_archivo': filename,
      'mime_type': 'image/jpeg',
      'tipo': 'jpg',
      'storage_path': storagePath,
      'download_url': downloadUrl,
      'size_bytes': jpegBytes.length,
      'estado': 'disponible',
      'source_mode': 'client_fallback',
      'created_at': FieldValue.serverTimestamp(),
    };

    await _db.collection('cartas_generadas').doc(docId).set(payload, SetOptions(merge: true));

    letters = await _firestoreService.getClientLetters(
      campaignId: campaignId,
      clientId: clientId,
      section: seccionKey,
    );
    return letters;
  }
}
