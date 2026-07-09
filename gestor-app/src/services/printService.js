export async function printImageFromUrl(url, title = 'Carta de Cobranza') {
  return new Promise((resolve, reject) => {
    const win = window.open('', '_blank', 'noopener,noreferrer,width=900,height=1200');
    if (!win) {
      reject(new Error('El navegador bloqueó la ventana de impresión.'));
      return;
    }

    win.document.write(`
      <html>
        <head><title>${title}</title></head>
        <body style="margin:0;display:flex;justify-content:center;align-items:center;background:#fff;">
          <img id="print-image" src="${url}" style="max-width:100%;height:auto;" />
        </body>
      </html>
    `);
    win.document.close();
    const img = win.document.getElementById('print-image');
    img.onload = () => {
      win.focus();
      win.print();
      resolve();
    };
    img.onerror = () => reject(new Error('No se pudo cargar la imagen para impresión.'));
  });
}
