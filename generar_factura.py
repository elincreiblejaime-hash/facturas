# -*- coding: utf-8 -*-
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle, Paragraph
from numeros import parse_numero, formato_es, calcular_totales


def generar_factura(datos, nombre_archivo):
    """Conserva la plantilla original, con filas dinámicas y páginas adicionales."""
    tipo = datos.get('tipo_documento', 'factura')
    filas = datos['filas_factura']
    importes, descuento, base, iva, total = calcular_totales(filas, datos.get('descuento', 0))
    width, height = letter
    ancho = width * .9
    margen = (width - ancho) / 2
    normal = ParagraphStyle('Texto', fontName='Helvetica', fontSize=10, leading=12, alignment=1)
    negrita = ParagraphStyle('Negrita', parent=normal, fontName='Helvetica-Bold')
    total_style = ParagraphStyle('Totales', parent=negrita, fontSize=8, leading=12)
    def p(texto, estilo=normal):
        return Paragraph(escape(str(texto)).replace('\n', '<br/>'), estilo)
    def euros(valor):
        return formato_es(valor) + '€'

    emisor = 'Francisco Javier Caldera Serrano\nC/Luis Buñuel, Nº3, 2ºC\nCP: 06800, Mérida\nTeléfono: 669493623\nE-mail: fjcserrano1963@gmail.com\nN.I.F.: 09170099-E'
    cliente = '<b>CLIENTE</b><br/>' + '<br/>'.join(escape(str(datos[k])).replace('\n', '<br/>') for k in ('cliente_nombre', 'cliente_direccion', 'cliente_cp_ciudad', 'cliente_nif'))
    contacto_data = [[p(emisor), '', Paragraph(cliente, normal)]]
    contacto_style = TableStyle([
        ('BOX', (0,0), (0,0), 1, colors.black), ('BOX', (2,0), (2,0), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12)])
    contactos = Table(contacto_data, colWidths=[250, ancho-500, 250], style=contacto_style)
    _, contacto_h = contactos.wrap(ancho, height)
    contacto_h = max(100, contacto_h)
    contactos = Table(contacto_data, colWidths=[250, ancho-500, 250],
                      rowHeights=[contacto_h], style=contacto_style)

    data = [['Descripción', 'Cantidad', 'P/UND', 'Precio Total']]
    for fila, importe in zip(filas, importes):
        data.append([p(fila['descripcion']), p(formato_es(parse_numero(fila['cantidad']))),
                     p(euros(parse_numero(fila['precio_unitario']))), p(euros(importe))])
    if descuento:
        data.append([p('Descuento'), '', '', p('-' + euros(descuento))])
    columnas = [ancho*.5, ancho*.15, ancho*.15, ancho*.2]
    tabla = Table(data, colWidths=columnas, repeatRows=1, splitByRow=1, splitInRow=1,
                  minRowHeights=[30] + [20]*(len(data)-1))
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige), ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'), ('VALIGN', (0,1), (-1,-1), 'TOP')]))
    pago = ('METODO DE PAGO POR TRANSFERENCIA BANCARIA A: ES4601826437850201529467 BBVA'
            if tipo == 'factura' else 'Forma de pago por transferencia bancaria')
    resumen_ancho = ancho*.7
    resumen = Table([[p(pago, negrita), p('Total: '+euros(base), total_style)],
                     ['', p('IVA 21%: '+euros(iva), total_style)],
                     ['', p('Total con Iva: '+euros(total), total_style)]],
                    colWidths=[resumen_ancho*.7, resumen_ancho*.3])
    resumen.setStyle(TableStyle([('SPAN', (0,0), (0,2)), ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12)]))
    _, resumen_h = resumen.wrap(resumen_ancho, height)
    pago_y = height*.05-15
    tabla_bottom = max(124.4, pago_y+resumen_h+18)
    tabla_top = height*.95-23.8-contacto_h-20
    disponible = tabla_top-tabla_bottom
    if disponible < 60:
        raise ValueError('Los datos del cliente no dejan espacio para los conceptos')
    c = canvas.Canvas(str(nombre_archivo), pagesize=letter)
    pendiente = tabla
    while pendiente is not None:
        c.setFont('Helvetica', 12)
        c.drawString(20, height*.95-12, f'Nº {tipo.capitalize()}: {datos["numero_documento"]}')
        c.drawString(width-120, height*.95-12, f'Fecha: {datos["fecha"]}')
        contactos.wrapOn(c, ancho, height)
        contactos.drawOn(c, margen, height*.95-23.8-contacto_h)
        _, alto = pendiente.wrap(ancho, disponible)
        if alto <= disponible:
            parte, pendiente = pendiente, None
        else:
            partes = pendiente.split(ancho, disponible)
            if len(partes) != 2:
                raise ValueError('No se puede dividir el concepto entre páginas')
            parte, pendiente = partes
        _, alto = parte.wrap(ancho, disponible)
        # El espacio para escritura manual conserva el fondo y todas las columnas.
        hueco = disponible-alto
        if hueco > .01:
            c.setFillColor(colors.beige)
            c.rect(margen, tabla_bottom, ancho, hueco, fill=1, stroke=0)
            c.setStrokeColor(colors.black)
            c.setLineWidth(1)
            x = margen
            for columna in [0]+columnas:
                x += columna
                c.line(x, tabla_bottom, x, tabla_bottom+hueco)
            c.line(margen, tabla_bottom, margen+ancho, tabla_bottom)
        parte.drawOn(c, margen, tabla_top-alto)
        if pendiente is None:
            resumen.drawOn(c, (width-resumen_ancho)/2, pago_y)
        c.showPage()
    c.save()
    return nombre_archivo


if __name__ == '__main__':
    import sys
    datos = dict(zip(('tipo_documento', 'numero_documento', 'fecha', 'cliente_nombre',
                      'cliente_direccion', 'cliente_cp_ciudad', 'cliente_nif'), sys.argv[1:8]))
    datos['filas_factura'] = [dict(descripcion=sys.argv[i], cantidad=parse_numero(sys.argv[i+1]),
                                  precio_unitario=parse_numero(sys.argv[i+2])) for i in range(8, len(sys.argv), 3)]
    print(generar_factura(datos, f'{datos["cliente_nombre"]}_{datos["tipo_documento"]}.pdf'))
