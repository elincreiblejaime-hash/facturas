# -*- coding: utf-8 -*-
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
from numeros import parse_numero, formato_es, calcular_totales


def generar_factura(datos, nombre_archivo):
    """Filas automáticas y flujo paginado; importes derivados de cantidad y precio."""
    tipo = datos.get('tipo_documento', 'factura')
    filas = datos['filas_factura']
    importes, descuento, base, iva, total = calcular_totales(filas, datos.get('descuento', 0))
    doc = SimpleDocTemplate(str(nombre_archivo), pagesize=letter,
                            leftMargin=30, rightMargin=30, topMargin=40, bottomMargin=40)
    normal = ParagraphStyle('Texto', fontName='Helvetica', fontSize=10, leading=13)
    derecha = ParagraphStyle('Numero', parent=normal, alignment=2)
    def p(texto, estilo=normal):
        return Paragraph(escape(str(texto)).replace('\n', '<br/>'), estilo)
    def euros(valor):
        return formato_es(valor) + ' €'
    ancho = doc.width
    cabecera = Table([[p(f'Nº {tipo.capitalize()}: {datos["numero_documento"]}'),
                       p(f'Fecha: {datos["fecha"]}', derecha)]], colWidths=[ancho * .65, ancho * .35])
    emisor = 'Francisco Javier Caldera Serrano\nC/Luis Buñuel, Nº3, 2ºC\nCP: 06800, Mérida\nTeléfono: 669493623\nE-mail: fjcserrano1963@gmail.com\nN.I.F.: 09170099-E'
    cliente = 'CLIENTE\n' + '\n'.join(str(datos[k]) for k in ('cliente_nombre', 'cliente_direccion', 'cliente_cp_ciudad', 'cliente_nif'))
    contactos = Table([[p(emisor), p(cliente)]], colWidths=[ancho / 2] * 2)
    contactos.setStyle(TableStyle([('BOX', (0,0), (0,0), 1, colors.black), ('BOX', (1,0), (1,0), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'TOP'), ('TOPPADDING', (0,0), (-1,-1), 8), ('BOTTOMPADDING', (0,0), (-1,-1), 8)]))
    data = [['Descripción', 'Cantidad', 'P/UND', 'Precio Total']]
    for fila, importe in zip(filas, importes):
        cantidad = format(parse_numero(fila['cantidad']), 'f').replace('.', ',')
        data.append([p(fila['descripcion']), p(cantidad, derecha),
                     p(euros(parse_numero(fila['precio_unitario'])), derecha), p(euros(importe), derecha)])
    if descuento:
        data.append([p('Descuento'), '', '', p('-' + euros(descuento), derecha)])
    tabla = Table(data, colWidths=[ancho*.49, ancho*.13, ancho*.18, ancho*.20],
                  repeatRows=1, splitByRow=1, splitInRow=1)
    tabla.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige), ('GRID', (0,0), (-1,-1), .5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('TOPPADDING', (0,0), (-1,-1), 7), ('BOTTOMPADDING', (0,0), (-1,-1), 7)]))
    pago = ('METODO DE PAGO POR TRANSFERENCIA BANCARIA A:\nES4601826437850201529467\nBBVA'
            if tipo == 'factura' else 'Forma de pago por transferencia bancaria')
    resumen = Table([[p(pago), p(f'Total: {euros(base)}\nIVA 21%: {euros(iva)}\nTotal con Iva: {euros(total)}', derecha)]], colWidths=[ancho*.55, ancho*.45])
    resumen.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 10), ('BOTTOMPADDING', (0,0), (-1,-1), 10)]))
    def pie(canvas, documento):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.drawRightString(letter[0] - 30, 22, f'Página {documento.page}')
        canvas.restoreState()
    doc.build([cabecera, Spacer(1, 12), contactos, Spacer(1, 18), tabla,
               KeepTogether([Spacer(1, 16), resumen])], onFirstPage=pie, onLaterPages=pie)
    return nombre_archivo


if __name__ == '__main__':
    import sys
    datos = dict(zip(('tipo_documento', 'numero_documento', 'fecha', 'cliente_nombre',
                      'cliente_direccion', 'cliente_cp_ciudad', 'cliente_nif'), sys.argv[1:8]))
    datos['filas_factura'] = [dict(descripcion=sys.argv[i], cantidad=parse_numero(sys.argv[i+1]),
                                  precio_unitario=parse_numero(sys.argv[i+2])) for i in range(8, len(sys.argv), 3)]
    print(generar_factura(datos, f'{datos["cliente_nombre"]}_{datos["tipo_documento"]}.pdf'))
