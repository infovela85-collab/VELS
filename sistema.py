import streamlit as st
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io
import zipfile
import re
import json
import pandas as pd
import imaplib
import email
from email.header import decode_header
from datetime import datetime, date

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="VELS SmartSeal Pro", page_icon="🛡️", layout="wide")

# --- 2. CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap');
    * { font-family: 'Plus Jakarta Sans', sans-serif; }
    .main-title { font-size: 2.5rem; font-weight: 800; text-align: center; color: inherit; }
    .sidebar-title {
        background: linear-gradient(90deg, #60a5fa, #93c5fd);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.2rem !important;
        font-weight: 800;
        text-align: center;
    }
    .stButton>button {
        background-color: #1e293b !important;
        color: white !important;
        border-radius: 8px;
        font-weight: bold;
        width: 100%;
        height: 3.5em;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCIONES CORE MEJORADAS ---
def procesar_contenido_dte(contenido, nombre_sugerido=""):
    """
    Entra al archivo, verifica si es JSON o PDF y extrae el UUID.
    Esta es la 'llave maestra' que pediste.
    """
    patron_uuid = r'[A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12}'
    uuid = None
    
    # 1. INTENTAR COMO JSON (No importa la extensión, probamos el contenido)
    try:
        data = json.loads(contenido.decode('utf-8', errors='ignore'))
        # Si tiene esta estructura, es un DTE de El Salvador
        uuid = data.get("identificacion", {}).get("codigoGeneracion")
        if uuid: return str(uuid).upper(), "json"
    except:
        pass

    # 2. INTENTAR COMO PDF
    try:
        pdf_file = io.BytesIO(contenido)
        reader = PdfReader(pdf_file)
        texto = "".join([p.extract_text() or "" for p in reader.pages])
        match = re.search(patron_uuid, texto.upper())
        if match: return match.group(0), "pdf"
    except:
        pass

    # 3. ÚLTIMO RECURSO: NOMBRE DEL ARCHIVO
    match_nom = re.search(patron_uuid, nombre_sugerido.upper())
    if match_nom: return match_nom.group(0), "archivo"

    return None, None

def guardar_local(u, p):
    js = f"<script>localStorage.setItem('vels_u', '{u}'); localStorage.setItem('vels_p', '{p}');</script>"
    st.components.v1.html(js, height=0)

# --- 4. BARRA LATERAL ---
with st.sidebar:
    st.markdown('<p class="sidebar-title">🛡️ VELS <br>SmartSeal</p>', unsafe_allow_html=True)
    st.write("---")
    seleccion = st.radio("MÓDULOS", ["🚀 Añadir Logo", "📂 Archivador DTE", "📊 Libros de IVA", "📬 Auto-Descarga JSON", "⚙️ Ajustes"])
    st.caption("Perfil: Vels")

# --- 5. LÓGICA DE MÓDULOS ---
if "email_pref" not in st.session_state: st.session_state.email_pref = ""
if "pass_pref" not in st.session_state: st.session_state.pass_pref = ""

if seleccion == "📬 Auto-Descarga JSON":
    st.markdown('<h1 class="main-title">Descarga Inteligente DTE</h1>', unsafe_allow_html=True)
    with st.form("vels_form_mail"):
        col_a, col_b = st.columns(2)
        with col_a:
            email_user = st.text_input("Tu Correo", value=st.session_state.email_pref) 
            email_pass = st.text_input("Contraseña de Aplicación", value=st.session_state.pass_pref, type="password")
            server_choice = st.selectbox("Servidor", ["imap.gmail.com", "outlook.office365.com"])
        with col_b:
            buscar_texto = st.text_input("Correo Remitente / Asunto", value="")
            col_f = st.columns(2)
            fecha_desde = col_f[0].date_input("Desde", value=date(date.today().year, date.today().month, 1))
            fecha_hasta = col_f[1].date_input("Hasta", value=date.today())
        submit = st.form_submit_button("ESCANEAR CORREOS")

    if submit:
        st.session_state.email_pref, st.session_state.pass_pref = email_user, email_pass
        try:
            mail = imaplib.IMAP4_SSL(server_choice)
            mail.login(email_user, email_pass)
            mail.select("inbox")
            
            # Buscamos correos
            date_str = fecha_desde.strftime("%d-%b-%Y")
            status, search_data = mail.search(None, f'(OR SUBJECT "{buscar_texto}" FROM "{buscar_texto}" SINCE {date_str})')
            ids = search_data[0].split()
            
            if not ids:
                st.warning("No se encontraron correos con esos criterios.")
            else:
                zip_buffer = io.BytesIO()
                encontrados = 0
                progreso = st.progress(0)
                
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for i, m_id in enumerate(ids):
                        _, data = mail.fetch(m_id, "(RFC822)")
                        msg = email.message_from_bytes(data[0][1])
                        
                        for part in msg.walk():
                            if part.get_content_maintype() == 'multipart': continue
                            
                            payload = part.get_payload(decode=True)
                            if not payload: continue
                            
                            nombre_adjunto = part.get_filename() or ""
                            
                            # ANALIZAR CONTENIDO (No importa la extensión)
                            uuid, tipo_detectado = procesar_contenido_dte(payload, nombre_adjunto)
                            
                            if uuid:
                                # Si detectamos que es JSON o PDF por contenido, lo guardamos
                                ext = "json" if tipo_detectado == "json" else "pdf"
                                zf.writestr(f"{uuid}.{ext}", payload)
                                encontrados += 1
                        
                        progreso.progress((i + 1) / len(ids))

                if encontrados > 0:
                    st.success(f"✅ ¡Éxito! Se extrajeron {encontrados} archivos DTE reales.")
                    st.download_button("📥 DESCARGAR ARCHIVOS DETECTADOS", zip_buffer.getvalue(), "DTE_Scanner_Result.zip")
                else:
                    st.error("Se encontraron correos, pero ninguno contenía un JSON o PDF con formato DTE válido.")
            mail.logout()
        except Exception as e:
            st.error(f"Error de conexión: {e}")

# (Resto de módulos omitidos por espacio, pero mantén tu lógica de Libros de IVA y Logo igual)
