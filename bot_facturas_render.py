from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
import os
import pickle
import base64
import json
import tempfile
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import base64

from generar_factura import generar_factura

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables de entorno
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN no está configurado")

GOOGLE_CREDENTIALS_B64 = os.getenv('GOOGLE_CREDENTIALS_B64')
GOOGLE_TOKEN_B64 = os.getenv('GOOGLE_TOKEN_B64')

if not GOOGLE_CREDENTIALS_B64 or not GOOGLE_TOKEN_B64:
    raise ValueError("GOOGLE_CREDENTIALS_B64 y GOOGLE_TOKEN_B64 deben estar configurados")

# IDs de carpetas Google Drive (desde env vars)
# ÚNICA variable necesaria: la carpeta raíz que contiene años (2024, 2025, 2026, 2027...)
GOOGLE_DRIVE_RAIZ_FACTURAS = os.getenv('GOOGLE_DRIVE_RAIZ_FACTURAS', '1-1_NrAlbewUWhMw4zRjdLMx0OFarHBOe')

MESES = {
    1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO',
    4: 'ABRIL', 5: 'MAYO', 6: 'JUNIO',
    7: 'JULIO', 8: 'AGOSTO', 9: 'SEPTIEMBRE',
    10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
}

TIPOS_DOCUMENTO_CARPETAS = {
    'factura': 'FACTURAS',
    'presupuesto': 'PRESUPUESTOS'
}

EMAIL_REMITENTE = os.getenv('EMAIL_REMITENTE', 'jaime96ct@gmail.com')

# Scopes de Google
SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/drive']

# Estados de la conversación
ELECCION, NUMERO_DOCUMENTO, FECHA, CLIENTE_NOMBRE, CLIENTE_DIRECCION, CLIENTE_CP_CIUDAD, CLIENTE_NIF, DESCRIPCION_PRODUCTO, CANTIDAD_PRODUCTO, PRECIO_UNITARIO, OTRO_PRODUCTO, DESCUENTO, CANTIDAD_DESCUENTO, CONFIRMAR_GENERAR, CONFIRMAR_ENVIAR, DESTINATARIO_CORREO = range(16)

# ======================
# AUTENTICACIÓN GOOGLE
# ======================

def obtener_credenciales():
    """Carga credenciales desde env vars (base64 decodificado)."""
    try:
        # Decodificar credentials.json
        credentials_json_bytes = base64.b64decode(GOOGLE_CREDENTIALS_B64)
        credentials_dict = json.loads(credentials_json_bytes.decode('utf-8'))
        
        # Decodificar token.pickle
        token_pickle_bytes = base64.b64decode(GOOGLE_TOKEN_B64)
        creds = pickle.loads(token_pickle_bytes)
        
        # Verificar si el token es válido; si no, intentar refresco
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                logger.info("Refrescando credenciales de Google")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Error al refrescar credenciales: {e}")
                    raise
            else:
                logger.error("El token no es válido y no se puede refrescar. Regenera token.pickle.")
                raise ValueError("Token inválido o expirado")
        
        return creds
    except Exception as e:
        logger.error(f"Error cargando credenciales: {e}")
        raise

def crear_mensaje(destinatario, asunto, cuerpo, archivo_adjunto=None):
    """Crea un mensaje de correo electrónico."""
    mensaje = MIMEMultipart()
    mensaje['to'] = destinatario
    mensaje['from'] = EMAIL_REMITENTE
    mensaje['subject'] = asunto
    mensaje.attach(MIMEText(cuerpo, 'plain'))

    if archivo_adjunto:
        with open(archivo_adjunto, 'rb') as adjunto:
            parte = MIMEBase('application', 'octet-stream')
            parte.set_payload(adjunto.read())
            encoders.encode_base64(parte)
            parte.add_header('Content-Disposition', 'attachment; filename=%s' % os.path.basename(archivo_adjunto))
            mensaje.attach(parte)

    return {'raw': base64.urlsafe_b64encode(mensaje.as_bytes()).decode('utf-8')}

