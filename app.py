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
# 5. CARGA INICIAL Y LOGIN INMERSIVO
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
    st.markdown("""
    <div style='display:flex; justify-content:center; align-items:center; height: 80vh;'>
        <div class='glass-card' style='width: 420px; text-align: center; padding: 35px;'>
            <div style='font-size: 3.5rem; color: var(--emerald); margin-bottom: 15px;'>🏥</div>
            <h1 style='margin-bottom: 5px;'>Geriatría OS</h1>
            <p style='color: #6B7280; margin-bottom: 25px; font-size: 0.9rem;'>Gestión Clínica y Notas de Enfermería</p>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,4,1])
    with col2:
        user_input = st.text_input("Usuario", placeholder="ID de Usuario")
        pass_input = st.text_input("Contraseña", type="password", placeholder="••••••••")
        if st.button("INGRESAR AL SISTEMA"):
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
    st.markdown("</div></div>", unsafe_allow_html=True)
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
