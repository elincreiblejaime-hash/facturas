import ast
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
import pdfplumber
from generar_factura import generar_factura
from numeros import parse_numero, calcular_totales, formato_es


def datos():
    return dict(tipo_documento='factura', numero_documento='26/044', fecha='19/10/2026',
        cliente_nombre='Cliente de prueba', cliente_direccion='Calle de prueba 1',
        cliente_cp_ciudad='06000 Ciudad', cliente_nif='NIF de prueba', filas_factura=[
        dict(descripcion='Reparar circuitos de maniobra en cuadro eléctrico máquina para funcionamiento de electrofresno motor, ordenar conexiones estrella triángulo en cuadro y motor, montar motor en máquina, reparar cepilladora SCM en taller pequeño, factura según presupuesto 26/06', cantidad=433, precio_unitario=433, precio_total=0),
        dict(descripcion='Trabajo tornero', cantidad=1, precio_unitario=170),
        dict(descripcion='Interruptor completo con cinco auxiliares NO para maniobra electrofresno', cantidad=1, precio_unitario=84)])


class NumerosTest(unittest.TestCase):
    def test_decimales(self):
        for texto, esperado in [('1,5','1.5'), ('1.5','1.5'), ('1.234,56','1234.56'), ('1,234.56','1234.56'), ('1.234','1.234'), (' 0,00 ','0')]:
            self.assertEqual(parse_numero(texto), Decimal(esperado))
        for texto in ['NaN','inf','-1','1,2,3','1.23,45','1e3','','1 000','1.234.567']:
            with self.assertRaises(ValueError): parse_numero(texto)
    def test_totales(self):
        self.assertEqual(calcular_totales(datos()['filas_factura'])[2:], (Decimal('187743.00'), Decimal('39426.03'), Decimal('227169.03')))
        filas = [dict(cantidad='3', precio_unitario='0.335', precio_total=999)]
        self.assertEqual(calcular_totales(filas, '0,01'), ([Decimal('1.01')], Decimal('0.01'), Decimal('1.00'), Decimal('0.21'), Decimal('1.21')))
        with self.assertRaises(ValueError): calcular_totales(filas, 2)
        self.assertEqual(formato_es(Decimal('1234567.89')), '1.234.567,89')
    def test_handlers_sin_servicios(self):
        # Ejecutar los handlers reales sin arrancar Telegram ni cargar credenciales.
        arbol = ast.parse(Path('bot_facturas_render.py').read_text(encoding='utf-8-sig'))
        nombres = {'cantidad_producto', 'precio_unitario', 'cantidad_descuento'}
        funciones = [n for n in arbol.body if isinstance(n, ast.AsyncFunctionDef) and n.name in nombres]
        modulo = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + funciones, type_ignores=[])
        ns = dict(parse_numero=parse_numero, calcular_totales=calcular_totales, CANTIDAD_PRODUCTO=1, PRECIO_UNITARIO=2, OTRO_PRODUCTO=3, CANTIDAD_DESCUENTO=4, generar_previsualizacion=AsyncMock(return_value=5))
        exec(compile(ast.fix_missing_locations(modulo), '<handlers>', 'exec'), ns)
        async def probar():
            ctx = SimpleNamespace(user_data={'descripcion_producto':'Servicio'})
            upd = SimpleNamespace(message=SimpleNamespace(text='1,5', reply_text=AsyncMock()))
            self.assertEqual(await ns['cantidad_producto'](upd,ctx), 2)
            upd.message.text='12.50'
            self.assertEqual(await ns['precio_unitario'](upd,ctx), 3)
            self.assertEqual(ctx.user_data['filas_factura'][0]['cantidad'], Decimal('1.5'))
            upd.message.text='NaN'
            self.assertEqual(await ns['precio_unitario'](upd,ctx), 2)
            self.assertEqual(len(ctx.user_data['filas_factura']), 1)
            upd.message.text='100'
            self.assertEqual(await ns['cantidad_descuento'](upd,ctx), 4)
            upd.message.text='0,50'
            self.assertEqual(await ns['cantidad_descuento'](upd,ctx), 5)
        with self.assertRaises(StopIteration):
            probar().send(None)


class PdfTest(unittest.TestCase):
    def test_ejemplo_y_paginacion(self):
        with TemporaryDirectory(dir=Path.cwd()) as carpeta:
            for caso in ['ejemplo', 'muchas', 'gigante', 'vacia', 'presupuesto']:
                d = datos()
                if caso == 'muchas':
                    d['filas_factura'] = [dict(descripcion=f'Concepto {i:03d} ' + 'descripción larga & <texto>\n' * 5, cantidad='1,5', precio_unitario='12.50') for i in range(80)]
                if caso == 'gigante':
                    d['filas_factura'] = [dict(descripcion='inicio ' + 'texto extenso ' * 1500 + ' finalgigante', cantidad=1, precio_unitario=1)]
                if caso == 'vacia': d['filas_factura'] = []
                if caso == 'presupuesto': d['tipo_documento'] = 'presupuesto'
                ruta = Path(carpeta) / (caso + '.pdf')
                generar_factura(d, ruta)
                with pdfplumber.open(ruta) as pdf:
                    texto = '\n'.join(p.extract_text() or '' for p in pdf.pages)
                    self.assertIn('Total con Iva:', texto)
                    if caso == 'ejemplo':
                        self.assertIn('227.169,03', texto)
                        self.assertEqual(len(pdf.pages), 1)
                    if caso == 'muchas':
                        self.assertGreater(len(pdf.pages), 1)
                        for i in range(80): self.assertEqual(texto.count(f'Concepto {i:03d}'), 1)
                    if caso == 'gigante':
                        self.assertGreater(len(pdf.pages), 1)
                        self.assertIn('finalgigante', texto)
                    for page in pdf.pages:
                        words = page.extract_words()
                        for w in words:
                            self.assertGreaterEqual(w['top'], 30)
                            self.assertLessEqual(w['bottom'], 780)
                        # Toda pareja de palabras debe ocupar áreas independientes.
                        for i, a in enumerate(words):
                            for b in words[i+1:]:
                                dx = min(a['x1'], b['x1']) - max(a['x0'], b['x0'])
                                dy = min(a['bottom'], b['bottom']) - max(a['top'], b['top'])
                                self.assertFalse(dx > 1 and dy > 1, (caso, a, b))


if __name__ == '__main__': unittest.main()