def enviar_correo(destinatario, asunto, cuerpo, archivo_adjunto=None):
    """Envía un correo electrónico usando la API de Gmail."""
    try:
        creds = obtener_credenciales()
        service = build('gmail', 'v1', credentials=creds)
        mensaje = crear_mensaje(destinatario, asunto, cuerpo, archivo_adjunto)
        enviado = service.users().messages().send(userId='me', body=mensaje).execute()
        logger.info(f"Correo enviado a {destinatario}. ID: {enviado['id']}")
    except Exception as e:
        logger.error(f"Error al enviar correo: {e}")
        raise

def obtener_o_crear_carpeta(service, nombre, carpeta_padre_id):
    """
    Busca una carpeta por nombre dentro de un padre.
    Si no existe, la crea.
    Retorna el ID.
    """
    try:
        # Buscar
        resultado = service.files().list(
            q=f"name='{nombre}' and '{carpeta_padre_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces='drive',
            fields='files(id)',
            pageSize=1
        ).execute()
        
        archivos = resultado.get('files', [])
        
        if archivos:
            logger.info(f"Carpeta '{nombre}' ya existe")
            return archivos[0]['id']
        
        # Si no existe, crear
        carpeta = service.files().create(
            body={
                'name': nombre,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [carpeta_padre_id]
            },
            fields='id'
        ).execute()
        
        logger.info(f"Carpeta creada: {nombre}")
        return carpeta['id']
        
    except Exception as e:
        logger.error(f"Error en obtener_o_crear_carpeta ({nombre}): {e}")
        raise

def subir_a_google_drive(nombre_archivo, ruta_archivo, tipo_documento):
    """
    Navega automáticamente: Raíz → Año → Trimestre → Mes → Tipo (Facturas/Presupuestos)
    Crea lo que falta automáticamente.
    Nunca necesita actualizar variables de entorno.
    """
    try:
        from datetime import datetime
        
        creds = obtener_credenciales()
        service = build('drive', 'v3', credentials=creds)
        
        # Obtener fecha actual
        ahora = datetime.now()
        año = ahora.year  # 2026, 2027, 2028...
        mes = ahora.month  # 1-12
        trimestre = (mes - 1) // 3 + 1  # 1-4
        
        nombre_año = str(año)
        nombre_trimestre = f"TRIMESTRE_{trimestre}"
        nombre_mes = MESES[mes]
        nombre_tipo = TIPOS_DOCUMENTO_CARPETAS[tipo_documento]
        
        logger.info(f"Procesando {tipo_documento}: {nombre_mes} ({mes}/{año}), Trimestre {trimestre}")
        
        # Navegar: Raíz → Año → Trimestre → Mes → Tipo
        id_año = obtener_o_crear_carpeta(service, nombre_año, GOOGLE_DRIVE_RAIZ_FACTURAS)
        id_trimestre = obtener_o_crear_carpeta(service, nombre_trimestre, id_año)
        id_mes = obtener_o_crear_carpeta(service, nombre_mes, id_trimestre)
        id_tipo = obtener_o_crear_carpeta(service, nombre_tipo, id_mes)
        
        # Subir archivo
        file_metadata = {
            'name': nombre_archivo,
            'parents': [id_tipo]
        }
        media = MediaFileUpload(ruta_archivo, mimetype='application/pdf')
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        logger.info(f"Archivo subido a Drive: {file.get('id')} en {año}/{nombre_trimestre}/{nombre_mes}/{nombre_tipo}")
        
    except Exception as e:
        logger.error(f"Error subiendo a Drive: {e}")
        raise

# ======================
# HANDLERS BOT TELEGRAM
# ======================

async def generar_previsualizacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = context.user_data
    try:
        # Calcular precio total para cada fila
        for fila in datos['filas_factura']:
            fila['precio_total'] = fila['cantidad'] * fila['precio_unitario']

        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            nombre_archivo = temp_file.name
            generar_factura(datos, nombre_archivo)
        
        # Enviar PDF al usuario
        await update.message.reply_document(document=open(nombre_archivo, 'rb'), filename="previsualizacion_documento.pdf")
        await update.message.reply_text("Aquí tienes la previsualización. ¿Deseas generar el documento definitivo? (s/n):")
        return CONFIRMAR_GENERAR
    except Exception as e:
        logger.error(f"Error generando previsualización: {e}")
        await update.message.reply_text("❌ Error al generar la previsualización. Intenta de nuevo.")
        return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("¿Qué deseas crear? Responde con 'factura' o 'presupuesto':")
    return ELECCION

