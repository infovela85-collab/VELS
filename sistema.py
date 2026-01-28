import streamlit as st
import imaplib
import email
from email.header import decode_header
import os
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="VELS SmartSeal Pro", layout="wide")

# --- ESTILO CSS PERSONALIZADO (MODERNO Y PRIVADO) ---
st.markdown("""
    <style>
    /* Ocultar menús nativos para mayor profesionalismo */
    header[data-testid="stHeader"] { visibility: hidden; height: 0%; }
    footer { visibility: hidden; }
    
    .main { background-color: #0e1117; }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #2e3b4e;
        color: white;
        border: 1px solid #4a5a71;
    }
    .stButton>button:hover {
        background-color: #3d4d66;
        border-color: #00d4ff;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LOGICA DE DESCARGA DE DTE ---
def conectar_y_descargar(correo_user, clave_user, carpeta_destino):
    try:
        # Conexión al servidor (Gmail como ejemplo)
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(correo_user, clave_user)
        imap.select("INBOX")

        # BÚSQUEDA FLEXIBLE: 'ALL' permite procesar correos originales y REENVIADOS
        # Luego filtramos por el contenido de los archivos adjuntos
        status, mensajes = imap.search(None, 'ALL')
        
        if status != "OK":
            st.error("No se pudo realizar la búsqueda en el correo.")
            return

        id_lista = mensajes[0].split()
        descargados = 0

        progreso = st.progress(0)
        status_text = st.empty()

        for i, num in enumerate(reversed(id_lista)):
            status_text.text(f"Analizando correo {i+1} de {len(id_lista)}...")
            res, msg_data = imap.fetch(num, "(RFC822)")
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Revisar cada parte del correo en busca de adjuntos
                    for part in msg.walk():
                        if part.get_content_maintype() == 'multipart':
                            continue
                        if part.get('Content-Disposition') is None:
                            continue

                        filename = part.get_filename()
                        if filename:
                            # Decodificar nombre de archivo si es necesario
                            decode = decode_header(filename)[0]
                            if isinstance(decode[0], bytes):
                                filename = decode[0].decode(decode[1] or 'utf-8')
                            
                            # FILTRO DE ARCHIVOS DTE: Acepta JSON y PDF de cualquier remitente
                            if filename.lower().endswith(('.json', '.pdf')):
                                filepath = os.path.join(carpeta_destino, filename)
                                
                                # Evitar duplicados
                                if not os.path.exists(filepath):
                                    with open(filepath, "wb") as f:
                                        f.write(part.get_payload(decode=True))
                                    descargados += 1
            
            progreso.progress((i + 1) / len(id_lista))
            if i > 50: break # Límite preventivo para no saturar en la primera prueba

        imap.close()
        imap.logout()
        return descargados

    except Exception as e:
        st.error(f"Error de conexión: {str(e)}")
        return None

# --- INTERFAZ DE USUARIO ---
st.title("🛡️ VELS SmartSeal Pro")
st.subheader("Gestión Inteligente de DTE (Documentos Tributarios Electrónicos)")

col1, col2 = st.columns([1, 2])

with col1:
    st.info("Configuración de Acceso")
    # Intentar leer de Secrets, si no, usar inputs manuales
    user_email = st.text_input("Correo Electrónico", value=st.secrets.get("EMAIL", ""))
    user_password = st.text_input("Contraseña de Aplicación", type="password", value=st.secrets.get("PASSWORD", ""))
    
    target_folder = st.text_input("Carpeta de Destino Local", value="C:/DTE_Descargas")

with col2:
    st.success("Panel de Control")
    st.write("El sistema ahora procesará correos **directos y reenviados** buscando archivos .JSON y .PDF.")
    
    if st.button("🚀 Iniciar Descarga Masiva"):
        if user_email and user_password:
            if not os.path.exists(target_folder):
                os.makedirs(target_folder)
            
            total = conectar_y_descargar(user_email, user_password, target_folder)
            
            if total is not None:
                st.balloons()
                st.success(f"Proceso finalizado. Se descargaron {total} archivos nuevos en: {target_folder}")
        else:
            st.warning("Por favor, ingresa tus credenciales.")

# --- FOOTER INFORMATIVO ---
st.markdown("---")
st.caption("Nota: Asegúrate de tener activado el acceso IMAP en tu configuración de correo.")
