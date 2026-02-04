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
    .main-title { font-size: 2.5rem; font-weight: 800; text-align: center; color: inherit; }
    .stTextInput label, .stSelectbox label, .stNumberInput label, .stCheckbox p, .stDateInput label { color: inherit !important; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    .sidebar-title {
        background: linear-gradient(90deg, #60a5fa, #93c5fd);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.2rem !important;
        font-weight: 800;
        text-align: center;
        margin-bottom: 0px;
        letter-spacing: -1px;
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

# --- 3. FUNCIONES CORE ---
def obtener_datos_dte(archivo):
    patron_uuid = r'[A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12}'
    catalogo = {
        "01": "FACTURAS", "03": "COMPROBANTES DE CREDITO FISCAL",
        "05": "NOTAS DE CREDITO", "06": "NOTAS DE DEBITO",
        "07": "COMPROBANTE DE RETENCION", "11": "FACTURA DE EXPORTACION",
        "14": "FACTURA SUJETO EXCLUIDO"
    }
    uuid, tipo_nombre = None, "OTROS_DOCUMENTOS"
    try:
        if archivo is None: return "ERROR", "OTROS"
        nombre_original = getattr(archivo, 'name', "").upper()
        archivo.seek(0)
        if nombre_original.endswith(".JSON"):
            data = json.load(archivo)
            uuid = data.get("identificacion", {}).get("codigoGeneracion")
            codigo_tipo = data.get("identificacion", {}).get("tipoDte")
            tipo_nombre = catalogo.get(codigo_tipo, "OTROS_DOCUMENTOS")
        else:
            reader = PdfReader(archivo)
            texto = "".join([p.extract_text() or "" for p in reader.pages])
            match_uuid = re.search(patron_uuid, texto.upper())
            if match_uuid: 
                uuid = match_uuid.group(0)
                for codigo, nombre in catalogo.items():
                    if nombre in texto.upper() or f"TIPO DE DOCUMENTO: {codigo}" in texto.upper():
                        tipo_nombre = nombre
                        break
        if not uuid and nombre_original:
            match_nom = re.search(patron_uuid, nombre_original)
            uuid = match_nom.group(0) if match_nom else None
    except: return None, "OTROS"
    return (str(uuid).upper(), tipo_nombre) if uuid else (None, None)

def guardar_local(u, p):
    js = f"<script>localStorage.setItem('vels_u', '{u}'); localStorage.setItem('vels_p', '{p}');</script>"
    st.components.v1.html(js, height=0)

# --- 4. BARRA LATERAL ---
with st.sidebar:
    st.markdown('<p class="sidebar-title">🛡️ VELS <br>SmartSeal</p>', unsafe_allow_html=True)
    st.write("---")
    seleccion = st.radio("MÓDULOS", ["🚀 Añadir Logo", "📂 Archivador DTE", "📊 Libros de IVA", "📬 Auto-Descarga JSON", "⚙️ Ajustes"])
    st.write("---")
    st.caption("Perfil: Vels")

# --- 5. LÓGICA DE MÓDULOS ---
if "email_pref" not in st.session_state: st.session_state.email_pref = ""
if "pass_pref" not in st.session_state: st.session_state.pass_pref = ""

if seleccion == "🚀 Añadir Logo":
    st.markdown('<h1 class="main-title">Añadir Logo</h1>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1: pdf_files = st.file_uploader("Subir PDFs", type=["pdf"], accept_multiple_files=True)
    with col2: img_file = st.file_uploader("Subir Logo", type=["png", "jpg", "jpeg"])
    if pdf_files and img_file:
        if st.button("EJECUTAR SELLADO"):
            zip_buffer = io.BytesIO()
            progreso = st.progress(0)
            for idx, up_pdf in enumerate(pdf_files):
                try:
                    uuid, _ = obtener_datos_dte(up_pdf)
                    if not uuid: uuid = up_pdf.name.split('.')[0]
                    reader, writer = PdfReader(up_pdf), PdfWriter()
                    p0 = reader.pages[0]
                    w, h = float(p0.mediabox.width), float(p0.mediabox.height)
                    packet = io.BytesIO()
                    can = canvas.Canvas(packet, pagesize=(w, h))
                    can.drawImage(ImageReader(img_file), 45, h - 85, width=110, height=55, preserveAspectRatio=True, mask='auto')
                    can.save()
                    packet.seek(0)
                    stamp = PdfReader(packet).pages[0]
                    for p in reader.pages:
                        p.merge_page(stamp)
                        writer.add_page(p)
                    pdf_out = io.BytesIO()
                    writer.write(pdf_out)
                    with zipfile.ZipFile(zip_buffer, "a") as zf: zf.writestr(f"{uuid}.pdf", pdf_out.getvalue())
                except: continue
                progreso.progress((idx + 1) / len(pdf_files))
            st.success("✅ Sellado completo.")
            st.download_button("📥 DESCARGAR ZIP", zip_buffer.getvalue(), "Sellados_VELS.zip")

elif seleccion == "📂 Archivador DTE":
    st.markdown('<h1 class="main-title">Archivador DTE</h1>', unsafe_allow_html=True)
    files = st.file_uploader("Cargar archivos", type=["pdf", "json"], accept_multiple_files=True)
    if files:
        if st.button("ORGANIZAR EN CARPETAS"):
            zip_buffer, procesados, progreso_arc = io.BytesIO(), {}, st.progress
