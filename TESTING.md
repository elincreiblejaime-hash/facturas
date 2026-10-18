# Pruebas de facturación

Instalar `requirements.txt` y `requirements-test.txt`, y ejecutar:

```sh
python -m unittest -v
```

Las pruebas no arrancan el bot ni llaman a Telegram, Google Drive o Gmail.
Comprueban parsing, handlers, redondeo y PDFs: caso de tres conceptos con
texto largo, 80 conceptos, una descripción mayor que una página, documento
vacío y presupuesto. Se verifican palabras, límites y ausencia de solapamientos.

## Números y totales

- Cantidad, precio y descuento aceptan coma o punto decimal: `1,5`, `1.5`.
- Un único separador siempre es decimal: `1.234` significa 1,234 unidades.
  Para miles usar `1234`, `1.234,56` o `1,234.56`.
- Se rechazan negativos, NaN, infinito y agrupaciones mal formadas.
- Se usan decimales exactos y redondeo comercial a céntimos por línea.
  El subtotal suma esas líneas; el descuento en euros se resta antes del IVA
  del 21%, que se redondea a céntimos. El total suma base e IVA.
- `precio_total` recibido se ignora: el PDF lo recalcula desde cantidad y precio.
- La salida española usa `1.234,56 €`.

El PDF de referencia contiene una primera línea de cantidad 433 y precio 433.
Estos datos dan 187.489,00 €, base 187.743,00 €, IVA 39.426,03 € y total
227.169,03 €. La corrección conserva esos valores de entrada; no supone que
la cantidad debiera ser 1.