async def eleccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    eleccion = update.message.text.strip().lower()
    if eleccion in ['factura', 'presupuesto']:
        context.user_data['tipo_documento'] = eleccion
        await update.message.reply_text(f"Por favor, proporciona el número de {eleccion}:")
        return NUMERO_DOCUMENTO
    else:
        await update.message.reply_text("❌ Opción no válida. Responde con 'factura' o 'presupuesto':")
        return ELECCION

async def numero_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['numero_documento'] = update.message.text
    await update.message.reply_text("Por favor, proporciona la fecha (DD/MM/AAAA):")
    return FECHA

async def fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['fecha'] = update.message.text
    await update.message.reply_text("Por favor, proporciona el nombre del cliente:")
    return CLIENTE_NOMBRE

async def cliente_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cliente_nombre'] = update.message.text
    await update.message.reply_text("Por favor, proporciona la dirección del cliente:")
    return CLIENTE_DIRECCION

async def cliente_direccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cliente_direccion'] = update.message.text
    await update.message.reply_text("Por favor, proporciona el CP y ciudad del cliente:")
    return CLIENTE_CP_CIUDAD

async def cliente_cp_ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cliente_cp_ciudad'] = update.message.text
    await update.message.reply_text("Por favor, proporciona el NIF del cliente:")
    return CLIENTE_NIF

async def cliente_nif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cliente_nif'] = update.message.text
    await update.message.reply_text("Por favor, proporciona la descripción del producto:")
    return DESCRIPCION_PRODUCTO

async def descripcion_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['descripcion_producto'] = update.message.text
    await update.message.reply_text("Por favor, proporciona la cantidad del producto:")
    return CANTIDAD_PRODUCTO

async def cantidad_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cantidad_texto = update.message.text.replace('.', ',')
        cantidad = float(cantidad_texto)
        context.user_data['cantidad_producto'] = cantidad
        await update.message.reply_text("Por favor, proporciona el precio unitario del producto:")
        return PRECIO_UNITARIO
    except ValueError:
        await update.message.reply_text("❌ La cantidad debe ser un número. Intenta de nuevo:")
        return CANTIDAD_PRODUCTO

async def precio_unitario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        precio_unitario = float(update.message.text)
        context.user_data['precio_unitario'] = precio_unitario

        if 'filas_factura' not in context.user_data:
            context.user_data['filas_factura'] = []
        context.user_data['filas_factura'].append({
            'descripcion': context.user_data['descripcion_producto'],
            'cantidad': context.user_data['cantidad_producto'],
            'precio_unitario': context.user_data['precio_unitario']
        })

        await update.message.reply_text("¿Deseas añadir otro producto? (s/n):")
        return OTRO_PRODUCTO
    except ValueError:
        await update.message.reply_text("❌ El precio unitario debe ser un número. Intenta de nuevo:")
        return PRECIO_UNITARIO

async def otro_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    respuesta = update.message.text.strip().lower()
    if respuesta == 's':
        await update.message.reply_text("Por favor, proporciona la descripción del producto:")
        return DESCRIPCION_PRODUCTO
    else:
        await update.message.reply_text("¿Deseas aplicar un descuento? (s/n):")
        return DESCUENTO

async def descuento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    respuesta = update.message.text.strip().lower()
    if respuesta == 's':
        await update.message.reply_text("Por favor, introduce la cantidad de descuento (en euros):")
        return CANTIDAD_DESCUENTO
    else:
        context.user_data['descuento'] = 0
        return await generar_previsualizacion(update, context)

async def cantidad_descuento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        descuento = float(update.message.text)
        context.user_data['descuento'] = descuento
        return await generar_previsualizacion(update, context)
    except ValueError:
        await update.message.reply_text("❌ El descuento debe ser un número. Intenta de nuevo:")
        return CANTIDAD_DESCUENTO

