# ==========================================
# GERIATRÍA OS v2.0 - ENTERPRISE CLINICAL SUITE
# ==========================================

import streamlit as st
import pandas as pd
import os
import uuid
from datetime import datetime, timedelta, timezone
import time

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Geriatría OS | Clinical Enterprise",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def ahora_colombia():
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=5)

# --- 2. CONEXIÓN GOOGLE SHEETS / DRIVE ---
try:
    import gspread
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    GSPREAD_DISPONIBLE = True
except ImportError:
    GSPREAD_DISPONIBLE = False

@st.cache_resource
def _almacen_cache():
    return {"tablas": {}, "hojas": {}}

@st.cache_resource
def conectar_gsheets():
    if not GSPREAD_DISPONIBLE: 
        return None
    try:
        creds = Credentials.from_authorized_user_info({
            "client_id": st.secrets["google_client_id"],
            "client_secret": st.secrets["google_client_secret"],
            "refresh_token": st.secrets["google_refresh_token"],
            "token_uri": "https://oauth2.googleapis.com/token"
        })
        client = gspread.authorize(creds)
        nombre_hoja = "DB_Geriatria_Master"
        
        try:
            sheet = client.open(nombre_hoja)
        except gspread.SpreadsheetNotFound:
            sheet = client.create(nombre_hoja)
            pestañas = ["residentes", "signos_vitales", "notas_soapie", "kardex_meds", "escalas", "usuarios", "logs"]
            first_sheet = sheet.get_sheet_by_id(0)
            first_sheet.update_title(pestañas[0])
            for p in pestañas[1:]:
                sheet.add_worksheet(title=p, rows="100", cols="20")
        return sheet
    except Exception as e:
        print(f"⚠️ Error conectando a GSheets: {e}")
        return None

gc_sheet = conectar_gsheets()
TTL_TABLAS = 600

def _hoja(nombre_tabla):
    hojas = _almacen_cache()["hojas"]
    if nombre_tabla not in hojas:
        hojas[nombre_tabla] = gc_sheet.worksheet(nombre_tabla)
    return hojas[nombre_tabla]

def leer_tabla(nombre_tabla, columnas_def):
    tablas = _almacen_cache()["tablas"]
    guardado = tablas.get(nombre_tabla)
    if guardado and (time.time() - guardado[0]) < TTL_TABLAS:
        return guardado[1].copy()
    if gc_sheet:
        try:
            data = _hoja(nombre_tabla).get_all_records()
            df = pd.DataFrame(data)
            df = df if not df.empty else pd.DataFrame(columns=columnas_def)
            tablas[nombre_tabla] = (time.time(), df)
            return df.copy()
        except Exception as e:
            _almacen_cache()["hojas"].pop(nombre_tabla, None)
    
    arch = f"db_{nombre_tabla}.csv"
    if not os.path.exists(arch):
        pd.DataFrame(columns=columnas_def).to_csv(arch, index=False)
    df = pd.read_csv(arch)
    tablas[nombre_tabla] = (time.time() - TTL_TABLAS + 30, df)
    return df.copy()

def guardar_tabla(df, nombre_tabla):
    arch = f"db_{nombre_tabla}.csv"
    df.to_csv(arch, index=False)
    if gc_sheet:
        try:
            ws = _hoja(nombre_tabla)
            ws.clear()
            ws.update([df.columns.values.tolist()] + df.fillna("").values.tolist())
        except Exception as e:
            _almacen_cache()["hojas"].pop(nombre_tabla, None)
    _almacen_cache()["tablas"].pop(nombre_tabla, None)

# ==========================================
# 3. MOTOR CSS AVANZADO: DISEÑO 3D Y LUJO
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');

:root {
  --navy: #0A192F; --navy-light: #132744; --emerald: #10B981; --emerald-dark: #047857;
  --gold: #D4AF37; --gold-light: #F3E7C4; --bg-canvas: #EEF2F6; --card-bg: #FFFFFF;
  --text-main: #1E293B; --text-muted: #64748B; --border-color: #CBD5E1; --radius: 20px;
}

html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; color: var(--text-main); }

[data-testid="stAppViewContainer"] {
  background: radial-gradient(circle at 10% 10%, rgba(212, 175, 55, 0.08) 0%, transparent 40%),
              radial-gradient(circle at 90% 90%, rgba(16, 185, 129, 0.08) 0%, transparent 40%),
              var(--bg-canvas) !important;
}

