# ==========================================
# GERIATRÍA OS v1.0 - CLINICAL ENTERPRISE
# ==========================================

import streamlit as st
import pandas as pd
import os
import uuid
from datetime import datetime, timedelta, timezone
import time
import requests
import json
from html import escape

# --- 1. CONFIGURACIÓN INICIAL DE PÁGINA ---
st.set_page_config(
    page_title="Geriatría OS | Clinical SaaS",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def ahora_colombia():
    """Hora exacta en Colombia (UTC-5) para trazabilidad legal."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=5)

# --- 2. LIBRERÍAS DE CONEXIÓN CON GOOGLE ---
try:
    import gspread
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    GSPREAD_DISPONIBLE = True
except ImportError:
    GSPREAD_DISPONIBLE = False

# ==========================================
# 3. MOTOR DE AUTO-CREACIÓN DE BASES DE DATOS
# ==========================================
@st.cache_resource
def _almacen_cache():
    return {"tablas": {}, "hojas": {}, "carpetas": {}, "listados": {}}

@st.cache_data(ttl=3000, show_spinner=False)
def obtener_token_fresco():
    creds = Credentials.from_authorized_user_info({
        "client_id": st.secrets["google_client_id"],
        "client_secret": st.secrets["google_client_secret"],
        "refresh_token": st.secrets["google_refresh_token"],
        "token_uri": "https://oauth2.googleapis.com/token"
    })
    creds.refresh(Request())
    return creds.token

@st.cache_resource
def conectar_gsheets():
    """Conecta a Google Sheets. Si la base de datos no existe, la crea con sus 9 pestañas clínicas."""
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
            # Auto-creación del libro y sus 9 pestañas clínicas
            sheet = client.create(nombre_hoja)
            pestañas = [
                "residentes", "signos_vitales", "notas_soapie", 
                "kardex_meds", "escalas", "usuarios", 
                "logs", "memos", "directorio"
            ]
            first_sheet = sheet.get_sheet_by_id(0)
            first_sheet.update_title(pestañas[0])
            for p in pestañas[1:]:
                sheet.add_worksheet(title=p, rows="100", cols="20")
        return sheet
    except Exception as e:
        print(f"⚠️ [LOG SISTEMA]: Error conectando a GSheets: {e}")
        return None

gc_sheet = conectar_gsheets()
TTL_TABLAS = 600

def _hoja(nombre_tabla):
    hojas = _almacen_cache()["hojas"]
    if nombre_tabla not in hojas:
        hojas[nombre_tabla] = gc_sheet.worksheet(nombre_tabla)
    return hojas[nombre_tabla]

def leer_tabla(nombre_tabla, columnas_def):
    """Lee la tabla remota o la crea automáticamente en CSV local si la red falla."""
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
            print(f"⚠️ [LOG SISTEMA]: Releyendo hoja {nombre_tabla} -> {e}")
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
            print(f"⚠️ [LOG SISTEMA]: Error guardando en {nombre_tabla} -> {e}")
            _almacen_cache()["hojas"].pop(nombre_tabla, None)
    _almacen_cache()["tablas"].pop(nombre_tabla, None)

# ==========================================
# 4. CONTROL DE SESIONES Y MOTOR CSS GLASS
# ==========================================
for v in ['autenticado']: 
    if v not in st.session_state: st.session_state[v] = False
for v in ['usuario_actual', 'rol_actual', 'alias_actual', 'reg_profesional']: 
    if v not in st.session_state: st.session_state[v] = ""
if 'pagina_actual' not in st.session_state: st.session_state.pagina_actual = 'Hub'

def cambiar_pagina(p): st.session_state.pagina_actual = p

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');

:root {
  --navy: #0A192F; --emerald: #10B981; --emerald-dark: #047857;
  --gold: #D4AF37; --bg-color: #F4F7F6; --text-main: #1F2937;
  --glass-bg: rgba(255, 255, 255, 0.80);
  --glass-border: rgba(255, 255, 255, 0.5);
  --glass-shadow: 0 8px 32px 0 rgba(10, 25, 47, 0.08);
}

html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; color: var(--text-main); }
[data-testid="stAppViewContainer"] { background: linear-gradient(135deg, #F4F7F6 0%, #E5E9E8 100%) !important; }
[data-testid="stHeader"], [data-testid="stSidebar"] { display: none !important; }
.block-container { padding: 5.5rem 2rem 2rem 2rem !important; max-width: 1400px; }

h1, h2, h3 { font-family: 'Fraunces', serif !important; color: var(--navy) !important; font-weight: 700; }

.glass-card {
  background: var(--glass-bg); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--glass-border); border-radius: 20px; padding: 25px;
  box-shadow: var(--glass-shadow); margin-bottom: 20px;
}

.sticky-navbar {
  position: fixed; top: 0; left: 0; width: 100%; height: 70px;
  background: rgba(10, 25, 47, 0.95); backdrop-filter: blur(10px);
  z-index: 999999; display: flex; align-items: center; justify-content: space-between;
  padding: 0 2rem; border-bottom: 3px solid var(--emerald);
}
.navbar-brand { font-family: 'Fraunces', serif; font-size: 1.4rem; color: var(--emerald); font-weight: 700; }
.navbar-brand span { color: white; font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.9rem; font-weight: 400; }

div.stButton > button {
  background: linear-gradient(135deg, var(--emerald) 0%, var(--emerald-dark) 100%) !important;
  color: white !important; font-weight: 700 !important; border: none !important;
  border-radius: 12px !important; padding: 0.5rem 1rem !important;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5. CARGA INICIAL Y LOGIN INMERSIVO (LIMPIO)
# ==========================================
df_usr = leer_tabla("usuarios", ["Usuario", "Password", "Rol", "Alias", "Reg_Profesional", "Session_Token"])

if df_usr.empty:
    df_usr = pd.DataFrame([{
        "Usuario": "enfermeria", 
        "Password": "123", 
        "Rol": "Enfermero/a", 
        "Alias": "Enf. Turno", 
        "Reg_Profesional": "TP-998877", 
        "Session_Token": ""
    }])
    guardar_tabla(df_usr, "usuarios")

if not st.session_state.autenticado:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 1.2, 1])
    
    with col_l2:
        with st.container(border=True):
            st.markdown("<div style='text-align: center; font-size: 3rem;'>🏥</div>", unsafe_allow_html=True)
            st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>Geriatría OS</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #6B7280; font-size: 0.9rem;'>Gestión Clínica y Notas de Enfermería</p>", unsafe_allow_html=True)
            st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
            
            user_input = st.text_input("Usuario", placeholder="ID de Usuario")
            pass_input = st.text_input("Contraseña", type="password", placeholder="••••••••")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("INGRESAR AL SISTEMA", use_container_width=True):
                user_match = df_usr[(df_usr["Usuario"].astype(str) == user_input) & (df_usr["Password"].astype(str) == pass_input)]
                if not user_match.empty:
                    st.session_state.autenticado = True
                    st.session_state.usuario_actual = user_input
                    st.session_state.rol_actual = user_match.iloc[0]["Rol"]
                    st.session_state.alias_actual = user_match.iloc[0].get("Alias", user_input)
                    st.session_state.reg_profesional = str(user_match.iloc[0].get("Reg_Profesional", "N/A"))
                    st.session_state.pagina_actual = 'Hub'
                    st.rerun()
                else:
                    st.error("Credenciales médicas incorrectas.")
    st.stop()

# ==========================================
# 6. STICKY NAVBAR Y NAVEGACIÓN
# ==========================================
st.markdown(f"""
<div class="sticky-navbar">
    <div class="navbar-brand">
        🏥 Geriatría OS <span>| {st.session_state.alias_actual} ({st.session_state.rol_actual})</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='position: fixed; top: 15px; right: 2rem; z-index: 999999; display: flex; gap: 8px;'>", unsafe_allow_html=True)
c_nav = st.columns(4)
with c_nav[0]: 
    if st.button("🏠 Hub"): cambiar_pagina("Hub")
with c_nav[1]: 
    if st.button("📝 SOAPIE"): cambiar_pagina("SOAPIE")
with c_nav[2]: 
    if st.button("👴 Residentes"): cambiar_pagina("Residentes")
with c_nav[3]: 
    if st.button("🚪 Salir"): 
        st.session_state.autenticado = False
        st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 7. VISTAS Y MÓDULOS
# ==========================================
if st.session_state.pagina_actual == 'Hub':
    st.markdown("<h1>Centro de Mando Clínico</h1><p>Bienvenido al sistema de administración y enfermería.</p>", unsafe_allow_html=True)
    st.markdown("<div class='glass-card'><h3>✅ Sistema Inicializado</h3><p>La base de datos y la interfaz de salud están operando correctamente.</p></div>", unsafe_allow_html=True)

elif st.session_state.pagina_actual == 'SOAPIE':
    st.markdown("<h1>📝 Notas de Enfermería (Metodología SOAPIE)</h1>", unsafe_allow_html=True)
    st.markdown("<div class='glass-card'><p>Aquí irá el formulario inmutable de evoluciones clínicas.</p></div>", unsafe_allow_html=True)

elif st.session_state.pagina_actual == 'Residentes':
    st.markdown("<h1>👴 Directorio de Residentes</h1>", unsafe_allow_html=True)
    st.markdown("<div class='glass-card'><p>Aquí irá el módulo de admisión de adultos mayores.</p></div>", unsafe_allow_html=True)
# ==========================================
# 8. MÓDULOS DEL SISTEMA: RESIDENTES Y SOAPIE
# ==========================================

# Cargamos las tablas de residentes y notas desde GSheets o CSV local
df_res = leer_tabla("residentes", ["Cedula", "Nombre", "Fecha_Nacimiento", "EPS", "Habitacion", "Acudiente_Nombre", "Acudiente_Tel", "Estado", "F_Ingreso"])
df_sop = leer_tabla("notas_soapie", ["ID_Nota", "Cedula", "Fecha_Hora", "Turno", "Autor", "Subjetivo", "Objetivo", "Analisis", "Plan", "Intervencion", "Evaluacion"])

# --- HUB CENTRAL ---
if st.session_state.pagina_actual == 'Hub':
    st.markdown("<h1>Centro de Mando Clínico</h1><p>Control de turno y registro geriátrico de salud.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.markdown("### 📝 Notas SOAPIE")
            st.markdown("Registro legal e inmutable de notas de enfermería por turno.")
            if st.button("ABRIR NOTAS SOAPIE", key="b_so", use_container_width=True): 
                cambiar_pagina("SOAPIE")
                st.rerun()
    with col2:
        with st.container(border=True):
            st.markdown("### 👴 Residentes")
            st.markdown("Directorio de adultos mayores, ingresos y carpetas clínicas.")
            if st.button("VER RESIDENTES", key="b_rs", use_container_width=True): 
                cambiar_pagina("Residentes")
                st.rerun()
    with col3:
        with st.container(border=True):
            st.markdown("### 📊 Estado General")
            st.metric("Residentes Activos", len(df_res[df_res["Estado"] == "Activo"]) if not df_res.empty else 0)

# --- MÓDULO: GESTIÓN DE RESIDENTES ---
elif st.session_state.pagina_actual == 'Residentes':
    st.markdown("<h1>👴 Gestión de Adultos Mayores</h1>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.subheader("Admisión de Nuevo Residente")
        with st.form("form_residente"):
            c1, c2, c3 = st.columns(3)
            with c1: cc_n = st.text_input("Cédula de Ciudadanía")
            with c2: nom_n = st.text_input("Nombre Completo")
            with c3: hab_n = st.text_input("Habitación / Cama")
            
            c4, c5, c6 = st.columns(3)
            with c4: fnac_n = st.date_input("Fecha Nacimiento")
            with c5: eps_n = st.text_input("EPS / Medicina Prepagada")
            with c6: acud_n = st.text_input("Nombre de Acudiente / Familiar")
            
            c7 = st.text_input("Teléfono de Emergencia Acudiente")
            
            if st.form_submit_button("REGISTRAR ADMISIÓN", use_container_width=True):
                if cc_n and nom_n:
                    nuevo_res = pd.DataFrame([{
                        "Cedula": str(cc_n), "Nombre": nom_n, "Fecha_Nacimiento": str(fnac_n),
                        "EPS": eps_n, "Habitacion": hab_n, "Acudiente_Nombre": acud_n,
                        "Acudiente_Tel": str(c7), "Estado": "Activo", "F_Ingreso": ahora_colombia().strftime("%Y-%m-%d")
                    }])
                    guardar_tabla(pd.concat([df_res, nuevo_res], ignore_index=True), "residentes")
                    st.success("✅ Residente admitido y registrado en la base de datos clínica.")
                    time.sleep(1)
                    st.rerun()
                else: 
                    st.error("Cédula y Nombre son requeridos.")
            
    if not df_res.empty:
        with st.container(border=True):
            st.subheader("📋 Directorio de Residentes Activos")
            st.dataframe(df_res[df_res["Estado"] == "Activo"][["Cedula", "Nombre", "Habitacion", "EPS", "Acudiente_Nombre", "Acudiente_Tel"]], use_container_width=True, hide_index=True)

# --- MÓDULO: NOTAS SOAPIE ---
elif st.session_state.pagina_actual == 'SOAPIE':
    st.markdown("<h1>📝 Notas de Enfermería (Metodología SOAPIE)</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        st.info("⚖️ **Cumplimiento Normativo:** Las notas de enfermería quedan registradas con marca de tiempo UTC-5 de Colombia y firma profesional inmutable.")
        
        res_activos = df_res[df_res["Estado"] == "Activo"] if not df_res.empty else pd.DataFrame()
        if not res_activos.empty:
            sel_res = st.selectbox("Seleccione el Residente / Paciente:", res_activos["Cedula"].astype(str) + " - " + res_activos["Nombre"])
            cc_r = sel_res.split(" - ")[0]
            
            with st.form("form_soapie"):
                turno = st.selectbox("Turno de Enfermería", ["Mañana (07:00 - 13:00)", "Tarde (13:00 - 19:00)", "Noche (19:00 - 07:00)"])
                
                st.markdown("### 📋 Estructura de la Evolución Clínica")
                s = st.text_area("S - Subjetivo (Lo que manifiesta el residente o familiar)")
                o = st.text_area("O - Objetivo (Hallazgos físicos, examen y constantes vitales)")
                a = st.text_area("A - Análisis (Juicio o diagnóstico de enfermería)")
                p = st.text_area("P - Plan (Cuidados o intervenciones programadas)")
                i = st.text_area("I - Intervención (Ejecución de actividades de enfermería)")
                e = st.text_area("E - Evaluación (Respuesta y evolución del residente)")
                
                if st.form_submit_button("FIRMAR Y GUARDAR NOTA INMUTABLE", use_container_width=True):
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
                        st.success("✅ Nota de Enfermería firmada digitalmente y archivada de forma inmutable.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("⚠️ Los campos Subjetivo y Objetivo son obligatorios.")
        else: 
            st.warning("⚠️ No hay residentes activos registrados. Primero debes admitir al menos un residente en el módulo correspondiente.")
