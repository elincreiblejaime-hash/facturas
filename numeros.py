from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

CENTIMO = Decimal('0.01')


def parse_numero(valor):
    """Un separador indica decimales; ambos admiten miles agrupados.

    1.234 y 1,234 significan 1,234 unidades, nunca 1234.
    Para miles usar 1234,56 o 1.234,56 (también 1,234.56).
    """
    texto = str(valor).strip()
    if ',' in texto and '.' in texto:
        decimal = ',' if texto.rfind(',') > texto.rfind('.') else '.'
        miles = '.' if decimal == ',' else ','
        patron = rf'[+-]?\d{{1,3}}(?:{re.escape(miles)}\d{{3}})+{re.escape(decimal)}\d+'
        if not re.fullmatch(patron, texto):
            raise ValueError('Agrupación de miles no válida')
        texto = texto.replace(miles, '').replace(decimal, '.')
    else:
        if not re.fullmatch(r'[+-]?\d+(?:[.,]\d+)?', texto):
            raise ValueError('Número no válido')
        texto = texto.replace(',', '.')
    try:
        numero = Decimal(texto)
    except InvalidOperation as exc:
        raise ValueError('Número no válido') from exc
    if not numero.is_finite() or numero < 0:
        raise ValueError('Se requiere un número finito no negativo')
    return numero


def dinero(valor):
    return parse_numero(valor).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def formato_es(valor):
    return format(valor, ',.2f').translate(str.maketrans(',.', '.,'))


def calcular_totales(filas, descuento=0):
    importes = [dinero(parse_numero(f['cantidad']) * parse_numero(f['precio_unitario'])) for f in filas]
    subtotal = sum(importes, Decimal('0.00'))
    descuento = dinero(descuento)
    if descuento > subtotal:
        raise ValueError('El descuento supera el subtotal')
    base = subtotal - descuento
    iva = dinero(base * Decimal('0.21'))
    return importes, descuento, base, iva, base + iva
