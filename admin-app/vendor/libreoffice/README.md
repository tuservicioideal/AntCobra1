# LibreOffice portable (Windows)

Para empaquetar conversión DOCX→PDF en el EXE sin depender de Microsoft Word:

1. Descargue **LibreOffice Portable** para Windows desde https://www.libreoffice.org/download/portable-versions/
2. Extraiga el contenido en esta carpeta de forma que exista:

   ```
   vendor/libreoffice/App/libreoffice/program/soffice.exe
   ```

   (La ruta exacta puede variar; `word_template_engine.resolve_soffice_path` busca `soffice.exe`
   recursivamente bajo `vendor/libreoffice/`.)

3. Recompile el EXE: `pyinstaller AntCobranzas.spec`

Si esta carpeta está vacía, la app usará LibreOffice del sistema (PATH o Program Files) o
Microsoft Word vía `docx2pdf` como respaldo.