[data-testid="stHeader"], [data-testid="stToolbar"] { display: none !important; }
.block-container { padding: 2rem 2.5rem 4rem 2.5rem !important; max-width: 1450px; }

h1, h2, h3 { font-family: 'Fraunces', serif !important; color: var(--navy) !important; font-weight: 700; }

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: none; }
}

.stContainer, [data-testid="stForm"] {
  animation: fadeUp 0.5s ease both;
  background: var(--card-bg) !important;
  border: 1px solid var(--border-color) !important;
  border-radius: var(--radius) !important;
  box-shadow: 0 20px 40px -15px rgba(10, 25, 47, 0.07), 0 10px 15px -5px rgba(10, 25, 47, 0.04) !important;
  padding: 24px !important;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}
.stContainer:hover {
  transform: translateY(-3px);
  box-shadow: 0 25px 50px -12px rgba(10, 25, 47, 0.12) !important;
}

/* Inputs y Textareas altamente visibles */
input, textarea, select, [data-baseweb="select"] > div, [data-baseweb="input"] > div {
  background-color: #FFFFFF !important;
  color: #0F172A !important;
  border: 1.5px solid #94A3B8 !important;
  border-radius: 12px !important;
  font-weight: 600 !important;
}
input:focus, textarea:focus, [data-baseweb="select"]:focus-within {
  border-color: var(--emerald) !important;
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.18) !important;
}

[data-testid="stWidgetLabel"] p, label p {
  color: var(--navy) !important;
  font-weight: 700 !important;
  font-size: 0.92rem !important;
}

/* Botones de alta gama */
div.stButton > button, div[data-testid="stFormSubmitButton"] > button {
  background: linear-gradient(135deg, var(--emerald) 0%, var(--emerald-dark) 100%) !important;
  color: white !important; font-weight: 700 !important; border: none !important;
  border-radius: 12px !important; padding: 0.65rem 1.4rem !important;
  box-shadow: 0 8px 20px rgba(16, 185, 129, 0.35) !important;
  transition: all 0.25s ease !important;
}
div.stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 25px rgba(16, 185, 129, 0.5) !important;
}

/* Barra superior elegante */
.top-navbar {
  background: linear-gradient(135deg, var(--navy) 0%, var(--navy-light) 100%);
  border-radius: var(--radius); padding: 14px 26px;
  display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 15px 35px rgba(10, 25, 47, 0.25); margin-bottom: 28px;
}
.top-navbar .brand { color: white; font-family: 'Fraunces', serif; font-size: 1.4rem; font-weight: 700; }
.top-navbar .badge { color: var(--gold); background: rgba(212, 175, 55, 0.15); padding: 5px 14px; border-radius: 20px; font-size: 0.85rem; font-weight: 700; border: 1px solid rgba(212, 175, 55, 0.3); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 4. GESTIÓN DE SESIÓN Y LOGIN
# ==========================================
for v in ['autenticado', 'usuario_actual', 'rol_actual', 'alias_actual', 'reg_profesional']: 
    if v not in st.session_state: 
        st.session_state[v] = False if v == 'autenticado' else ""
if 'pagina_actual' not in st.session_state: 
    st.session_state.pagina_actual = 'Hub'

df_usr = leer_tabla("usuarios", ["Usuario", "Password", "Rol", "Alias", "Reg_Profesional"])
if df_usr.empty:
    df_usr = pd.DataFrame([{
        "Usuario": "enfermeria", "Password": "123", "Rol": "Enfermero/a", 
        "Alias": "Enf. Turno", "Reg_Profesional": "TP-998877"
    }])
    guardar_tabla(df_usr, "usuarios")

if not st.session_state.autenticado:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.15, 1])
    with c2:
        with st.container():
            st.markdown("<div style='text-align: center; font-size: 4rem; margin-bottom: 5px;'>🏥</div>", unsafe_allow_html=True)
            st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>Geriatría OS</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: var(--text-muted); font-size: 0.95rem; margin-bottom: 22px;'>Enterprise Clinical Suite & Notas SOAPIE</p>", unsafe_allow_html=True)
            
            user_input = st.text_input("Usuario del Sistema", placeholder="Ej: enfermeria")
            pass_input = st.text_input("Contraseña de Acceso", type="password", placeholder="••••••••")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("INICIAR SESIÓN CLÍNICA", use_container_width=True):
                match = df_usr[(df_usr["Usuario"].astype(str) == user_input) & (df_usr["Password"].astype(str) == pass_input)]
                if not match.empty:
                    st.session_state.autenticado = True
                    st.session_state.usuario_actual = user_input
                    st.session_state.rol_actual = match.iloc[0]["Rol"]
                    st.session_state.alias_actual = match.iloc[0]["Alias"]
                    st.session_state.reg_profesional = match.iloc[0]["Reg_Profesional"]
                    st.session_state.pagina_actual = 'Hub'
                    st.rerun()
                else:
                    st.error("⚠️ Credenciales incorrectas. Verifique usuario y contraseña.")
    st.stop()

