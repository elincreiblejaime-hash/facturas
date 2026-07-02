# -*- coding: utf-8 -*-

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph, Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generar_factura(datos, nombre_archivo):
    """Genera un PDF de factura o presupuesto usando los datos proporcionados."""
    try:
        tipo_documento = datos.get('tipo_documento', 'factura')
        numero_documento = datos['numero_documento']
        fecha = datos['fecha']
        cliente_nombre = datos['cliente_nombre']
        cliente_direccion = datos['cliente_direccion']
        cliente_cp_ciudad = datos['cliente_cp_ciudad']
        cliente_nif = datos['cliente_nif']
        filas_factura = datos['filas_factura']
        descuento = datos.get('descuento', 0)

        # Crear canvas
        c = canvas.Canvas(nombre_archivo, pagesize=letter)
        width, height = letter

        # Definir márgenes y secciones
        margen_superior = height * 0.05  # 5% de margen superior
        margen_inferior = height * 0.05  # 5% de margen inferior
        seccion_superior = height * 0.15  # 15% para número de factura y fecha
        seccion_inferior = height * 0.15  # 15% para la tabla 2
        espacio_central = height * 0.60  # 60% para la tabla 1

        # Número de documento y fecha (en la sección superior, ajustado 8 píxeles hacia arriba)
        c.drawString(20, height - margen_superior - 12, "Nº %s: %s" % (tipo_documento.capitalize(), numero_documento))
        c.drawString(width - 120, height - margen_superior - 12, "Fecha: %s" % fecha)

        # Datos del emisor (en la sección superior, bajado 5 píxeles)
        emisor_text = """Francisco Javier Caldera Serrano
C/Luis Buñuel, Nº3, 2ºC
CP: 06800, Mérida
Teléfono: 669493623
E-mail: fjcserrano1963@gmail.com
N.I.F.: 09170099-E"""
        
        styles = getSampleStyleSheet()
        styles['Normal'].alignment = 1  # Centrado
        emisor_paragraph = Paragraph(emisor_text.replace("\n", "<br/>"), styles['Normal'])
        
        emisor_width = 250
        emisor_height = 100

        # Calcular el margen lateral de la tabla 1
        table_width = width * 0.9
        margen_lateral_tabla = (width - table_width) / 2

        # Posición del emisor (ajustado al margen lateral de la tabla 1)
        emisor_x = margen_lateral_tabla
        emisor_y = height - margen_superior - seccion_superior - 5
        
        c.rect(emisor_x, emisor_y, emisor_width, emisor_height)
        frame_emisor = Frame(emisor_x + 5, emisor_y + 5, emisor_width - 10, emisor_height - 10, showBoundary=0)
        frame_emisor.addFromList([emisor_paragraph], c)

        # Datos del cliente (en la sección superior, bajado 5 píxeles)
        cliente_text = "<b>CLIENTE</b><br/>%s<br/>%s<br/>%s<br/>%s" % (cliente_nombre, cliente_direccion, cliente_cp_ciudad, cliente_nif)
        
        cliente_paragraph = Paragraph(cliente_text.replace("\n", "<br/>"), styles['Normal'])
        
        cliente_width = 250
        cliente_height = 100

        # Posición del cliente (ajustado al margen lateral de la tabla 1)
        cliente_x = width - margen_lateral_tabla - cliente_width
        cliente_y = height - margen_superior - seccion_superior - 5
        
        c.rect(cliente_x, cliente_y, cliente_width, cliente_height)
        frame_cliente = Frame(cliente_x + 5, cliente_y + 5, cliente_width - 10, cliente_height - 10, showBoundary=0)
        frame_cliente.addFromList([cliente_paragraph], c)

        # Tabla de la factura (en el espacio central, bajada 30 píxeles en total)
        data = [["Descripción", "Cantidad", "P/UND", "Precio Total"]]

        # Agregar filas de la factura
        for fila in filas_factura:
            descripcion_paragraph = Paragraph(fila['descripcion'], styles['Normal'])
            
            # Formatear números con comas
            cantidad_str = f"{fila['cantidad']:,.2f}".replace('.', ',')
            precio_unitario_str = f"{fila['precio_unitario']:,.2f}".replace('.', ',')
            precio_total_str = f"{fila['precio_total']:,.2f}".replace('.', ',')
            
            data.append([
                descripcion_paragraph,
                cantidad_str,
                precio_unitario_str + "€",
                precio_total_str + "€"
            ])

        # Agregar fila de descuento si existe
        if descuento > 0:
            descuento_str = f"{descuento:,.2f}".replace('.', ',')
            data.append([
                Paragraph("Descuento", styles['Normal']),
                "",
                "",
                f"-{descuento_str}€"
            ])

        # Calcular la altura de la tabla 1
        altura_por_fila = 20
        altura_total_filas = len(data) * altura_por_fila
        
        if altura_total_filas < espacio_central:
            altura_ultima_fila = espacio_central - (altura_total_filas - altura_por_fila)
            row_heights = [30] + [altura_por_fila] * (len(data) - 2) + [altura_ultima_fila]
        else:
            row_heights = [30] + [altura_por_fila] * (len(data) - 1)

        # Crear la tabla con altura ajustada
        table = Table(data, colWidths=[table_width * 0.5, table_width * 0.15, table_width * 0.15, table_width * 0.2], rowHeights=row_heights)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('VALIGN', (0, 1), (-1, -1), 'TOP')
        ]))
        
        # Posición de la tabla 1 (en el espacio central, bajada 30 píxeles en total)
        table_y = cliente_y - espacio_central - 30
        table.wrapOn(c, table_width, height - 200)
        table.drawOn(c, margen_lateral_tabla, table_y)

        # Calcular el total de la factura
        total = sum(fila['precio_total'] for fila in filas_factura)
        total_con_descuento = total - descuento
        iva = total_con_descuento * 0.21
        total_con_iva = total_con_descuento + iva

        # Formatear números con comas
        total_str = f"{total_con_descuento:,.2f}".replace('.', ',')
        iva_str = f"{iva:,.2f}".replace('.', ',')
        total_con_iva_str = f"{total_con_iva:,.2f}".replace('.', ',')

        # Segunda tabla con el total y el IVA (en la sección inferior, centrada en la página)
        table2_width = table_width * 0.7
        
        if tipo_documento == 'factura':
            data2 = [
                ["METODO DE PAGO POR TRANSFERENCIA BANCARIA A:\nES4601826437850201529467\nBBVA", f"Total: {total_str}€"],
                ["", f"IVA 21%: {iva_str}€"],
                ["", f"Total con Iva: {total_con_iva_str}€"]
            ]
        else:
            data2 = [
                ["Forma de pago por transferencia bancaria", f"Total: {total_str}€"],
                ["", f"IVA 21%: {iva_str}€"],
                ["", f"Total con Iva: {total_con_iva_str}€"]
            ]
        
        styles.add(ParagraphStyle(name='BlackText', textColor=colors.black, alignment=1))
        if tipo_documento == 'factura':
            data2[0][0] = Paragraph(data2[0][0], styles['BlackText'])
        
        table2 = Table(data2, colWidths=[table2_width * 0.7, table2_width * 0.3])
        table2.setStyle(TableStyle([
            ('SPAN', (0, 0), (0, 2)),
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 1), (-1, -1), colors.white),
            ('BACKGROUND', (1, 2), (1, 2), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        
        # Posición de la tabla 2 (en la sección inferior, centrada en la página)
        table2_y = margen_inferior - 15
        table2.wrapOn(c, width - 100, height - 400)
        table2.drawOn(c, (width - table2_width) / 2, table2_y)

        c.save()
        return nombre_archivo

    except Exception as e:
        print(f"Error al generar {tipo_documento}: {e}")
        raise

if __name__ == "__main__":
    # Uso desde línea de comandos (no se usa en Render, pero se deja para compatibilidad)
    import sys
    try:
        datos = {
            'tipo_documento': sys.argv[1],
            'numero_documento': sys.argv[2],
            'fecha': sys.argv[3],
            'cliente_nombre': sys.argv[4],
            'cliente_direccion': sys.argv[5],
            'cliente_cp_ciudad': sys.argv[6],
            'cliente_nif': sys.argv[7],
            'filas_factura': []
        }

        for i in range(8, len(sys.argv), 3):
            descripcion = sys.argv[i]
            cantidad = float(sys.argv[i + 1])
            precio_unitario = float(sys.argv[i + 2])
            precio_total = cantidad * precio_unitario
            datos['filas_factura'].append({
                'descripcion': descripcion,
                'cantidad': cantidad,
                'precio_unitario': precio_unitario,
                'precio_total': precio_total
            })

        nombre_archivo = generar_factura(datos, f"{datos['cliente_nombre']}_{datos['tipo_documento']}.pdf")
        print(f"Documento generado: {nombre_archivo}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
