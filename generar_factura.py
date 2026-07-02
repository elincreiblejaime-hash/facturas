# -*- coding: utf-8 -*-

import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph, Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Esta función SOLO genera el PDF.
# La autenticación de Google está en bot_facturas_render.py

def generar_factura(datos, nombre_archivo):
    """Genera un PDF de factura o presupuesto usando los datos proporcionados."""
    try:
        tipo_documento = datos['tipo_documento']
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

        # Márgenes
        margen_izquierdo = 30
        margen_derecho = 30
        margen_superior = 750
        margen_inferior = 50
        ancho_disponible = width - margen_izquierdo - margen_derecho

        # Estilos
        styles = getSampleStyleSheet()
        titulo_style = ParagraphStyle(
            'titulo',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.black,
            alignment=1,
            spaceAfter=6
        )

        # Título
        titulo = Paragraph(f"<b>{tipo_documento.upper()}</b>", titulo_style)
        titulo.wrapOn(c, ancho_disponible, height - margen_superior)
        titulo.drawOn(c, margen_izquierdo, margen_superior)

        # Información del documento
        y = margen_superior - 30
        c.setFont("Helvetica", 9)
        c.drawString(margen_izquierdo, y, f"Número: {numero_documento}")
        c.drawString(margen_izquierdo + 200, y, f"Fecha: {fecha}")

        # Información del cliente
        y -= 30
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margen_izquierdo, y, "CLIENTE:")
        c.setFont("Helvetica", 9)
        y -= 15
        c.drawString(margen_izquierdo, y, cliente_nombre)
        y -= 12
        c.drawString(margen_izquierdo, y, cliente_direccion)
        y -= 12
        c.drawString(margen_izquierdo, y, cliente_cp_ciudad)
        y -= 12
        c.drawString(margen_izquierdo, y, f"NIF: {cliente_nif}")

        # Tabla de productos
        y -= 30

        # Encabezados de tabla
        data = [["Descripción", "Cantidad", "Precio Unitario", "Total"]]

        for fila in filas_factura:
            descripcion = fila['descripcion']
            cantidad = fila['cantidad']
            precio_unitario = fila['precio_unitario']
            precio_total = fila.get('precio_total', cantidad * precio_unitario)
            
            data.append([
                descripcion,
                f"{cantidad:.2f}",
                f"{precio_unitario:.2f}€",
                f"{precio_total:.2f}€"
            ])

        # Crear tabla
        table_width = ancho_disponible
        table = Table(data, colWidths=[table_width * 0.45, table_width * 0.15, table_width * 0.2, table_width * 0.2])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ]))

        table.wrapOn(c, table_width, height - 200)
        table.drawOn(c, margen_izquierdo, y - 150)

        # Calcular totales
        subtotal = sum(fila['cantidad'] * fila['precio_unitario'] for fila in filas_factura)
        subtotal_con_descuento = subtotal - descuento
        iva = subtotal_con_descuento * 0.21
        total_con_iva = subtotal_con_descuento + iva

        # Formatear números con comas
        total_str = f"{subtotal_con_descuento:,.2f}".replace('.', ',')
        iva_str = f"{iva:,.2f}".replace('.', ',')
        total_con_iva_str = f"{total_con_iva:,.2f}".replace('.', ',')

        # Segunda tabla con el total y el IVA (en la sección inferior, centrada en la página)
        table2_width = width * 0.7
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
        
        table2 = Table(data2, colWidths=[table2_width * 0.7, table2_width * 0.3])
        table2.setStyle(TableStyle([
            ('SPAN', (0, 0), (0, 2)),
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        
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
