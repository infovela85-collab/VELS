import streamlit as st
import imaplib
import email
from email.header import decode_header
import os

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="VELS SmartSeal Pro", layout="wide")

# --- LOGICA DE DESCARGA DE DTE ---
def conectar_y_descargar(correo_user, clave_user, carpeta_destino):
    try:
        # Conexión al servidor (Gmail)
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(correo_user, clave_user)
        imap.select("INBOX")

        # EL CAMBIO CLAVE: Se usa 'ALL' para que el sistema revise cada correo 
        # en tu bandeja, permitiendo encontrar archivos en correos reenviados.
        status, mensajes = imap.search(None, 'ALL')
        
        if status != "OK":
            st.error("No se pudo realizar la búsqueda en el correo.")
            return

        id_lista = mensajes[0].split()
        descargados = 0

        progreso = st.progress(0)
        status_text = st.empty()

        # Procesamos desde el más reciente al más antiguo
        for i, num in enumerate(reversed(id_lista)):
            status_text.text(f"Analizando correo {i+1} de {len(id_lista)}...")
            res, msg_data = imap.fetch(num, "(RFC822)")
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Caminar por las partes del correo para buscar adjuntos
                    for part in msg.walk():
                        if part.get_content_maintype() == 'multipart':
                            continue
                        if part.get('Content-Disposition') is None:
                            continue

                        filename = part.get_filename()
                        if filename:
                            # Decodificar el nombre del archivo
                            decode = decode_header(filename)[0]
                            if isinstance(decode[0], bytes):
                                filename = decode[0].decode(decode[1] or 'utf-8')
                            
                            # Filtro: Solo descargar si es JSON o PDF
                            if filename.lower().endswith(('.json', '.pdf')):
                                filepath = os.path.join(carpeta_destino, filename)
                                
                                # Solo descargar si el archivo no existe localmente
                                if not os.path.exists(filepath):
                                    with open(filepath, "wb") as f:
                                        f.write(part.get_payload(decode=True))
                                    descargados += 1
            
            progreso.progress((i + 1) / len(id_lista))
            
            # Límite de seguridad para no saturar la memoria en la primera ejecución
            if i > 150: 
                break 

        imap.close()
        imap.logout()
        return descargados

    except Exception as e:
        st.error(f"Error de conexión: {str(e)}")
        return None

# --- INTERFAZ DE USUARIO ---
st.title("🛡️ VELS SmartSeal Pro")

# Inputs de usuario
user_email = st.text_input("Correo Electrónico")
user_password = st.text_input("Contraseña de Aplicación", type="password")
target_folder = st.text_input("Carpeta de Destino Local", value="C:/DTE_Descargas")

# Botón de ejecución
if st.button("🚀 Iniciar Descarga"):
    if user_email and user_password:
        # Crear la carpeta si no existe
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        
        total = conectar_y_descargar(user_email, user_password, target_folder)
        
        if total is not None:
            st.success(f"Proceso finalizado. Se descargaron {total} archivos nuevos en {target_folder}.")
    else:
        st.warning("Por favor, ingresa tus credenciales para continuar.")
