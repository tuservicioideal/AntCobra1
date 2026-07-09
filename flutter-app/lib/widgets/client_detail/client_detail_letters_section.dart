import 'package:flutter/material.dart';

import '../../models/client_model.dart';

import 'detail_section_tile.dart';



typedef LetterMenuAction = void Function(CartaGenerada letter, String action);



class ClientDetailLettersSection extends StatelessWidget {

  final List<CartaGenerada> letters;

  final bool loading;

  final bool generating;

  final LetterMenuAction onMenuAction;

  final VoidCallback? onGenerate;



  const ClientDetailLettersSection({

    super.key,

    required this.letters,

    required this.loading,

    this.generating = false,

    required this.onMenuAction,

    this.onGenerate,

  });



  @override

  Widget build(BuildContext context) {

    if (loading) {

      return const DetailSectionTile(

        title: 'Cartas JPG publicadas',

        icon: Icons.image_outlined,

        initiallyExpanded: false,

        child: Padding(

          padding: EdgeInsets.symmetric(vertical: 8),

          child: Center(child: CircularProgressIndicator(strokeWidth: 2)),

        ),

      );

    }



    if (letters.isEmpty) {

      return DetailSectionTile(

        title: 'Cartas JPG publicadas',

        icon: Icons.image_outlined,

        initiallyExpanded: true,

        child: Column(

          crossAxisAlignment: CrossAxisAlignment.stretch,

          children: [

            const Text(

              'No hay cartas JPG publicadas para este cliente.',

              style: TextStyle(fontSize: 13, color: Colors.black54),

            ),

            const SizedBox(height: 8),

            FilledButton.icon(

              onPressed: generating ? null : onGenerate,

              icon: generating

                  ? const SizedBox(

                      width: 16,

                      height: 16,

                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),

                    )

                  : const Icon(Icons.image_outlined, size: 18),

              label: Text(generating ? 'Generando carta…' : 'Generar carta JPG'),

            ),

          ],

        ),

      );

    }



    return DetailSectionTile(

      title: 'Cartas JPG publicadas',

      icon: Icons.image_outlined,

      initiallyExpanded: false,

      child: Column(

        children: letters

            .map(

              (letter) => ListTile(

                contentPadding: EdgeInsets.zero,

                dense: true,

                leading: const Icon(Icons.description_outlined, size: 20),

                title: Text(

                  letter.nombreArchivo,

                  style: const TextStyle(fontSize: 13),

                ),

                subtitle: Text(

                  'Carta #${letter.numeroCarta}',

                  style: const TextStyle(fontSize: 11),

                ),

                trailing: PopupMenuButton<String>(

                  onSelected: (value) => onMenuAction(letter, value),

                  itemBuilder: (_) => const [

                    PopupMenuItem(value: 'abrir', child: Text('Abrir / Descargar')),

                    PopupMenuItem(value: 'compartir', child: Text('Compartir')),

                    PopupMenuItem(value: 'imprimir', child: Text('Imprimir')),

                  ],

                ),

              ),

            )

            .toList(),

      ),

    );

  }

}