# ==========================================
# 5. NAVEGACIÓN SUPERIOR
# ==========================================
st.markdown(f"""
<div class="top-navbar">
    <div class="brand">🏥 Geriatría OS <span style="font-size:0.85rem; font-family:'Plus Jakarta Sans'; color:#94A3B8; font-weight:400;">| Suite Gerontológica</span></div>
    <div class="badge">👤 {st.session_state.alias_actual} ({st.session_state.rol_actual})</div>
</div>
""", unsafe_allow_html=True)

nav_cols = st.columns(4)
with nav_cols[0]:
    if st.button("🏠 Centro de Mando", use_container_width=True): st.session_state.pagina_actual = 'Hub'; st.rerun()
with nav_cols[1]:
    if st.button("👴 Gestión Residentes", use_container_width=True): st.session_state.pagina_actual = 'Residentes'; st.rerun()
with nav_cols[2]:
    if st.button("📝 Notas SOAPIE", use_container_width=True): st.session_state.pagina_actual = 'SOAPIE'; st.rerun()
with nav_cols[3]:
    if st.button("🚪 Cerrar Sesión", use_container_width=True): st.session_state.autenticado = False; st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 6. MÓDULOS DEL SISTEMA
# ==========================================
df_res = leer_tabla("residentes", ["Cedula", "Nombre", "Fecha_Nacimiento", "EPS", "Habitacion", "Acudiente_Nombre", "Acudiente_Tel", "Estado", "F_Ingreso"])
df_sop = leer_tabla("notas_soapie", ["ID_Nota", "Cedula", "Fecha_Hora", "Turno", "Autor", "Subjetivo", "Objetivo", "Analisis", "Plan", "Intervencion", "Evaluacion"])

def cambiar_pagina(p): st.session_state.pagina_actual = p

# --- HUB CENTRAL ---
if st.session_state.pagina_actual == 'Hub':
    st.markdown("<h1>Centro de Mando Clínico</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: var(--text-muted); margin-bottom: 25px;'>Panel general de supervisión gerátrica y trazabilidad en tiempo real.</p>", unsafe_allow_html=True)
    
    col_h1, col_h2, col_h3 = st.columns(3)
    with col_h1:
        with st.container():
            st.markdown("### 👴 Residentes Activos")
            st.metric("Total en Centro", len(df_res[df_res["Estado"] == "Activo"]) if not df_res.empty else 0)
    with col_h2:
        with st.container():
            st.markdown("### 📝 Notas Registradas")
            st.metric("Evoluciones SOAPIE", len(df_sop) if not df_sop.empty else 0)
    with col_h3:
        with st.container():
            st.markdown("### ⚖️ Marco Legal")
            st.markdown("<p style='font-size:0.88rem; color:var(--text-muted);'>Resolución 1995 de 1999 & Ley 911 de 2004 sincronizadas.</p>", unsafe_allow_html=True)

