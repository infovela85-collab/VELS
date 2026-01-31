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
            zip_buffer, procesados, progreso_arc = io.BytesIO(), {}, st.progress(0)
            for i, f in enumerate(files):
                try:
                    uuid, carpeta = obtener_datos_dte(f)
                    if not uuid: continue
                    ext = "PDF" if f.name.lower().endswith(".pdf") else "JSON"
                    if uuid not in procesados: procesados[uuid] = {"PDF": None, "JSON": None, "CARPETA": carpeta}
                    f.seek(0)
                    procesados[uuid][ext] = f.read()
                except: continue
                progreso_arc.progress((i + 1) / len(files))
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for uuid, data in procesados.items():
                    if data["JSON"]:
                        zf.writestr(f"{data['CARPETA']}/{uuid}.json", data["JSON"])
                        if data["PDF"]: zf.writestr(f"{data['CARPETA']}/{uuid}.pdf", data["PDF"])
                    elif data["PDF"]: zf.writestr(f"SOLO_PDF_DTE/{uuid}.pdf", data["PDF"])
            st.success("✅ Organización finalizada.")
            st.download_button("📥 DESCARGAR DTE ORGANIZADOS", zip_buffer.getvalue(), "Auditoria_Organizada.zip")

elif seleccion == "📊 Libros de IVA":
    st.markdown('<h1 class="main-title">Generación de Libros de IVA</h1>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1: arc_comp = st.file_uploader("🛒 Compras", type=["json"], accept_multiple_files=True, key="c")
    with col2: arc_cons = st.file_uploader("👥 Consumidor", type=["json"], accept_multiple_files=True, key="cf")
    with col3: arc_cont = st.file_uploader("🏢 Contribuyente", type=["json"], accept_multiple_files=True, key="ct")
    if st.button("GENERAR LIBRO VENTAS"):
        if arc_cons:
            registros = []
            for f in arc_cons:
                try:
                    f.seek(0)
                    data = json.load(f)
                    ident, res = data.get("identificacion", {}), data.get("resumen", {})
                    if ident.get("codigoGeneracion"):
                        registros.append({"Fecha": ident.get("fecEmi"), "UUID": ident.get("codigoGeneracion"), "Exentas": float(res.get("totalExenta", 0.0)), "Gravadas": float(res.get("totalGravada", 0.0)), "Total": float(res.get("totalPagar", 0.0))})
                except: continue
            if registros:
                df = pd.DataFrame(registros)
                st.dataframe(df)
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as writer: df.to_excel(writer, index=False)
                st.download_button("📥 DESCARGAR EXCEL", out.getvalue(), "Libro_IVA.xlsx")

elif seleccion == "📬 Auto-Descarga JSON":
    st.markdown('<h1 class="main-title">Descarga Inteligente DTE</h1>', unsafe_allow_html=True)
    with st.form("vels_form_mail", clear_on_submit=False):
        col_a, col_b = st.columns(2)
        with col_a:
            email_user = st.text_input("Tu Correo", value=st.session_state.email_pref) 
            email_pass = st.text_input("Contraseña de Aplicación", value=st.session_state.pass_pref, type="password")
            recordar = st.checkbox("Recordar en este navegador", value=True)
            server_choice = st.selectbox("Servidor", ["imap.gmail.com", "outlook.office365.com"])
        with col_b:
            email_sender = st.text_input("Correo del Remitente", value="facturas@empresa.com")
            col_f1, col_f2 = st.columns(2)
            with col_f1: fecha_desde = st.date_input("Desde", value=date(date.today().year, date.today().month, 1), format="DD/MM/YYYY")
            with col_f2: fecha_hasta = st.date_input("Hasta", value=date.today(), format="DD/MM/YYYY")
        submit_button = st.form_submit_button("PROCESAR DTE")

    if submit_button:
        st.session_state.email_pref, st.session_state.pass_pref = email_user, email_pass
        if recordar: guardar_local(email_user, email_pass)
        try:
            imap_date = fecha_desde.strftime("%d-%b-%Y")
            mail = imaplib.IMAP4_SSL(server_choice)
            mail.login(email_user, email_pass)
            mail.select("inbox")
            
            # Búsqueda flexible por texto y fecha
            status, search_data = mail.search(None, f'(TEXT "{email_sender}" SINCE {imap_date})')
            
            mail_ids = search_data[0].split()
            if mail_ids:
                zip_buffer, encontrados, progreso_mail = io.BytesIO(), 0, st.progress(0)
                uuids_procesados = set()
                with zipfile.ZipFile(zip_buffer, "w") as zf_final:
                    for idx, m_id in enumerate(mail_ids):
                        res, data = mail.fetch(m_id, "(RFC822)")
                        msg = email.message_from_bytes(data[0][1])
                        
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            fn = part.get_filename()
                            
                            if not fn:
                                if content_type == "application/json": fn = "temp.json"
                                elif content_type == "application/pdf": fn = "temp.pdf"
                                elif content_type == "application/zip": fn = "temp.zip"
                                else: continue
                            
                            fn = fn.lower()
                            payload = part.get_payload(decode=True)
                            if not payload: continue

                            # --- NUEVA LÓGICA: PROCESAR ARCHIVOS ZIP ---
                            if fn.endswith(".zip"):
                                try:
                                    with zipfile.ZipFile(io.BytesIO(payload)) as z_in:
                                        for z_name in z_in.namelist():
                                            z_payload = z_in.read(z_name)
                                            u_tmp = None
                                            if z_name.lower().endswith(".json"):
                                                try:
                                                    raw = json.loads(z_payload)
                                                    u_tmp = raw.get("identificacion", {}).get("codigoGeneracion")
                                                except: pass
                                            elif z_name.lower().endswith(".pdf"):
                                                u_tmp, _ = obtener_datos_dte(io.BytesIO(z_payload))
                                            
                                            if u_tmp:
                                                u_tmp = u_tmp.upper()
                                                if u_tmp not in uuids_procesados:
                                                    ext_zip = "json" if z_name.lower().endswith(".json") else "pdf"
                                                    zf_final.writestr(f"{u_tmp}.{ext_zip}", z_payload)
                                                    uuids_procesados.add(u_tmp)
                                                    encontrados += 1
                                except: pass

                            # --- LÓGICA EXISTENTE: PROCESAR JSON Y PDF DIRECTOS ---
                            elif fn.endswith(".json"):
                                try:
                                    raw = json.loads(payload)
                                    u_tmp = raw.get("identificacion", {}).get("codigoGeneracion")
                                    if u_tmp:
                                        u_tmp = u_tmp.upper()
                                        if u_tmp not in uuids_procesados:
                                            zf_final.writestr(f"{u_tmp}.json", payload)
                                            uuids_procesados.add(u_tmp)
                                            encontrados += 1
                                except: pass
                            elif fn.endswith(".pdf"):
                                try:
                                    u_tmp, _ = obtener_datos_dte(io.BytesIO(payload))
                                    if u_tmp:
                                        u_tmp = u_tmp.upper()
                                        if u_tmp not in uuids_procesados:
                                            zf_final.writestr(f"{u_tmp}.pdf", payload)
                                            uuids_procesados.add(u_tmp)
                                            encontrados += 1
                                except: pass
                        
                        progreso_mail.progress((idx + 1) / len(mail_ids))
                
                if encontrados > 0:
                    st.success(f"✅ {encontrados} DTE procesados (incluyendo archivos dentro de ZIP).")
                    st.download_button("📥 DESCARGAR ZIP", zip_buffer.getvalue(), f"DTE_{fecha_desde.strftime('%d%m%Y')}_al_{fecha_hasta.strftime('%d%m%Y')}.zip")
                else: st.warning("No se encontraron DTE nuevos o válidos.")
            mail.logout()
        except Exception as e: st.error(f"Error: {e}")

elif seleccion == "⚙️ Ajustes":
    st.markdown('<h1 class="main-title">Ajustes</h1>', unsafe_allow_html=True)
    st.info("Formato de fecha regional y control de duplicidad activo.")

