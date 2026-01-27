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
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="VELS SmartSeal Pro", page_icon="🛡️", layout="wide")

# --- 2. CSS PARA EL DISEÑO (INTACTO) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap');
    * { font-family: 'Plus Jakarta Sans', sans-serif; }
    .stApp { background-color: #f8fafc; }
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
    .main-title { 
        color: #1e293b; 
        font-size: 2.5rem; 
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

# --- 3. FUNCIONES CORE (INTACTO) ---
def obtener_datos_dte(archivo):
    patron_uuid = r'[A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12}'
    catalogo = {
        "01": "FACTURAS", "03": "COMPROBANTES DE CREDITO FISCAL",
        "05": "NOTAS DE CREDITO", "06": "NOTAS DE DEBITO",
        "07": "COMPROBANTE DE RETENCION", "11": "FACTURA DE EXPORTACION",
        "14": "FACTURA SUJETO EXCLUIDO"
    }
    uuid = None
    tipo_nombre = "OTROS_DOCUMENTOS"
    try:
        if archivo is None: return "ERROR", "OTROS"
        nombre_original = archivo.name.upper()
        archivo.seek(0)
        if nombre_original.endswith(".JSON"):
            data = json.load(archivo)
            uuid = data.get("identificacion", {}).get("codigoGeneracion")
            codigo_tipo = data.get("identificacion", {}).get("tipoDte")
            tipo_nombre = catalogo.get(codigo_tipo, "OTROS_DOCUMENTOS")
        elif nombre_original.endswith(".PDF"):
            reader = PdfReader(archivo)
            texto = "".join([p.extract_text() or "" for p in reader.pages])
            match_uuid = re.search(patron_uuid, texto.upper())
            if match_uuid: uuid = match_uuid.group(0)
            for codigo, nombre in catalogo.items():
                if nombre in texto.upper() or f"TIPO DE DOCUMENTO: {codigo}" in texto.upper():
                    tipo_nombre = nombre
                    break
        if not uuid:
            match_nom = re.search(patron_uuid, nombre_original)
            uuid = match_nom.group(0) if match_nom else nombre_original.split('.')[0]
    except: return "ERROR", "OTROS"
    return str(uuid).upper(), tipo_nombre

# --- 4. BARRA LATERAL (INTACTO) ---
with st.sidebar:
    st.markdown('<p class="sidebar-title">🛡️ VELS <br>SmartSeal</p>', unsafe_allow_html=True)
    st.write("---")
    seleccion = st.radio("MÓDULOS", ["🚀 Añadir Logo", "📂 Archivador DTE", "📊 Libros de IVA", "📬 Auto-Descarga JSON", "⚙️ Ajustes"])
    st.write("---")
    st.caption("Perfil: Vels")

# --- 5. LÓGICA DE MÓDULOS ---

if seleccion == "🚀 Añadir Logo":
    st.markdown('<h1 class="main-title">Añadir Logo</h1>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        pdf_files = st.file_uploader("Subir PDFs", type=["pdf"], accept_multiple_files=True)
    with col2:
        img_file = st.file_uploader("Subir Logo", type=["png", "jpg", "jpeg"])
    if pdf_files and img_file:
        if st.button("EJECUTAR SELLADO"):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for up_pdf in pdf_files:
                    if up_pdf is None: continue
                    try:
                        uuid, _ = obtener_datos_dte(up_pdf)
                        reader = PdfReader(up_pdf)
                        writer = PdfWriter()
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
                        zip_file.writestr(f"{uuid}.pdf", pdf_out.getvalue())
                    except: continue
            st.success("✅ Sellado completo.")
            st.download_button("📥 DESCARGAR ZIP", zip_buffer.getvalue(), "Sellados_VELS.zip")

elif seleccion == "📂 Archivador DTE":
    st.markdown('<h1 class="main-title">Archivador DTE</h1>', unsafe_allow_html=True)
    files = st.file_uploader("Cargar archivos", type=["pdf", "json"], accept_multiple_files=True)
    if files:
        if st.button("ORGANIZAR EN CARPETAS"):
            zip_buffer = io.BytesIO()
            procesados = {}
            for f in files:
                if f is None: continue
                try:
                    uuid, carpeta = obtener_datos_dte(f)
                    if uuid == "ERROR": continue
                    ext = "PDF" if f.name.lower().endswith(".pdf") else "JSON"
                    if uuid not in procesados: procesados[uuid] = {"PDF": None, "JSON": None, "CARPETA": carpeta}
                    f.seek(0)
                    procesados[uuid][ext] = f.read()
                    if ext == "JSON": procesados[uuid]["CARPETA"] = carpeta
                except: continue
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for uuid, data in procesados.items():
                    if data["JSON"]:
                        zip_file.writestr(f"{data['CARPETA']}/{uuid}.json", data["JSON"])
                        if data["PDF"]: zip_file.writestr(f"{data['CARPETA']}/{uuid}.pdf", data["PDF"])
                    elif data["PDF"]:
                        zip_file.writestr(f"SOLO_PDF_SIN_JSON/{uuid}.pdf", data["PDF"])
            st.success("✅ Organización finalizada.")
            st.download_button("📥 DESCARGAR DTE ORGANIZADOS", zip_buffer.getvalue(), "Auditoria_DTE_Organizado.zip")

elif seleccion == "📊 Libros de IVA":
    st.markdown('<h1 class="main-title">Generación de Libros de IVA</h1>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1: arc_comp = st.file_uploader("🛒 Compras", type=["json"], accept_multiple_files=True, key="c")
    with col2: arc_cons = st.file_uploader("👥 Consumidor", type=["json"], accept_multiple_files=True, key="cf")
    with col3: arc_cont = st.file_uploader("🏢 Contribuyente", type=["json"], accept_multiple_files=True, key="ct")
    
    if st.button("GENERAR LIBRO VENTAS CONSUMIDOR"):
        if arc_cons:
            registros = []
            for f in arc_cons:
                if f is None: continue 
                try:
                    f.seek(0)
                    data = json.load(f)
                    ident = data.get("identificacion", {})
                    res = data.get("resumen", {})
                    if ident and ident.get("codigoGeneracion"):
                        registros.append({
                            "Fecha": ident.get("fecEmi"),
                            "UUID": ident.get("codigoGeneracion"),
                            "Exentas": float(res.get("totalExenta", 0.0)),
                            "Gravadas": float(res.get("totalGravada", 0.0)),
                            "Total": float(res.get("totalPagar", 0.0))
                        })
                except: continue
            
            if registros:
                df = pd.DataFrame(registros)
                
                # --- FÓRMULA SOLO PARA GRAVADAS ---
                def crear_formula_excel(serie):
                    return "=" + "+".join(serie.astype(str))

                resumen = df.groupby("Fecha").agg({
                    "UUID": ["first", "last", "count"],
                    "Exentas": "sum",
                    "Gravadas": crear_formula_excel,
                    "Total": "sum"
                }).reset_index()
                
                resumen.columns = ["Fecha", "Desde", "Hasta", "Cant", "Exentas", "Gravadas", "Total"]
                st.dataframe(resumen)
                
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                    resumen.to_excel(writer, index=False, sheet_name='Ventas_CF')
                st.download_button("📥 DESCARGAR EXCEL", out.getvalue(), "Libro_Consumidor.xlsx")

elif seleccion == "📬 Auto-Descarga JSON":
    st.markdown('<h1 class="main-title">Descarga Inteligente DTE</h1>', unsafe_allow_html=True)
    
    # INICIALIZACIÓN VACÍA PARA GITHUB
    if "email_pref" not in st.session_state: st.session_state.email_pref = ""
    if "pass_pref" not in st.session_state: st.session_state.pass_pref = ""

    with st.form("vels_form_mail", clear_on_submit=False):
        col_a, col_b = st.columns(2)
        with col_a:
            email_user = st.text_input("Tu Correo", value=st.session_state.email_pref, key="vels_u") 
            email_pass = st.text_input("Contraseña de Aplicación", value=st.session_state.pass_pref, type="password", key="vels_p")
            recordar = st.checkbox("Recordar en esta sesión", value=True)
            server_choice = st.selectbox("Servidor", ["imap.gmail.com", "outlook.office365.com"], index=0)
        with col_b:
            email_sender = st.text_input("Correo del Remitente", value="facturas@empresa.com", key="vels_s")
            meses_lista = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            col_m, col_y = st.columns(2)
            with col_m: mes_sel = st.selectbox("Mes", meses_lista, index=datetime.now().month - 1)
            with col_y: anio_sel = st.number_input("Año", min_value=2024, max_value=2030, value=datetime.now().year)

        submit_button = st.form_submit_button("PROCESAR Y RENOMBRAR POR UUID")

    if submit_button:
        if recordar:
            st.session_state.email_pref = email_user
            st.session_state.pass_pref = email_pass
        try:
            mes_imap = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][meses_lista.index(mes_sel)]
            date_filter = f"SINCE 01-{mes_imap}-{anio_sel}"
            mail = imaplib.IMAP4_SSL(server_choice)
            mail.login(email_user, email_pass)
            mail.select("inbox")
            status, search_data = mail.search(None, f'(FROM "{email_sender}" {date_filter})')
            mail_ids = search_data[0].split()
            if mail_ids:
                zip_buffer = io.BytesIO()
                encontrados = 0
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for m_id in mail_ids:
                        res, data = mail.fetch(m_id, "(RFC822)")
                        msg = email.message_from_bytes(data[0][1])
                        uuid_correo, json_data, pdf_data = None, None, None
                        for part in msg.walk():
                            if part.get_content_maintype() == 'multipart': continue
                            fname = part.get_filename()
                            if fname and fname.lower().endswith(".json"):
                                try:
                                    raw_json = json.loads(part.get_payload(decode=True))
                                    uuid_correo = raw_json.get("identificacion", {}).get("codigoGeneracion")
                                    json_data = part.get_payload(decode=True)
                                except: pass
                        if uuid_correo:
                            for part in msg.walk():
                                if part.get_filename() and part.get_filename().lower().endswith(".pdf"):
                                    pdf_data = part.get_payload(decode=True)
                                    break
                            if json_data and pdf_data:
                                zf.writestr(f"{uuid_correo.upper()}.json", json_data)
                                zf.writestr(f"{uuid_correo.upper()}.pdf", pdf_data)
                                encontrados += 1
                if encontrados > 0:
                    st.success(f"✅ {encontrados} DTE procesados.")
                    st.download_button("📥 DESCARGAR ZIP", zip_buffer.getvalue(), f"DTE_{mes_sel}.zip")
            mail.logout()
        except Exception as e: st.error(f"Error: {e}")

elif seleccion == "⚙️ Ajustes":
    st.markdown('<h1 class="main-title">Ajustes</h1>', unsafe_allow_html=True)
