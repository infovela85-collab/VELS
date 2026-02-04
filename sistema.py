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

# --- 2. CSS PARA EL DISEÑO ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap');
* { font-family: 'Plus Jakarta Sans', sans-serif; }
.main-title { font-size: 2.5rem; font-weight: 800; text-align: center; }
[data-testid="stSidebar"] { background-color: #1e293b !important; }
[data-testid="stSidebar"] * { color: #ffffff !important; }
.sidebar-title {
    font-size: 2.2rem;
    font-weight: 800;
    text-align: center;
}
.stButton>button {
    background-color: #1e293b !important;
    color: white !important;
    width: 100%;
}
</style>
""", unsafe_allow_html=True)

# --- 3. FUNCIONES CORE ---
def obtener_datos_dte(archivo):
    patron_uuid = r'[A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12}'
    catalogo = {
        "01": "FACTURAS",
        "03": "COMPROBANTES DE CREDITO FISCAL",
        "05": "NOTAS DE CREDITO",
        "06": "NOTAS DE DEBITO",
        "07": "COMPROBANTE DE RETENCION",
        "11": "FACTURA DE EXPORTACION",
        "14": "FACTURA SUJETO EXCLUIDO"
    }
    uuid, tipo_nombre = None, "OTROS_DOCUMENTOS"
    try:
        archivo.seek(0)
        nombre = getattr(archivo, 'name', '').upper()

        if nombre.endswith(".JSON"):
            data = json.load(archivo)
            uuid = data.get("identificacion", {}).get("codigoGeneracion")
            tipo_nombre = catalogo.get(data.get("identificacion", {}).get("tipoDte"), "OTROS")
        else:
            reader = PdfReader(archivo)
            texto = "".join([p.extract_text() or "" for p in reader.pages])
            m = re.search(patron_uuid, texto.upper())
            if m:
                uuid = m.group(0)
    except:
        pass

    return (str(uuid).upper(), tipo_nombre) if uuid else (None, None)

def guardar_local(u, p):
    js = f"<script>localStorage.setItem('vels_u','{u}');localStorage.setItem('vels_p','{p}');</script>"
    st.components.v1.html(js, height=0)

# --- 4. SIDEBAR ---
with st.sidebar:
    st.markdown('<p class="sidebar-title">🛡️ VELS<br>SmartSeal</p>', unsafe_allow_html=True)
    seleccion = st.radio("MÓDULOS", [
        "🚀 Añadir Logo",
        "📂 Archivador DTE",
        "📊 Libros de IVA",
        "📬 Auto-Descarga JSON",
        "⚙️ Ajustes"
    ])

# --- 5. MÓDULOS ---
if "email_pref" not in st.session_state: st.session_state.email_pref = ""
if "pass_pref" not in st.session_state: st.session_state.pass_pref = ""

# ================== AUTO DESCARGA JSON ==================
if seleccion == "📬 Auto-Descarga JSON":
    st.markdown('<h1 class="main-title">Descarga Inteligente DTE</h1>', unsafe_allow_html=True)

    with st.form("mail_form"):
        col1, col2 = st.columns(2)
        with col1:
            ema