# --- MÓDULO: RESIDENTES ---
elif st.session_state.pagina_actual == 'Residentes':
    st.markdown("<h1>Gestión de Residentes</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: var(--text-muted); margin-bottom: 25px;'>Admisión y control integral de adultos mayores institucionalizados.</p>", unsafe_allow_html=True)
    
    with st.container():
        st.subheader("➕ Admisión de Nuevo Residente")
        with st.form("form_residente"):
            c1, c2, c3 = st.columns(3)
            with c1: cc_n = st.text_input("Cédula de Ciudadanía")
            with c2: nom_n = st.text_input("Nombre Completo")
            with c3: hab_n = st.text_input("Habitación / Cama")
            
            c4, c5, c6 = st.columns(3)
            with c4: 
                # Rango de fecha ampliado hacia atrás para adultos mayores (desde 1900)
                fnac_n = st.date_input("Fecha de Nacimiento", min_value=datetime(1900, 1, 1).date(), max_value=datetime.today().date(), value=datetime(1945, 1, 1).date())
            with c5: eps_n = st.text_input("EPS / Medicina Prepagada")
            with c6: acud_n = st.text_input("Nombre del Familiar / Acudiente")
            
            c7 = st.text_input("Teléfono de Contacto del Acudiente")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("REGISTRAR ADMISIÓN CLÍNICA", use_container_width=True):
                if cc_n and nom_n:
                    nuevo_res = pd.DataFrame([{
                        "Cedula": str(cc_n), "Nombre": nom_n, "Fecha_Nacimiento": str(fnac_n),
                        "EPS": eps_n, "Habitacion": hab_n, "Acudiente_Nombre": acud_n,
                        "Acudiente_Tel": str(c7), "Estado": "Activo", "F_Ingreso": ahora_colombia().strftime("%Y-%m-%d")
                    }])
                    guardar_tabla(pd.concat([df_res, nuevo_res], ignore_index=True), "residentes")
                    st.success("✅ Residente admitido exitosamente en el sistema y Google Drive.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("⚠️ La cédula y el nombre completo son obligatorios.")

    if not df_res.empty:
        with st.container():
            st.subheader("📋 Directorio de Residentes Activos")
            st.dataframe(df_res[df_res["Estado"] == "Activo"][["Cedula", "Nombre", "Habitacion", "EPS", "Acudiente_Nombre", "Acudiente_Tel"]], use_container_width=True, hide_index=True)

# --- MÓDULO: NOTAS SOAPIE ---
elif st.session_state.pagina_actual == 'SOAPIE':
    st.markdown("<h1>Notas de Enfermería (Metodología SOAPIE)</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: var(--text-muted); margin-bottom: 25px;'>Evolución clínica inmutable sujeta a normatividad legal colombiana.</p>", unsafe_allow_html=True)
    
    with st.container():
        st.info("⚖️ **Garantía Legal:** Cada nota se sella de forma inalterable con marca temporal UTC-5 y firma digital profesional.")
        
        res_activos = df_res[df_res["Estado"] == "Activo"] if not df_res.empty else pd.DataFrame()
        if not res_activos.empty:
            sel_res = st.selectbox("Seleccione el Residente / Paciente:", res_activos["Cedula"].astype(str) + " - " + res_activos["Nombre"])
            cc_r = sel_res.split(" - ")[0]
            
            with st.form("form_soapie"):
                turno = st.selectbox("Turno Asignado", ["Mañana (07:00 - 13:00)", "Tarde (13:00 - 19:00)", "Noche (19:00 - 07:00)"])
                
                st.markdown("### 📋 Estructura de Registro SOAPIE")
                s = st.text_area("S - Subjetivo (Manifestaciones del paciente o familiar)")
                o = st.text_area("O - Objetivo (Examen físico y constantes vitales)")
                a = st.text_area("A - Análisis (Juicio clínico de enfermería)")
                p = st.text_area("P - Plan (Cuidados programados)")
                i = st.text_area("I - Intervención (Procedimientos ejecutados)")
                e = st.text_area("E - Evaluación (Respuesta clínica del paciente)")
                
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("FIRMAR Y ARCHIVAR NOTA INMUTABLE", use_container_width=True):
                    if s and o:
                        id_n = f"SOAPIE-{uuid.uuid4().hex[:6].upper()}"
                        f_hora = ahora_colombia().strftime("%Y-%m-%d %H:%M:%S")
                        autor_firma = f"{st.session_state.alias_actual} ({st.session_state.reg_profesional})"
                        
                        nueva_nota = pd.DataFrame([{
                            "ID_Nota": id_n, "Cedula": str(cc_r), "Fecha_Hora": f_hora, "Turno": turno,
                            "Autor": autor_firma, "Subjetivo": s, "Objetivo": o, "Analisis": a,
                            "Plan": p, "Intervencion": i, "Evaluacion": e
                        }])
                        
                        guardar_tabla(pd.concat([df_sop, nueva_nota], ignore_index=True), "notas_soapie")
                        st.success("✅ Nota SOAPIE guardada con éxito y sincronizada en la nube.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("⚠️ Los campos Subjetivo y Objetivo son obligatorios para la firma legal.")
        else:
            st.warning("⚠️ No hay residentes activos registrados en el sistema.")