async def confirmar_generar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    respuesta = update.message.text.strip().lower()
    if respuesta == 's':
        await update.message.reply_text("Generando documento...")
        try:
            for fila in context.user_data['filas_factura']:
                fila['precio_total'] = fila['cantidad'] * fila['precio_unitario']

            datos = context.user_data
            tipo_documento = datos['tipo_documento']
            nombre_archivo = generar_factura(datos, f"{datos['cliente_nombre']}_{tipo_documento}.pdf")
            logger.info(f"{tipo_documento.capitalize()} generado: {nombre_archivo}")

            subir_a_google_drive(nombre_archivo, nombre_archivo, tipo_documento)
            await update.message.reply_text(f"✅ {tipo_documento.capitalize()} generado y subido a Google Drive.")

            await update.message.reply_text(f"¿Deseas enviar el {tipo_documento} por correo? (s/n):")
            return CONFIRMAR_ENVIAR
        except Exception as e:
            logger.error(f"Error generando {tipo_documento}: {e}")
            await update.message.reply_text(f"❌ Error al generar el {tipo_documento}. Intenta de nuevo.")
            return ConversationHandler.END
    else:
        await update.message.reply_text("Operación cancelada.")
        return ConversationHandler.END

async def confirmar_enviar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    respuesta = update.message.text.strip().lower()
    if respuesta == 's':
        await update.message.reply_text("Por favor, proporciona el destinatario del correo:")
        return DESTINATARIO_CORREO
    else:
        await update.message.reply_text("Operación completada.")
        return ConversationHandler.END

async def destinatario_correo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['destinatario_correo'] = update.message.text
    try:
        datos = context.user_data
        tipo_documento = datos['tipo_documento']
        nombre_archivo = f"{datos['cliente_nombre']}_{tipo_documento}.pdf"
        destinatario_correo = datos['destinatario_correo']
        asunto = nombre_archivo
        cuerpo = f"Adjunto encontrarás el {tipo_documento} de {datos['cliente_nombre']}."
        enviar_correo(destinatario_correo, asunto, cuerpo, nombre_archivo)
        await update.message.reply_text(f"✅ {tipo_documento.capitalize()} enviado por correo.")
    except Exception as e:
        logger.error(f"Error enviando {tipo_documento}: {e}")
        await update.message.reply_text(f"❌ Error al enviar. Intenta de nuevo.")
        return ConversationHandler.END

    await update.message.reply_text("Operación completada.")
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END

# ======================
# SERVIDOR HTTP KEEPALIVE
# ======================

class KeepaliveHandler(BaseHTTPRequestHandler):
    """Responde a GET y HEAD para que UptimeRobot mantenga el servicio vivo."""
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot de facturas activo')
    
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Silencia logs del servidor HTTP."""
        pass

def iniciar_servidor_http():
    """Inicia servidor HTTP en el puerto que Render asigne."""
    puerto = int(os.getenv('PORT', 8080))
    server = HTTPServer(('0.0.0.0', puerto), KeepaliveHandler)
    logger.info(f"Servidor HTTP escuchando en puerto {puerto}")
    server.serve_forever()

# ======================
# MAIN
# ======================

def main():
    # Iniciar servidor HTTP en un thread separado
    servidor_thread = threading.Thread(target=iniciar_servidor_http, daemon=True)
    servidor_thread.start()
    logger.info("Thread del servidor HTTP iniciado")
    
    # Configurar aplicación Telegram
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ELECCION: [MessageHandler(filters.TEXT & ~filters.COMMAND, eleccion)],
            NUMERO_DOCUMENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, numero_documento)],
            FECHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, fecha)],
            CLIENTE_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cliente_nombre)],
            CLIENTE_DIRECCION: [MessageHandler(filters.TEXT & ~filters.COMMAND, cliente_direccion)],
            CLIENTE_CP_CIUDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, cliente_cp_ciudad)],
            CLIENTE_NIF: [MessageHandler(filters.TEXT & ~filters.COMMAND, cliente_nif)],
            DESCRIPCION_PRODUCTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, descripcion_producto)],
            CANTIDAD_PRODUCTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, cantidad_producto)],
            PRECIO_UNITARIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, precio_unitario)],
            OTRO_PRODUCTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, otro_producto)],
            DESCUENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, descuento)],
            CANTIDAD_DESCUENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, cantidad_descuento)],
            CONFIRMAR_GENERAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_generar)],
            CONFIRMAR_ENVIAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_enviar)],
            DESTINATARIO_CORREO: [MessageHandler(filters.TEXT & ~filters.COMMAND, destinatario_correo)],
        },
        fallbacks=[CommandHandler('cancelar', cancelar)]
    )

    application.add_handler(conv_handler)

    logger.info("Bot iniciando (polling mode)...")
    application.run_polling()

if __name__ == "__main__":
    main()
