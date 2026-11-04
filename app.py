# -*- coding: utf-8 -*-
"""
GERIATRÍA OS · Suite clínica
Interfaz Streamlit. Los datos viven en Google Drive (carpeta Geriatria_OS) vía nucleo.py
"""
import html
from datetime import date

import pandas as pd
import streamlit as st

import nucleo as N

st.set_page_config(page_title="Geriatría OS", page_icon="🏥", layout="wide",
                   initial_sidebar_state="expanded")

# Streamlit ≥1.50 usa width="stretch"; las anteriores use_container_width=True
try:
    _VER = tuple(int(x) for x in st.__version__.split(".")[:2])
except Exception:
    _VER = (0, 0)
KW = {"width": "stretch"} if _VER >= (1, 50) else {"use_container_width": True}

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]
ROLES = ["Enfermero/a", "Auxiliar de enfermería", "Médico/a", "Administrador"]
h = html.escape

# ══════════════════════════════════════════════════════════════
# ESTILOS
# ══════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');
:root{--navy:#0B1F3A;--navy2:#16325C;--green:#0F9D7A;--green2:#0A7A5E;--gold:#C9A227;
--bg:#F3F6FA;--ink:#1B2A3F;--muted:#5F6F85;--line:#D6DEE9;--r:16px}

.stApp, .stApp p, .stApp label, .stApp li, .stApp td, .stApp th, .stApp input, .stApp textarea,
.stApp button, .stApp [data-baseweb="select"] {font-family:'Plus Jakarta Sans',sans-serif}
.stApp{background:linear-gradient(180deg,#E8EFF7 0%,var(--bg) 260px);color:var(--ink)}
.stApp h1,.stApp h2,.stApp h3{font-family:'Fraunces',serif;color:var(--navy);font-weight:700}
.stApp h1{font-size:2rem;margin-bottom:.1rem}
.stApp h5{color:var(--navy);font-weight:800}
.block-container{padding:2rem 2.2rem 4rem!important;max-width:1400px}
#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important}
[data-testid="stHeader"]{background:transparent}
.sub{color:var(--muted);margin:0 0 1.2rem;font-size:.98rem}

/* Barra lateral */
[data-testid="stSidebar"]{background:linear-gradient(180deg,var(--navy) 0%,var(--navy2) 100%)}
[data-testid="stSidebar"] *{color:#E6EDF7}
.sb-brand{font-family:'Fraunces',serif;font-size:1.45rem;font-weight:700;color:#fff;margin:.2rem 0 .9rem}
.sb-user{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);border-radius:14px;padding:10px 14px;margin-bottom:1rem}
.sb-tenant{color:#9FB3CC;font-size:.82rem;font-weight:600;margin:-.6rem 0 .9rem}
.sb-alias{font-weight:800;color:#fff}.sb-rol{font-size:.8rem;color:#C9A227;font-weight:700}
[data-testid="stSidebar"] button[kind="secondary"],[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]{
 background:rgba(255,255,255,.06)!important;border:1px solid rgba(255,255,255,.12)!important;color:#fff!important;
 justify-content:flex-start;box-shadow:none!important}
[data-testid="stSidebar"] button[kind="secondary"]:hover{background:rgba(255,255,255,.14)!important}

/* Botones */
.stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button{
 border-radius:12px;font-weight:700;padding:.55rem 1.1rem;transition:all .2s ease}
button[kind="primary"],button[kind="primaryFormSubmit"],
button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"]{
 background:linear-gradient(135deg,var(--green),var(--green2))!important;color:#fff!important;border:none!important;
 box-shadow:0 6px 16px rgba(15,157,122,.28)!important}
button[kind="primary"] p,button[kind="primaryFormSubmit"] p,
button[data-testid="stBaseButton-primary"] p,button[data-testid="stBaseButton-primaryFormSubmit"] p{color:#fff!important}
button[kind="secondary"],button[kind="secondaryFormSubmit"],
button[data-testid="stBaseButton-secondary"],button[data-testid="stBaseButton-secondaryFormSubmit"]{
 background:#fff;color:var(--navy);border:1.5px solid var(--line)}
.stButton>button:hover{transform:translateY(-1px)}

/* Campos */
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="select"]>div{
 background:#fff!important;border-radius:10px!important;border:1.5px solid #AAB7C8!important}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within,[data-baseweb="select"]:focus-within>div{
 border-color:var(--green)!important;box-shadow:0 0 0 3px rgba(15,157,122,.18)!important}
.stApp input,.stApp textarea{color:#0F172A!important;font-weight:500}
[data-testid="stWidgetLabel"] p,.stApp label p{color:var(--navy)!important;font-weight:700!important;font-size:.9rem!important}

/* Formularios, pestañas */
[data-testid="stForm"]{background:#fff;border:1px solid var(--line)!important;border-radius:var(--r)!important;
 padding:20px 22px!important;box-shadow:0 10px 28px -12px rgba(11,31,58,.14)}
button[data-baseweb="tab"] p{font-weight:700;font-size:.98rem}
[data-baseweb="tab-highlight"]{background:var(--green)!important}

/* Tarjetas propias */
.kpi{background:#fff;border:1px solid var(--line);border-left:5px solid var(--green);border-radius:var(--r);
 padding:16px 18px;box-shadow:0 8px 22px -10px rgba(11,31,58,.18);margin-bottom:10px}
.kpi .n{font-family:'Fraunces',serif;font-size:2.2rem;font-weight:700;color:var(--navy);line-height:1}
.kpi .l{color:var(--muted);font-size:.84rem;font-weight:700;margin-top:6px}
.kpi.warn{border-left-color:var(--gold)}.kpi.crit{border-left-color:#D64545}
.ficha{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:14px 20px;margin:4px 0 16px;
 display:flex;gap:16px;align-items:center;flex-wrap:wrap;box-shadow:0 8px 22px -12px rgba(11,31,58,.18)}
.avatar{width:54px;height:54px;border-radius:50%;background:linear-gradient(135deg,var(--green),var(--navy2));color:#fff;
 display:flex;align-items:center;justify-content:center;font-weight:800;font-size:1.15rem;flex:none}
.ficha .nom{font-weight:800;font-size:1.15rem;color:var(--navy)}
.ficha .sub2{color:var(--muted);font-size:.86rem;margin-top:2px}
.ficha .der{margin-left:auto;text-align:right}
.chip{display:inline-block;padding:4px 11px;border-radius:999px;font-size:.78rem;font-weight:700;margin:2px 4px 2px 0}
.chip-ok{background:#E3F6EF;color:#0A7A5E}.chip-warn{background:#FFF3D6;color:#8A6A00}.chip-crit{background:#FDECEC;color:#A12828}
.puntaje{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:16px 20px;margin:10px 0;
 display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.puntaje .n{font-family:'Fraunces',serif;font-size:2.4rem;font-weight:700;color:var(--navy)}
.login-logo{text-align:center;font-size:3.6rem;margin-top:3rem}
.login-sub{text-align:center;color:var(--muted);margin:-.2rem 0 1rem}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# UTILIDADES DE INTERFAZ
# ══════════════════════════════════════════════════════════════
def bloque(s):
    """HTML en una sola línea (evita que Markdown lo tome como código)."""
    return "".join(l.strip() for l in s.strip().splitlines())


def _cfg():
    try:
        return dict(st.secrets)
    except Exception:
        return {}


def titulo(t, sub=""):
    st.markdown(f"<h1>{t}</h1><p class='sub'>{sub}</p>", unsafe_allow_html=True)


def kpi(n, etiqueta, tono=""):
    return f"<div class='kpi {tono}'><div class='n'>{n}</div><div class='l'>{h(etiqueta)}</div></div>"


def chip(texto, nivel="ok"):
    return f"<span class='chip chip-{nivel}'>{h(texto)}</span>"


def flash(tipo, msg):
    st.session_state["_flash"] = (tipo, msg)


def mostrar_flash():
    f = st.session_state.pop("_flash", None)
    if f:
        {"ok": st.success, "warn": st.warning, "err": st.error}[f[0]](f[1])


def nueva_version(form):
    st.session_state[f"f_{form}"] += 1


def selector_fecha(etiqueta, defecto, clave):
    """Día / Mes / Año en listas: mucho más cómodo que el calendario para años antiguos."""
    st.markdown(f"<p style='margin:0 0 4px;font-weight:700;font-size:.9rem;color:#0B1F3A'>{etiqueta}</p>",
                unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.7, 1.2])
    anios = list(range(N.hoy().year, 1899, -1))
    d = c1.selectbox("Día", list(range(1, 32)), index=defecto.day - 1, key=f"{clave}_d")
    m = c2.selectbox("Mes", list(range(1, 13)), index=defecto.month - 1,
                     format_func=lambda x: MESES[x - 1], key=f"{clave}_m")
    a = c3.selectbox("Año", anios, index=anios.index(defecto.year) if defecto.year in anios else 0,
                     key=f"{clave}_a")
    try:
        f = date(a, m, d)
    except ValueError:
        return None
    return f if f <= N.hoy() else None


def selector_residente(clave, solo_activos=True):
    df = N.leer("residentes")
    if solo_activos:
        df = df[df["Estado"] != "Egresado"]
    if df.empty:
        st.info("Aún no hay residentes registrados. Cree una admisión en el módulo **Residentes**.")
        return None
    opciones = df["Cedula"].tolist()
    etiquetas = {r.Cedula: f"{r.Nombre} · CC {r.Cedula} · Hab. {r.Habitacion or '—'}" for r in df.itertuples()}
    k = f"sel_{clave}"
    if st.session_state.get(k) not in opciones:  # primera vez en esta pantalla: hereda el último residente elegido
        previo = st.session_state.get("res_sel")
        st.session_state[k] = previo if previo in opciones else opciones[0]
    sel = st.selectbox("Residente", opciones, format_func=lambda c: etiquetas.get(c, c), key=k)
    st.session_state["res_sel"] = sel
    return sel


def ficha(cedula):
    df = N.leer("residentes")
    f = df[df["Cedula"] == cedula]
    if f.empty:
        return None
    r = f.iloc[0]
    edad = N.calcular_edad(r["Fecha_Nacimiento"])
    ini = "".join(p[0] for p in r["Nombre"].split()[:2]).upper() or "?"
    alerg = r["Alergias"].strip()
    sin_alerg = alerg.lower() in ("", "ninguna", "no", "n/a", "ninguna conocida")
    chip_al = chip("Sin alergias reportadas", "ok") if sin_alerg else chip(f"⚠ Alergias: {alerg}", "crit")
    dx = f"<div class='sub2'>Dx: {h(r['Diagnosticos'])}</div>" if r["Diagnosticos"].strip() else ""
    edad_txt = f"{edad} años · " if edad is not None else ""
    estado = "" if r["Estado"] != "Egresado" else chip("Egresado", "warn")
    st.markdown(bloque(f"""
        <div class="ficha"><div class="avatar">{h(ini)}</div>
        <div><div class="nom">{h(r['Nombre'])} {estado}</div>
        <div class="sub2">{edad_txt}CC {h(r['Cedula'])} · Hab. {h(r['Habitacion'] or '—')} · {h(r['EPS'] or 'Sin EPS')}</div>{dx}</div>
        <div class="der">{chip_al}<div class="sub2">Acudiente: {h(r['Acudiente_Nombre'] or '—')} {h(r['Acudiente_Tel'])}</div></div></div>
    """), unsafe_allow_html=True)
    return r


def tabla(df, **kw):
    st.dataframe(df, hide_index=True, **KW, **kw)


# ══════════════════════════════════════════════════════════════
# SESIÓN Y LOGIN (multi-geriátrico)
# ══════════════════════════════════════════════════════════════
import time

for _k, _v in {"auth": False, "usuario": "", "rol": "", "alias": "", "reg": "", "pagina": "Hub", "tenant": "",
               "forzar_clave": False, "intentos": 0, "bloqueo": 0.0}.items():
    st.session_state.setdefault(_k, _v)
for _f in ("adm", "edit", "vit", "med", "adm_med", "susp", "esc", "soap", "usr", "pw",
           "cli_pago", "cli_ed", "cli_new", "cli_pw", "cli_estado", "cli_vault"):
    st.session_state.setdefault(f"f_{_f}", 0)

N.usar_tenant(None)   # cada recarga empieza sin geriátrico; solo se fija tras validar la sesión
N.conectar(_cfg())    # hoja de CONTROL del propietario


def _ocultar_sidebar():
    st.markdown("<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl'],"
                "[data-testid='collapsedControl']{display:none!important}</style>", unsafe_allow_html=True)


def _cerrar_sesion(aviso=None):
    st.session_state.update(auth=False, usuario="", rol="", alias="", reg="", tenant="", forzar_clave=False, pagina="Hub")
    if aviso:
        st.session_state["_aviso_login"] = aviso
    st.rerun()


def _frenar():
    if time.time() < st.session_state.bloqueo:
        st.error("Demasiados intentos. Espere un minuto e intente de nuevo.")
        return True
    return False


def _fallo():
    st.session_state.intentos += 1
    if st.session_state.intentos >= 5:
        st.session_state.bloqueo = time.time() + 60
        st.session_state.intentos = 0


def _login_cliente():
    cfg = _cfg()
    if N.hay_credenciales(cfg) and not N.estado_control()["conectado"]:
        st.error("No hay conexión con la bóveda de datos en este momento. Intente de nuevo en un minuto.")
        if st.button("🔄 Reintentar", key="reint_login", **KW):
            N.conectar(cfg, forzar=True)
            st.rerun()
        return
    with st.form("login_cli"):
        cod = st.text_input("Código del geriátrico", placeholder="GER-XXXXXX")
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Iniciar sesión", type="primary", **KW)
    if not ok or _frenar():
        return
    try:
        cli = N.buscar_cliente(cod)
        if cli is None:
            _fallo()
            st.error("Código, usuario o contraseña incorrectos.")
            return
        acceso, motivo, _ = N.estado_servicio(cli)
        if not acceso:
            st.error(f"⛔ {motivo} Comuníquese con su proveedor para reactivar el servicio.")
            return
        if not N.abrir_tenant(cfg, cli):
            st.error("No se pudo abrir la bóveda de este geriátrico. Intente de nuevo o avise a su proveedor.")
            return
        N.usar_tenant(cli["Codigo"])
        r = N.autenticar(u, p)
        if r is None:
            N.log(u or "?", "LOGIN_FALLIDO")
            _fallo()
            st.error("Código, usuario o contraseña incorrectos.")
            return
        st.session_state.update(auth=True, tenant=cli["Codigo"], usuario=r["Usuario"], rol=r["Rol"],
                                alias=r["Alias"] or r["Usuario"], reg=r["Reg_Profesional"], pagina="Hub", intentos=0,
                                forzar_clave=str(r.get("Cambiar_Clave", "")).upper() == "SI")
        N.log(r["Usuario"], "LOGIN")
    except N.ErrorNube as e:
        st.error(f"Problema con la bóveda de datos: {e}")
        return
    st.rerun()


def _login_owner():
    cfg = _cfg()
    if not N.owner_configurado(cfg):
        if N.hay_credenciales(cfg):
            st.warning("El acceso de propietario no está configurado. Defina `owner_password` en Secrets.")
            return
        st.info("🧪 Modo demostración local · usuario `owner` · contraseña `owner123`")
    with st.form("login_owner"):
        u = st.text_input("Usuario propietario")
        p = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Entrar al panel", type="primary", **KW)
    if not ok or _frenar():
        return
    if N.verificar_owner(cfg, u, p):
        st.session_state.update(auth=True, tenant="", usuario=u.strip().lower(), rol="Propietario", alias="Propietario",
                                reg="", pagina="OwnerHub", intentos=0, forzar_clave=False)
        N.log_control(u.strip().lower(), "LOGIN_PROPIETARIO")
        st.rerun()
    _fallo()
    st.error("Credenciales incorrectas.")


def pantalla_login():
    _ocultar_sidebar()
    _, c, _ = st.columns([1, 1.15, 1])
    with c:
        st.markdown("<div class='login-logo'>🏥</div><h1 style='text-align:center'>Geriatría OS</h1>"
                    "<p class='login-sub'>Suite clínica gerontológica · Notas SOAPIE</p>", unsafe_allow_html=True)
        aviso = st.session_state.pop("_aviso_login", None)
        if aviso:
            st.error(aviso)
        t1, t2 = st.tabs(["🏥 Mi geriátrico", "🔑 Propietario"])
        with t1:
            _login_cliente()
        with t2:
            _login_owner()


if not st.session_state.auth:
    pantalla_login()
    st.stop()

ES_OWNER = st.session_state.rol == "Propietario"
CLI = None
if not ES_OWNER:
    # En CADA recarga: el geriátrico debe seguir existiendo y con servicio vigente (si no paga, se corta el acceso)
    try:
        CLI = N.buscar_cliente(st.session_state.tenant)
        _ok, _motivo, _dias = N.estado_servicio(CLI) if CLI else (False, "Cuenta no encontrada.", None)
        if not _ok:
            _cerrar_sesion(f"⛔ {_motivo} Comuníquese con su proveedor para reactivar el servicio.")
        if not N.abrir_tenant(_cfg(), CLI):
            st.error("No se pudo abrir la bóveda de datos de este geriátrico. Intente de nuevo en unos segundos.")
            st.stop()
        N.usar_tenant(CLI["Codigo"])
    except N.ErrorNube as e:
        st.error(f"⚠️ Problema con la bóveda de datos: {e}")
        st.stop()


def pantalla_cambio_clave():
    _ocultar_sidebar()
    _, c, _ = st.columns([1, 1.15, 1])
    with c:
        st.markdown("<div class='login-logo'>🔐</div><h2 style='text-align:center'>Cree su contraseña personal</h2>"
                    "<p class='login-sub'>Por seguridad debe cambiar la clave temporal antes de continuar.</p>", unsafe_allow_html=True)
        with st.form("form_pw_forzado"):
            n1 = st.text_input("Nueva contraseña (mínimo 8 caracteres)", type="password")
            n2 = st.text_input("Repetir contraseña", type="password")
            ok = st.form_submit_button("Guardar y continuar", type="primary", **KW)
        if ok:
            if len(n1) < 8 or n1 != n2:
                st.error("La contraseña debe tener 8+ caracteres y coincidir en ambos campos.")
            else:
                N.actualizar("usuarios", "Usuario", st.session_state.usuario, {"Password": N.hash_pw(n1), "Cambiar_Clave": "NO"})
                N.log(st.session_state.usuario, "CAMBIO_CLAVE")
                st.session_state.forzar_clave = False
                st.rerun()
        if st.button("Cancelar y salir", key="salir_forzado", **KW):
            _cerrar_sesion()


if st.session_state.forzar_clave and not ES_OWNER:
    pantalla_cambio_clave()
    st.stop()

# ══════════════════════════════════════════════════════════════
# BARRA LATERAL
# ══════════════════════════════════════════════════════════════
if ES_OWNER:
    PAGINAS = [("OwnerHub", "📈", "Resumen"), ("Clientes", "🏢", "Clientes"), ("NuevoCliente", "➕", "Nuevo cliente"),
               ("Pagos", "💳", "Pagos"), ("OwnerSistema", "🛠", "Sistema")]
    MARCA = "Panel del propietario"
else:
    PAGINAS = [("Hub", "🏠", "Centro de mando"), ("Residentes", "👴", "Residentes"), ("Vitales", "🩺", "Signos vitales"),
               ("Kardex", "💊", "Kardex de medicamentos"), ("Escalas", "📊", "Escalas geriátricas"),
               ("SOAPIE", "📝", "Notas SOAPIE")]
    if st.session_state.rol == "Administrador":
        PAGINAS.append(("Admin", "⚙️", "Administración"))
    MARCA = CLI["Nombre"]
if st.session_state.pagina not in [p[0] for p in PAGINAS]:
    st.session_state.pagina = PAGINAS[0][0]

with st.sidebar:
    st.markdown(bloque(f"""<div class="sb-brand">🏥 Geriatría OS</div><div class="sb-tenant">{h(MARCA)}</div><div class="sb-user">
        <div class="sb-alias">{h(st.session_state.alias)}</div><div class="sb-rol">{h(st.session_state.rol)}</div></div>"""),
                unsafe_allow_html=True)
    for clave, icono, nombre in PAGINAS:
        activa = st.session_state.pagina == clave
        if st.button(f"{icono}  {nombre}", key=f"nav_{clave}", type="primary" if activa else "secondary", **KW):
            st.session_state.pagina = clave
            st.rerun()
    st.markdown("---")
    _e = N.estado_control() if ES_OWNER else N.estado_nube()
    st.markdown(chip("☁️ Bóveda conectada", "ok") if _e["conectado"] else chip("💾 Modo demostración local", "crit"),
                unsafe_allow_html=True)
    if st.button("🚪  Cerrar sesión", key="nav_salir", **KW):
        if ES_OWNER:
            N.log_control(st.session_state.usuario, "LOGOUT_PROPIETARIO")
        else:
            N.log(st.session_state.usuario, "LOGOUT")
        _cerrar_sesion()

mostrar_flash()
if not ES_OWNER and not N.estado_nube()["conectado"]:
    st.warning("💾 **Modo demostración local.** Los datos se guardan solo en este servidor y pueden perderse al reiniciar la app.")


# ══════════════════════════════════════════════════════════════
# CENTRO DE MANDO
# ══════════════════════════════════════════════════════════════
def pagina_hub():
    titulo("Centro de mando", f"{N.hoy().strftime('%d/%m/%Y')} · panel general de supervisión gerontológica")
    if st.session_state.rol == "Administrador" and CLI:
        _o, _m, _d = N.estado_servicio(CLI)
        if _d is not None and _d <= 7:
            st.warning("💳 Su suscripción " + (f"vence en {_d} días" if _d >= 0 else "está en periodo de gracia") +
                       ". Contacte a su proveedor para renovar y evitar la suspensión del servicio.")

    res = N.leer("residentes")
    act = res[res["Estado"] != "Egresado"]
    vit, sop, kar = N.leer("signos_vitales"), N.leer("notas_soapie"), N.leer("kardex_meds")
    hoy_s = N.hoy().isoformat()
    v_hoy = vit[vit["Fecha_Hora"].str.startswith(hoy_s)]
    crit = int(v_hoy["Alertas"].str.contains("🔴", regex=False).sum())

    c = st.columns(5)
    c[0].markdown(kpi(len(act), "Residentes activos"), unsafe_allow_html=True)
    c[1].markdown(kpi(len(v_hoy), "Signos vitales hoy"), unsafe_allow_html=True)
    c[2].markdown(kpi(crit, "Alertas críticas hoy", "crit" if crit else ""), unsafe_allow_html=True)
    c[3].markdown(kpi(int(sop["Fecha_Hora"].str.startswith(hoy_s).sum()), "Notas SOAPIE hoy"), unsafe_allow_html=True)
    c[4].markdown(kpi(int((kar["Estado"] == "Activo").sum()), "Medicamentos activos"), unsafe_allow_html=True)

    izq, der = st.columns([1.35, 1])
    with izq:
        st.markdown("##### 🚨 Alertas recientes de signos vitales")
        al = vit[vit["Alertas"].str.strip() != ""].sort_values("Fecha_Hora", ascending=False).head(8)
        if al.empty:
            st.caption("Sin alertas registradas.")
        else:
            al = al.merge(res[["Cedula", "Nombre"]], on="Cedula", how="left")
            tabla(al[["Fecha_Hora", "Nombre", "Alertas"]].rename(columns={"Fecha_Hora": "Fecha y hora", "Nombre": "Residente"}))
        st.markdown("##### ⏳ Pendientes de signos vitales hoy")
        pend = act[~act["Cedula"].isin(v_hoy["Cedula"])]
        if act.empty:
            st.caption("Sin residentes activos.")
        elif pend.empty:
            st.markdown(chip("Todos los residentes tienen signos registrados hoy", "ok"), unsafe_allow_html=True)
        else:
            st.markdown("".join(chip(n, "warn") for n in pend["Nombre"]), unsafe_allow_html=True)
    with der:
        st.markdown("##### 🎂 Cumpleaños del mes")
        mes = f"{N.hoy().month:02d}"
        cum = act[act["Fecha_Nacimiento"].str[5:7] == mes].sort_values("Fecha_Nacimiento")
        if cum.empty:
            st.caption("Ningún cumpleaños este mes.")
        for r in cum.itertuples():
            st.markdown(f"🎂 **{h(r.Nombre)}** · día {r.Fecha_Nacimiento[8:10]} · cumple {N.hoy().year - int(r.Fecha_Nacimiento[:4])}")
        st.markdown("##### 📝 Últimas notas")
        ult = sop.sort_values("Fecha_Hora", ascending=False).head(5).merge(res[["Cedula", "Nombre"]], on="Cedula", how="left")
        if ult.empty:
            st.caption("Aún no hay notas.")
        else:
            tabla(ult[["Fecha_Hora", "Nombre", "Turno"]].rename(columns={"Fecha_Hora": "Fecha y hora", "Nombre": "Residente"}))

    with st.expander("🔑 Cambiar mi contraseña"):
        v = st.session_state.f_pw
        with st.form(f"form_pw_{v}"):
            actual = st.text_input("Contraseña actual", type="password", key=f"pw_a_{v}")
            nueva = st.text_input("Nueva contraseña (mínimo 6 caracteres)", type="password", key=f"pw_n_{v}")
            conf = st.text_input("Repetir nueva contraseña", type="password", key=f"pw_c_{v}")
            if st.form_submit_button("Actualizar contraseña", type="primary"):
                if N.autenticar(st.session_state.usuario, actual) is None:
                    st.error("La contraseña actual no es correcta.")
                elif len(nueva) < 6 or nueva != conf:
                    st.error("La nueva contraseña debe tener 6+ caracteres y coincidir en ambos campos.")
                else:
                    N.actualizar("usuarios", "Usuario", st.session_state.usuario, {"Password": N.hash_pw(nueva), "Cambiar_Clave": "NO"})
                    N.log(st.session_state.usuario, "CAMBIO_CLAVE")
                    flash("ok", "✅ Contraseña actualizada.")
                    nueva_version("pw")
                    st.rerun()


# ══════════════════════════════════════════════════════════════
# RESIDENTES
# ══════════════════════════════════════════════════════════════
def pagina_residentes():
    titulo("Residentes", "Admisión, ficha clínica y control de adultos mayores institucionalizados.")
    t1, t2 = st.tabs(["📋 Directorio y ficha", "➕ Nueva admisión"])

    with t1:
        res = N.leer("residentes")
        c1, c2 = st.columns([2, 1])
        q = c1.text_input("🔍 Buscar por nombre o cédula", key="q_res")
        ver = c2.radio("Mostrar", ["Activos", "Egresados", "Todos"], horizontal=True, key="ver_res")
        d = res if ver == "Todos" else res[(res["Estado"] == "Egresado") == (ver == "Egresados")]
        if q.strip():
            d = d[d["Nombre"].str.contains(q.strip(), case=False, regex=False) | d["Cedula"].str.contains(q.strip(), regex=False)]
        if d.empty:
            st.info("No hay residentes que coincidan.")
        else:
            d = d.assign(Edad=d["Fecha_Nacimiento"].map(N.calcular_edad))
            tabla(d[["Cedula", "Nombre", "Edad", "Habitacion", "EPS", "Alergias", "Acudiente_Nombre", "Acudiente_Tel", "Estado"]])
        st.divider()

        ced = selector_residente("dir", solo_activos=False)
        if ced:
            r = ficha(ced)
            ed = ced
            v = st.session_state.f_edit
            with st.form(f"form_edit_{v}"):
                st.markdown("##### ✏️ Editar datos del residente")
                a, b, c = st.columns(3)
                nom = a.text_input("Nombre completo", r["Nombre"], key=f"e_nom_{ed}_{v}")
                sexo = b.selectbox("Sexo", ["Femenino", "Masculino", "Otro"],
                                   index=["Femenino", "Masculino", "Otro"].index(r["Sexo"]) if r["Sexo"] in ("Femenino", "Masculino", "Otro") else 0,
                                   key=f"e_sex_{ed}_{v}")
                hab = c.text_input("Habitación / cama", r["Habitacion"], key=f"e_hab_{ed}_{v}")
                a, b = st.columns(2)
                eps = a.text_input("EPS / medicina prepagada", r["EPS"], key=f"e_eps_{ed}_{v}")
                with b:
                    fn = selector_fecha("Fecha de nacimiento", N.parsear_fecha(r["Fecha_Nacimiento"]) or date(1945, 1, 1), f"e_fn_{ed}_{v}")
                dx = st.text_area("Diagnósticos principales", r["Diagnosticos"], key=f"e_dx_{ed}_{v}", height=80)
                al = st.text_input("Alergias (escriba «Ninguna» si no tiene)", r["Alergias"], key=f"e_al_{ed}_{v}")
                a, b = st.columns(2)
                acn = a.text_input("Familiar / acudiente", r["Acudiente_Nombre"], key=f"e_acn_{ed}_{v}")
                act_ = b.text_input("Teléfono del acudiente", r["Acudiente_Tel"], key=f"e_act_{ed}_{v}")
                if st.form_submit_button("Guardar cambios", type="primary", **KW):
                    if not nom.strip():
                        st.error("El nombre es obligatorio.")
                    elif fn is None:
                        st.error("La fecha de nacimiento no es válida.")
                    else:
                        N.actualizar("residentes", "Cedula", ced, {
                            "Nombre": nom.strip(), "Sexo": sexo, "Habitacion": hab.strip(), "EPS": eps.strip(),
                            "Fecha_Nacimiento": fn.isoformat(), "Diagnosticos": dx.strip(), "Alergias": al.strip(),
                            "Acudiente_Nombre": acn.strip(), "Acudiente_Tel": act_.strip()})
                        N.log(st.session_state.usuario, "EDITA_RESIDENTE", ced)
                        flash("ok", "✅ Datos actualizados.")
                        nueva_version("edit")
                        st.rerun()

            with st.expander("🚪 Egreso / reingreso"):
                if r["Estado"] == "Egresado":
                    st.write(f"Egresó el **{r['F_Egreso']}** · motivo: {r['Motivo_Egreso']}")
                    if st.button("↩️ Reactivar residente", key=f"react_{ced}"):
                        N.actualizar("residentes", "Cedula", ced, {"Estado": "Activo", "F_Egreso": "", "Motivo_Egreso": ""})
                        N.log(st.session_state.usuario, "REACTIVA_RESIDENTE", ced)
                        flash("ok", "✅ Residente reactivado.")
                        st.rerun()
                else:
                    motivo = st.selectbox("Motivo de egreso", ["Traslado a hospital", "Retorno a domicilio",
                                                               "Traslado a otra institución", "Fallecimiento", "Otro"], key=f"mot_{ced}")
                    if st.button("Registrar egreso", key=f"egr_{ced}"):
                        N.actualizar("residentes", "Cedula", ced, {"Estado": "Egresado", "F_Egreso": N.hoy().isoformat(), "Motivo_Egreso": motivo})
                        N.log(st.session_state.usuario, "EGRESO_RESIDENTE", f"{ced} · {motivo}")
                        flash("ok", "✅ Egreso registrado.")
                        st.rerun()

    with t2:
        v = st.session_state.f_adm
        with st.form(f"form_adm_{v}"):
            st.markdown("##### Datos del residente")
            a, b, c = st.columns(3)
            cc = a.text_input("Cédula de ciudadanía", key=f"a_cc_{v}")
            nom = b.text_input("Nombre completo", key=f"a_nom_{v}")
            sexo = c.selectbox("Sexo", ["Femenino", "Masculino", "Otro"], key=f"a_sex_{v}")
            a, b, c = st.columns([1.6, 1, 1])
            with a:
                fn = selector_fecha("Fecha de nacimiento", date(1945, 1, 1), f"a_fn_{v}")
            hab = b.text_input("Habitación / cama", key=f"a_hab_{v}")
            ing = c.date_input("Fecha de ingreso", value=N.hoy(), max_value=N.hoy(), key=f"a_ing_{v}")
            eps = st.text_input("EPS / medicina prepagada", key=f"a_eps_{v}")
            dx = st.text_area("Diagnósticos principales", key=f"a_dx_{v}", height=80)
            al = st.text_input("Alergias (escriba «Ninguna» si no tiene)", key=f"a_al_{v}")
            a, b = st.columns(2)
            acn = a.text_input("Familiar / acudiente", key=f"a_acn_{v}")
            act_ = b.text_input("Teléfono del acudiente", key=f"a_act_{v}")
            if st.form_submit_button("REGISTRAR ADMISIÓN", type="primary", **KW):
                ccl = cc.strip().replace(".", "").replace(" ", "")
                ya = N.leer("residentes")
                if not ccl or not nom.strip():
                    st.error("La cédula y el nombre son obligatorios.")
                elif fn is None:
                    st.error("La fecha de nacimiento no existe o está en el futuro. Revise día, mes y año.")
                elif not al.strip():
                    st.error("Indique las alergias (o escriba «Ninguna»). Es un dato de seguridad del paciente.")
                elif ccl in ya["Cedula"].values:
                    st.error("Ya existe un residente con esa cédula. Si egresó, reactívelo desde el directorio.")
                else:
                    N.agregar("residentes", {
                        "Cedula": ccl, "Nombre": nom.strip(), "Fecha_Nacimiento": fn.isoformat(), "Sexo": sexo,
                        "EPS": eps.strip(), "Habitacion": hab.strip(), "Diagnosticos": dx.strip(), "Alergias": al.strip(),
                        "Acudiente_Nombre": acn.strip(), "Acudiente_Tel": act_.strip(), "Estado": "Activo",
                        "F_Ingreso": ing.isoformat()})
                    N.log(st.session_state.usuario, "ADMISION", f"{ccl} · {nom.strip()}")
                    st.session_state["res_sel"] = ccl
                    flash("ok", f"✅ {nom.strip()} fue admitido/a correctamente.")
                    nueva_version("adm")
                    st.rerun()


# ══════════════════════════════════════════════════════════════
# SIGNOS VITALES
# ══════════════════════════════════════════════════════════════
def pagina_vitales():
    titulo("Signos vitales", "Registro, alertas automáticas y tendencia por residente.")
    ced = selector_residente("vit")
    if not ced:
        return
    ficha(ced)
    v = st.session_state.f_vit
    with st.form(f"form_vit_{v}"):
        st.markdown("##### Nuevo registro")
        c = st.columns(4)
        sis = c[0].number_input("TA sistólica (mmHg)", min_value=40, max_value=260, value=120, step=1, key=f"v_s_{ced}_{v}")
        dia = c[1].number_input("TA diastólica (mmHg)", min_value=20, max_value=160, value=80, step=1, key=f"v_d_{ced}_{v}")
        fc = c[2].number_input("Frecuencia cardíaca (lpm)", min_value=20, max_value=220, value=76, step=1, key=f"v_fc_{ced}_{v}")
        fr = c[3].number_input("Frecuencia respiratoria (rpm)", min_value=5, max_value=60, value=18, step=1, key=f"v_fr_{ced}_{v}")
        c = st.columns(4)
        temp = c[0].number_input("Temperatura (°C)", min_value=30.0, max_value=43.0, value=36.5, step=0.1, format="%.1f", key=f"v_t_{ced}_{v}")
        sat = c[1].number_input("Saturación O₂ (%)", min_value=50, max_value=100, value=95, step=1, key=f"v_o_{ced}_{v}")
        glu = c[2].number_input("Glucemia (mg/dL) · 0 = no medida", min_value=0, max_value=600, value=0, step=1, key=f"v_g_{ced}_{v}")
        dolor = c[3].number_input("Dolor (0-10)", min_value=0, max_value=10, value=0, step=1, key=f"v_p_{ced}_{v}")
        peso = st.number_input("Peso (kg) · 0 = no medido", min_value=0.0, max_value=250.0, value=0.0, step=0.1, format="%.1f", key=f"v_w_{ced}_{v}")
        if st.form_submit_button("GUARDAR SIGNOS VITALES", type="primary", **KW):
            if sis <= dia:
                st.error("La presión sistólica debe ser mayor que la diastólica.")
            else:
                al = N.evaluar_signos(sis, dia, fc, fr, temp, sat, glu, dolor)
                texto = "; ".join(("🔴 " if n == "crit" else "🟡 ") + t for t, n in al)
                N.agregar("signos_vitales", {
                    "ID": N.nueva_id("SV"), "Cedula": ced, "Fecha_Hora": N.fmt_fh(), "TA_Sis": sis, "TA_Dia": dia, "FC": fc,
                    "FR": fr, "Temp": temp, "SatO2": sat, "Glucemia": glu or "", "Dolor": dolor, "Peso": peso or "",
                    "Alertas": texto, "Autor": f"{st.session_state.alias} ({st.session_state.reg})".replace(" ()", "")})
                N.log(st.session_state.usuario, "SIGNOS_VITALES", f"{ced} · {texto or 'sin alertas'}")
                flash("warn" if al else "ok", "⚠️ Registro guardado con alertas: " + texto if al else "✅ Signos vitales guardados. Sin alertas.")
                nueva_version("vit")
                st.rerun()

    vit = N.leer("signos_vitales")
    hist = vit[vit["Cedula"] == ced].sort_values("Fecha_Hora", ascending=False)
    st.markdown("##### Historial")
    if hist.empty:
        st.caption("Este residente aún no tiene registros.")
        return
    tabla(hist[["Fecha_Hora", "TA_Sis", "TA_Dia", "FC", "FR", "Temp", "SatO2", "Glucemia", "Dolor", "Peso", "Alertas", "Autor"]].head(40))
    g = hist.head(30).sort_values("Fecha_Hora").set_index("Fecha_Hora")[["TA_Sis", "TA_Dia", "FC"]].apply(pd.to_numeric, errors="coerce")
    if len(g) >= 2:
        st.markdown("##### Tendencia (últimos 30 registros)")
        st.line_chart(g)


# ══════════════════════════════════════════════════════════════
# KARDEX DE MEDICAMENTOS
# ══════════════════════════════════════════════════════════════
def pagina_kardex():
    titulo("Kardex de medicamentos", "Prescripciones vigentes y registro de cada administración.")
    ced = selector_residente("kar")
    if not ced:
        return
    ficha(ced)
    meds = N.leer("kardex_meds")
    mr = meds[meds["Cedula"] == ced]
    act = mr[mr["Estado"] == "Activo"]
    etq = {r.ID_Med: f"{r.Medicamento} {r.Dosis} · {r.Via} · {r.Frecuencia}" for r in act.itertuples()}

    t1, t2, t3 = st.tabs(["💊 Administrar", "➕ Prescribir / suspender", "🗂 Historial"])
    with t1:
        if act.empty:
            st.info("Este residente no tiene medicamentos activos. Agregue uno en «Prescribir / suspender».")
        else:
            tabla(act[["Medicamento", "Dosis", "Via", "Frecuencia", "Horarios", "Indicaciones"]])
            v = st.session_state.f_adm_med
            with st.form(f"form_admmed_{v}"):
                st.markdown("##### Registrar administración")
                idm = st.selectbox("Medicamento", list(etq), format_func=lambda i: etq[i], key=f"am_m_{ced}_{v}")
                res_ = st.radio("Resultado", ["Administrado", "Rechazado por el residente", "No administrado (otra causa)"],
                                horizontal=True, key=f"am_r_{ced}_{v}")
                obs = st.text_area("Observación (obligatoria si no se administró)", key=f"am_o_{ced}_{v}", height=70)
                if st.form_submit_button("REGISTRAR", type="primary", **KW):
                    if res_ != "Administrado" and not obs.strip():
                        st.error("Explique por qué no se administró.")
                    else:
                        N.agregar("admin_meds", {"ID": N.nueva_id("AD"), "ID_Med": idm, "Cedula": ced, "Fecha_Hora": N.fmt_fh(),
                                                 "Resultado": res_, "Observacion": obs.strip(), "Autor": st.session_state.alias})
                        N.log(st.session_state.usuario, "ADMINISTRA_MED", f"{ced} · {etq[idm]} · {res_}")
                        flash("ok" if res_ == "Administrado" else "warn", f"Registrado: {etq[idm]} → {res_}")
                        nueva_version("adm_med")
                        st.rerun()

    with t2:
        v = st.session_state.f_med
        with st.form(f"form_med_{v}"):
            st.markdown("##### Nueva prescripción")
            a, b, c = st.columns(3)
            med = a.text_input("Medicamento", key=f"m_n_{ced}_{v}")
            dosis = b.text_input("Dosis (ej: 500 mg)", key=f"m_d_{ced}_{v}")
            via = c.selectbox("Vía", ["Oral", "Sublingual", "Intramuscular", "Intravenosa", "Subcutánea", "Tópica", "Inhalada", "Oftálmica", "Rectal"], key=f"m_v_{ced}_{v}")
            a, b = st.columns(2)
            frec = a.selectbox("Frecuencia", ["Cada 4 h", "Cada 6 h", "Cada 8 h", "Cada 12 h", "Cada 24 h", "Dosis única", "Si es necesario (PRN)"], key=f"m_f_{ced}_{v}")
            hor = b.text_input("Horarios (ej: 08:00, 20:00)", key=f"m_h_{ced}_{v}")
            ind = st.text_area("Indicaciones", key=f"m_i_{ced}_{v}", height=70)
            if st.form_submit_button("GUARDAR PRESCRIPCIÓN", type="primary", **KW):
                if not med.strip() or not dosis.strip():
                    st.error("Medicamento y dosis son obligatorios.")
                else:
                    N.agregar("kardex_meds", {"ID_Med": N.nueva_id("MD"), "Cedula": ced, "Medicamento": med.strip(), "Dosis": dosis.strip(),
                                              "Via": via, "Frecuencia": frec, "Horarios": hor.strip(), "Indicaciones": ind.strip(),
                                              "Estado": "Activo", "Prescrito_Por": st.session_state.alias, "F_Inicio": N.hoy().isoformat()})
                    N.log(st.session_state.usuario, "PRESCRIBE", f"{ced} · {med.strip()} {dosis.strip()}")
                    flash("ok", f"✅ {med.strip()} agregado al kardex.")
                    nueva_version("med")
                    st.rerun()
        if not act.empty:
            v2 = st.session_state.f_susp
            with st.form(f"form_susp_{v2}"):
                st.markdown("##### Suspender un medicamento")
                idm = st.selectbox("Medicamento a suspender", list(etq), format_func=lambda i: etq[i], key=f"s_m_{ced}_{v2}")
                if st.form_submit_button("Suspender", **KW):
                    N.actualizar("kardex_meds", "ID_Med", idm, {"Estado": "Suspendido", "F_Suspension": N.hoy().isoformat()})
                    N.log(st.session_state.usuario, "SUSPENDE_MED", f"{ced} · {etq[idm]}")
                    flash("ok", f"Suspendido: {etq[idm]}")
                    nueva_version("susp")
                    st.rerun()

    with t3:
        ad = N.leer("admin_meds")
        ad = ad[ad["Cedula"] == ced].sort_values("Fecha_Hora", ascending=False)
        if ad.empty:
            st.caption("Aún no hay administraciones registradas.")
        else:
            nombres = mr.set_index("ID_Med")["Medicamento"].to_dict()
            ad = ad.assign(Medicamento=ad["ID_Med"].map(nombres).fillna("—"))
            tabla(ad[["Fecha_Hora", "Medicamento", "Resultado", "Observacion", "Autor"]].head(60))
        susp = mr[mr["Estado"] != "Activo"]
        if not susp.empty:
            st.markdown("##### Medicamentos suspendidos")
            tabla(susp[["Medicamento", "Dosis", "Frecuencia", "F_Inicio", "F_Suspension"]])


# ══════════════════════════════════════════════════════════════
# ESCALAS
# ══════════════════════════════════════════════════════════════
def pagina_escalas():
    titulo("Escalas de valoración geriátrica", "Barthel, Braden, Downton y Pfeiffer con interpretación automática.")
    ced = selector_residente("esc")
    if not ced:
        return
    r = ficha(ced)
    edad = N.calcular_edad(r["Fecha_Nacimiento"]) or 0
    nombre = st.selectbox("Escala", list(N.ESCALAS), format_func=lambda k: N.ESCALAS[k]["titulo"], key="esc_sel")
    esc = N.ESCALAS[nombre]
    v = st.session_state.f_esc

    resp = {}
    with st.container(border=True):
        for it in esc["items"]:
            ops = it["o"]
            idx = (1 if edad >= 70 else 0) if it["k"] == "edad70" else 0
            sel = st.radio(it["t"], list(range(len(ops))), index=idx, horizontal=len(ops) <= 4,
                           format_func=lambda i, o=ops: f"{o[i][0]} ({o[i][1]})", key=f"es_{ced}_{nombre}_{it['k']}_{v}")
            resp[it["k"]] = ops[sel][1]
        edu = None
        if nombre == "Pfeiffer":
            edu = st.selectbox("Nivel educativo (ajusta la interpretación)", list(N.EDUCACION), index=1,
                               format_func=lambda k: N.EDUCACION[k], key=f"es_edu_{ced}_{v}")
    puntaje = sum(resp.values())
    texto, nivel = N.interpretar(nombre, puntaje, edu)
    st.markdown(bloque(f"""<div class="puntaje"><div><div class="sub2" style="color:#5F6F85;font-weight:700">PUNTAJE</div>
        <div class="n">{puntaje}</div></div><div>{chip(texto, nivel)}</div></div>"""), unsafe_allow_html=True)

    if st.button("💾 GUARDAR VALORACIÓN", type="primary", key=f"es_save_{nombre}", **KW):
        detalle = "; ".join(f"{k}={p}" for k, p in resp.items()) + (f"; educacion={edu}" if edu else "")
        N.agregar("escalas", {"ID": N.nueva_id("ES"), "Cedula": ced, "Fecha_Hora": N.fmt_fh(), "Escala": nombre,
                              "Puntaje": puntaje, "Interpretacion": texto, "Detalle": detalle, "Autor": st.session_state.alias})
        N.log(st.session_state.usuario, "ESCALA", f"{ced} · {nombre} = {puntaje}")
        flash("ok", f"✅ {nombre}: {puntaje} pts · {texto}")
        nueva_version("esc")
        st.rerun()

    hist = N.leer("escalas")
    hist = hist[(hist["Cedula"] == ced) & (hist["Escala"] == nombre)].sort_values("Fecha_Hora", ascending=False)
    st.markdown(f"##### Historial de {nombre}")
    if hist.empty:
        st.caption("Sin valoraciones previas de esta escala.")
    else:
        tabla(hist[["Fecha_Hora", "Puntaje", "Interpretacion", "Autor"]].head(20))
        g = hist.sort_values("Fecha_Hora").set_index("Fecha_Hora")[["Puntaje"]].apply(pd.to_numeric, errors="coerce")
        if len(g) >= 2:
            st.line_chart(g)


# ══════════════════════════════════════════════════════════════
# NOTAS SOAPIE
# ══════════════════════════════════════════════════════════════
def _turno_actual():
    hh = N.ahora().hour
    return 0 if 7 <= hh < 13 else 1 if 13 <= hh < 19 else 2


def pagina_soapie():
    titulo("Notas de enfermería · SOAPIE", "Evolución clínica con sello digital. Las notas no se editan ni se borran (Res. 1995/1999 y Ley 911/2004).")
    ced = selector_residente("soap", solo_activos=False)
    if not ced:
        return
    r = ficha(ced)
    t1, t2 = st.tabs(["✍️ Nueva nota", "📚 Historial"])
    with t1:
        if r["Estado"] == "Egresado":
            st.warning("Este residente está egresado; no se pueden agregar notas nuevas.")
        else:
            v = st.session_state.f_soap
            with st.form(f"form_soap_{v}"):
                turno = st.selectbox("Turno", ["Mañana (07:00 - 13:00)", "Tarde (13:00 - 19:00)", "Noche (19:00 - 07:00)"],
                                     index=_turno_actual(), key=f"so_t_{ced}_{v}")
                s = st.text_area("S · Subjetivo (lo que refiere el residente o la familia)", key=f"so_s_{ced}_{v}", height=90)
                o = st.text_area("O · Objetivo (examen físico, signos vitales, observación)", key=f"so_o_{ced}_{v}", height=90)
                a = st.text_area("A · Análisis (juicio clínico de enfermería)", key=f"so_a_{ced}_{v}", height=90)
                p = st.text_area("P · Plan (cuidados programados)", key=f"so_p_{ced}_{v}", height=90)
                i = st.text_area("I · Intervención (lo que se realizó)", key=f"so_i_{ced}_{v}", height=90)
                e = st.text_area("E · Evaluación (respuesta del residente)", key=f"so_e_{ced}_{v}", height=90)
                if st.form_submit_button("FIRMAR Y ARCHIVAR NOTA", type="primary", **KW):
                    if not s.strip() or not o.strip():
                        st.error("Subjetivo y Objetivo son obligatorios para firmar la nota.")
                    else:
                        firma = f"{st.session_state.alias} ({st.session_state.reg})".replace(" ()", "")
                        nota = {"ID_Nota": N.nueva_id("SOAPIE"), "Cedula": ced, "Fecha_Hora": N.fmt_fh(), "Turno": turno,
                                "Autor": firma, "Subjetivo": s.strip(), "Objetivo": o.strip(), "Analisis": a.strip(),
                                "Plan": p.strip(), "Intervencion": i.strip(), "Evaluacion": e.strip()}
                        nota["Sello"] = N.sello_nota(nota)
                        N.agregar("notas_soapie", nota)
                        N.log(st.session_state.usuario, "NOTA_SOAPIE", f"{ced} · {nota['ID_Nota']}")
                        flash("ok", f"✅ Nota {nota['ID_Nota']} firmada y archivada. Sello: {nota['Sello']}")
                        nueva_version("soap")
                        st.rerun()
    with t2:
        sop = N.leer("notas_soapie")
        sop = sop[sop["Cedula"] == ced].sort_values("Fecha_Hora", ascending=False)
        if sop.empty:
            st.caption("Este residente aún no tiene notas.")
            return
        st.download_button("⬇️ Descargar historial (CSV)", sop.drop(columns=["Cedula"]).to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"soapie_{ced}.csv", mime="text/csv", key=f"dl_{ced}")
        for n in sop.head(30).to_dict("records"):
            integra = N.sello_nota(n) == n["Sello"]
            with st.expander(f"📝 {n['Fecha_Hora']} · {n['Turno'].split(' (')[0]} · {n['Autor']}"):
                st.markdown(chip("Sello íntegro ✓", "ok") if integra else chip("⚠ El contenido no coincide con el sello", "crit"),
                            unsafe_allow_html=True)
                for etiqueta, campo in [("S · Subjetivo", "Subjetivo"), ("O · Objetivo", "Objetivo"), ("A · Análisis", "Analisis"),
                                        ("P · Plan", "Plan"), ("I · Intervención", "Intervencion"), ("E · Evaluación", "Evaluacion")]:
                    if n[campo].strip():
                        st.markdown(f"**{etiqueta}:** {n[campo]}")
                st.caption(f"ID {n['ID_Nota']} · Sello {n['Sello']}")


# ══════════════════════════════════════════════════════════════
# ADMINISTRACIÓN DEL GERIÁTRICO
# ══════════════════════════════════════════════════════════════
def pagina_admin():
    titulo("Administración", "Usuarios de su geriátrico, auditoría y copia de seguridad.")
    t1, t2, t3 = st.tabs(["👥 Usuarios", "🧾 Auditoría", "🛠 Sistema y respaldo"])
    mx = int(N._num(CLI["Max_Usuarios"])) if CLI else 0
    with t1:
        usr = N.leer("usuarios")
        activos = int((usr["Activo"].str.upper() != "NO").sum())
        lleno = bool(mx) and activos >= mx
        st.markdown(chip(f"Usuarios activos: {activos}" + (f" de {mx} permitidos por su plan" if mx else ""),
                         "warn" if lleno else "ok"), unsafe_allow_html=True)
        tabla(usr.drop(columns=["Password"]))
        v = st.session_state.f_usr
        a, b = st.columns(2)
        with a:
            with st.form(f"form_usr_{v}"):
                st.markdown("##### ➕ Crear usuario")
                u = st.text_input("Usuario (sin espacios)", key=f"u_u_{v}")
                al = st.text_input("Nombre o alias que se mostrará", key=f"u_a_{v}")
                rol = st.selectbox("Rol", ROLES, key=f"u_r_{v}")
                reg = st.text_input("Registro profesional (opcional)", key=f"u_g_{v}")
                pw = st.text_input("Contraseña temporal (mínimo 6)", type="password", key=f"u_p_{v}")
                st.caption("La persona deberá cambiarla en su primer ingreso.")
                if st.form_submit_button("Crear usuario", type="primary", **KW):
                    ul = u.strip().lower()
                    if lleno:
                        st.error(f"Su plan permite {mx} usuarios activos. Desactive uno o solicite ampliar su plan.")
                    elif not ul or " " in ul or len(pw) < 6 or not al.strip():
                        st.error("Complete usuario (sin espacios), alias y una contraseña de 6+ caracteres.")
                    elif ul in usr["Usuario"].str.lower().values:
                        st.error("Ese usuario ya existe.")
                    else:
                        N.agregar("usuarios", {"Usuario": ul, "Password": N.hash_pw(pw), "Rol": rol, "Alias": al.strip(),
                                               "Reg_Profesional": reg.strip(), "Activo": "SI", "Cambiar_Clave": "SI"})
                        N.log(st.session_state.usuario, "CREA_USUARIO", ul)
                        flash("ok", f"✅ Usuario {ul} creado.")
                        nueva_version("usr")
                        st.rerun()
        with b:
            with st.form(f"form_usr2_{v}"):
                st.markdown("##### 🔧 Modificar usuario")
                sel = st.selectbox("Usuario", usr["Usuario"].tolist(), key=f"m_u_{v}")
                nuevo_pw = st.text_input("Nueva contraseña temporal (vacío = no cambiar)", type="password", key=f"m_p_{v}")
                estado = st.radio("Estado", ["Activo", "Inactivo"], horizontal=True, key=f"m_e_{v}")
                if st.form_submit_button("Aplicar cambios", **KW):
                    inactivo_hoy = usr[usr["Usuario"] == sel]["Activo"].str.upper().eq("NO").any()
                    if sel == st.session_state.usuario and estado == "Inactivo":
                        st.error("No puede desactivar su propio usuario.")
                    elif estado == "Activo" and inactivo_hoy and lleno:
                        st.error(f"Su plan permite {mx} usuarios activos. Desactive otro antes de reactivar este.")
                    elif nuevo_pw and len(nuevo_pw) < 6:
                        st.error("La contraseña debe tener 6+ caracteres.")
                    else:
                        cambios = {"Activo": "SI" if estado == "Activo" else "NO"}
                        if nuevo_pw:
                            cambios.update(Password=N.hash_pw(nuevo_pw), Cambiar_Clave="SI")
                        N.actualizar("usuarios", "Usuario", sel, cambios)
                        N.log(st.session_state.usuario, "MODIFICA_USUARIO", f"{sel} · {estado}")
                        flash("ok", f"✅ Usuario {sel} actualizado.")
                        nueva_version("usr")
                        st.rerun()
    with t2:
        lg = N.leer("logs").sort_values("Fecha_Hora", ascending=False)
        q = st.text_input("Filtrar por usuario o acción", key="q_log")
        if q.strip():
            lg = lg[lg["Usuario"].str.contains(q.strip(), case=False, regex=False) | lg["Accion"].str.contains(q.strip(), case=False, regex=False)]
        tabla(lg.head(300))
        st.download_button("⬇️ Descargar auditoría (CSV)", lg.to_csv(index=False).encode("utf-8-sig"), file_name="auditoria.csv", mime="text/csv")
    with t3:
        if N.estado_nube()["conectado"]:
            st.success("✅ Su información se guarda en una bóveda exclusiva de su geriátrico. Ningún otro geriátrico puede verla.")
        else:
            st.info("Modo de demostración local.")
        if CLI:
            vence = CLI["Vence"] or "sin vencimiento"
            st.markdown(f"**Plan:** {h(CLI['Plan'] or '—')} · **Usuarios permitidos:** {mx or '—'} · **Vigente hasta:** {h(vence)}")
        st.markdown("##### 💾 Copia de seguridad (CSV)")
        st.caption("Descargue sus datos cuando quiera: son suyos.")
        cols = st.columns(3)
        for i, t in enumerate([t for t in N.ESQUEMA if t != "usuarios"]):
            cols[i % 3].download_button(f"⬇️ {t}", N.leer(t).to_csv(index=False).encode("utf-8-sig"),
                                        file_name=f"{t}.csv", mime="text/csv", key=f"bk_{t}")


# ══════════════════════════════════════════════════════════════
# PANEL DEL PROPIETARIO
# ══════════════════════════════════════════════════════════════
def _wa(tel):
    d = "".join(ch for ch in str(tel) if ch.isdigit())
    return f"https://wa.me/{d if len(d) > 10 else '57' + d}" if d else ""


def pagina_owner_hub():
    titulo("Panel del propietario", "Suscripciones, clientes e ingresos. Aquí nunca se muestran datos clínicos.")
    regs = N.leer("clientes").to_dict("records")
    con = [r for r in regs if N.estado_servicio(r)[0]]
    sin = [r for r in regs if not N.estado_servicio(r)[0]]
    por_vencer = [r for r in con if N.estado_servicio(r)[2] is not None and N.estado_servicio(r)[2] <= 7]
    mrr = sum(N._num(r["Precio_Mensual"]) for r in con)
    pg = N.leer("pagos")
    mes = pg[pg["Fecha"].str.startswith(N.hoy().strftime("%Y-%m"))]
    cobrado = sum(N._num(x) for x in mes["Monto"])
    c = st.columns(6)
    c[0].markdown(kpi(len(regs), "Geriátricos registrados"), unsafe_allow_html=True)
    c[1].markdown(kpi(len(con), "Con acceso activo"), unsafe_allow_html=True)
    c[2].markdown(kpi(len(sin), "Sin acceso", "crit" if sin else ""), unsafe_allow_html=True)
    c[3].markdown(kpi(len(por_vencer), "Vencen en 7 días", "warn" if por_vencer else ""), unsafe_allow_html=True)
    c[4].markdown(kpi(N.cop(mrr), "Ingreso mensual esperado"), unsafe_allow_html=True)
    c[5].markdown(kpi(N.cop(cobrado), "Cobrado este mes"), unsafe_allow_html=True)
    if not regs:
        st.info("Aún no hay geriátricos. Cree el primero en **Nuevo cliente**.")
        return
    st.markdown("##### 🏢 Todos los geriátricos")
    tabla(pd.DataFrame([{"Geriátrico": r["Nombre"], "Código": r["Codigo"], "Plan": r["Plan"], "Usuarios": r["Max_Usuarios"],
                         "Mensualidad": N.cop(r["Precio_Mensual"]), "Estado": N.etiqueta_servicio(r)[0], "Vence": r["Vence"]}
                        for r in regs]))
    cobrar = [r for r in regs if r in por_vencer or r in sin]
    if cobrar:
        st.markdown("##### 📞 Cobranza")
        for r in cobrar:
            t, n = N.etiqueta_servicio(r)
            w = _wa(r["Telefono"])
            st.markdown(f"{chip(t, n)} **{h(r['Nombre'])}** · {N.cop(r['Precio_Mensual'])}" +
                        (f" · [💬 WhatsApp]({w})" if w else ""), unsafe_allow_html=True)


def pagina_clientes():
    titulo("Clientes", "Estado, pagos, plan y accesos de cada geriátrico.")
    cl = N.leer("clientes")
    if cl.empty:
        st.info("Aún no hay geriátricos. Cree el primero en **Nuevo cliente**.")
        return
    etq = {r.Codigo: f"{r.Nombre} · {r.Codigo}" for r in cl.itertuples()}
    cod = st.selectbox("Geriátrico", list(etq), format_func=lambda c: etq[c], key="cli_sel")
    cli = N.buscar_cliente(cod)
    txt, niv = N.etiqueta_servicio(cli)
    st.markdown(bloque(f"""<div class="ficha"><div class="avatar">🏢</div><div>
        <div class="nom">{h(cli['Nombre'])} {chip(txt, niv)}</div>
        <div class="sub2">Código <b>{h(cli['Codigo'])}</b> · Plan {h(cli['Plan'] or '—')} · {h(cli['Max_Usuarios'] or '—')} usuarios ·
        {N.cop(cli['Precio_Mensual'])}/mes · Vence {h(cli['Vence'] or '—')}</div>
        <div class="sub2">{h(cli['Contacto'])} {h(cli['Telefono'])} {h(cli['Email'])}</div></div>
        <div class="der">{chip(cli['Modo_Boveda'] or 'Central', 'ok')}</div></div>"""), unsafe_allow_html=True)
    actor = st.session_state.usuario
    t1, t2, t3, t4 = st.tabs(["💳 Estado y pagos", "📝 Plan y datos", "👥 Accesos", "🗄 Bóveda"])

    with t1:
        v = st.session_state.f_cli_pago
        with st.form(f"form_pago_{cod}_{v}"):
            st.markdown("##### Registrar pago (extiende la vigencia y reactiva el acceso)")
            a, b, c = st.columns(3)
            monto = a.number_input("Monto (COP)", min_value=0.0, value=float(N._num(cli["Precio_Mensual"])), step=1000.0, key=f"p_m_{cod}_{v}")
            meses = b.number_input("Meses que cubre", min_value=1, max_value=24, value=1, step=1, key=f"p_n_{cod}_{v}")
            metodo = c.selectbox("Método", ["Transferencia", "Nequi", "Daviplata", "Efectivo", "Otro"], key=f"p_t_{cod}_{v}")
            nota = st.text_input("Nota (opcional)", key=f"p_o_{cod}_{v}")
            if st.form_submit_button("REGISTRAR PAGO", type="primary", **KW):
                nueva = N.registrar_pago(cod, monto, meses, metodo, nota, actor)
                flash("ok", f"✅ Pago registrado. {cli['Nombre']} tiene acceso hasta el {nueva.strftime('%d/%m/%Y')}.")
                nueva_version("cli_pago")
                st.rerun()
        v2 = st.session_state.f_cli_estado
        with st.form(f"form_estado_{cod}_{v2}"):
            if cli["Estado"] == "Activo":
                st.markdown("##### ⛔ Suspender acceso (inmediato, incluso para quienes ya están dentro)")
                motivo = st.text_input("Motivo (ej: falta de pago)", key=f"s_m_{cod}_{v2}")
                if st.form_submit_button("Suspender ahora", **KW):
                    N.actualizar("clientes", "Codigo", cod, {"Estado": "Suspendido", "Notas": (cli["Notas"] + " | " if cli["Notas"] else "") + f"{N.hoy()} suspendido: {motivo}"})
                    N.log_control(actor, "SUSPENDE", f"{cod} · {motivo}")
                    flash("warn", f"⛔ {cli['Nombre']} fue suspendido.")
                    nueva_version("cli_estado")
                    st.rerun()
            else:
                st.markdown("##### ✅ Reactivar acceso")
                st.caption("Si el vencimiento ya pasó, registre un pago o extienda la fecha en «Plan y datos».")
                if st.form_submit_button("Reactivar", type="primary", **KW):
                    N.actualizar("clientes", "Codigo", cod, {"Estado": "Activo"})
                    N.log_control(actor, "REACTIVA", cod)
                    flash("ok", f"✅ {cli['Nombre']} fue reactivado.")
                    nueva_version("cli_estado")
                    st.rerun()
        pg = N.leer("pagos")
        pg = pg[pg["Codigo"] == cod].sort_values("Fecha", ascending=False)
        st.markdown("##### Historial de pagos")
        if pg.empty:
            st.caption("Sin pagos registrados.")
        else:
            tabla(pg[["Fecha", "Monto", "Metodo", "Periodo", "Nota"]])

    with t2:
        v = st.session_state.f_cli_ed
        with st.form(f"form_cli_ed_{cod}_{v}"):
            a, b, c = st.columns(3)
            nom = a.text_input("Nombre del geriátrico", cli["Nombre"], key=f"c_n_{cod}_{v}")
            nit = b.text_input("NIT", cli["NIT"], key=f"c_nit_{cod}_{v}")
            plan = c.selectbox("Plan", ["Básico", "Estándar", "Pro", "Personalizado"],
                               index=["Básico", "Estándar", "Pro", "Personalizado"].index(cli["Plan"]) if cli["Plan"] in ("Básico", "Estándar", "Pro", "Personalizado") else 0,
                               key=f"c_pl_{cod}_{v}")
            a, b, c = st.columns(3)
            con_ = a.text_input("Contacto", cli["Contacto"], key=f"c_c_{cod}_{v}")
            tel = b.text_input("Teléfono / WhatsApp", cli["Telefono"], key=f"c_t_{cod}_{v}")
            mail = c.text_input("Email", cli["Email"], key=f"c_e_{cod}_{v}")
            a, b, c = st.columns(3)
            mxu = a.number_input("Máximo de usuarios activos", min_value=1, max_value=1000, value=max(1, int(N._num(cli["Max_Usuarios"], 5))), step=1, key=f"c_mx_{cod}_{v}")
            precio = b.number_input("Mensualidad (COP)", min_value=0.0, value=float(N._num(cli["Precio_Mensual"])), step=1000.0, key=f"c_pr_{cod}_{v}")
            gr = c.number_input("Días de gracia", min_value=0, max_value=60, value=int(N._num(cli["Dias_Gracia"])), step=1, key=f"c_g_{cod}_{v}")
            a, b = st.columns(2)
            sin_v = a.checkbox("Sin fecha de vencimiento", value=not cli["Vence"], key=f"c_sv_{cod}_{v}")
            vence = b.date_input("Vigente hasta", value=N.parsear_fecha(cli["Vence"]) or N.hoy(), key=f"c_v_{cod}_{v}")
            if st.form_submit_button("Guardar cambios", type="primary", **KW):
                if not nom.strip():
                    st.error("El nombre es obligatorio.")
                else:
                    N.actualizar("clientes", "Codigo", cod, {"Nombre": nom.strip(), "NIT": nit.strip(), "Plan": plan, "Contacto": con_.strip(),
                                                             "Telefono": tel.strip(), "Email": mail.strip(), "Max_Usuarios": mxu, "Precio_Mensual": precio,
                                                             "Dias_Gracia": gr, "Vence": "" if sin_v else vence.isoformat()})
                    N.log_control(actor, "EDITA_CLIENTE", cod)
                    flash("ok", "✅ Datos del cliente actualizados.")
                    nueva_version("cli_ed")
                    st.rerun()

    with t3:
        st.caption("Como propietario usted ve solo los usuarios del geriátrico. Los datos clínicos no se muestran en este panel.")
        if not N.abrir_tenant(_cfg(), cli):
            st.error("No se pudo abrir la bóveda de este cliente.")
            st.code(N.estado_nube(cod)["error"] or "")
        else:
            usr = N.leer("usuarios", tid=cod)
            tabla(usr.drop(columns=["Password"]))
            v = st.session_state.f_cli_pw
            with st.form(f"form_cli_pw_{cod}_{v}"):
                st.markdown("##### 🔑 Restablecer clave de un usuario del cliente")
                sel = st.selectbox("Usuario", usr["Usuario"].tolist(), key=f"r_u_{cod}_{v}")
                pw = st.text_input("Clave temporal", value=N.clave_temporal(), key=f"r_p_{cod}_{v}")
                st.caption("Se le pedirá cambiarla al ingresar. Entréguesela al cliente por un canal seguro.")
                if st.form_submit_button("Restablecer", **KW):
                    if len(pw) < 6:
                        st.error("Mínimo 6 caracteres.")
                    else:
                        N.actualizar("usuarios", "Usuario", sel, {"Password": N.hash_pw(pw), "Cambiar_Clave": "SI", "Activo": "SI"}, tid=cod)
                        N.log_control(actor, "RESET_CLAVE_CLIENTE", f"{cod} · {sel}")
                        flash("ok", f"✅ Clave de {sel} restablecida. Clave temporal: {pw}")
                        nueva_version("cli_pw")
                        st.rerun()

    with t4:
        st.markdown(f"**Modo:** {h(cli['Modo_Boveda'] or 'Central')}")
        if cli["Carpeta_URL"]:
            st.markdown(f"[📁 Abrir carpeta del cliente en Drive]({cli['Carpeta_URL']})")
        if cli["Sheet_ID"]:
            st.markdown(f"[📄 Abrir base de datos](https://docs.google.com/spreadsheets/d/{cli['Sheet_ID']})")
            st.caption("Abrir la hoja es solo para soporte técnico: contiene datos clínicos del cliente.")
        if st.button("🔌 Probar conexión con la bóveda", key=f"probar_{cod}"):
            if N.abrir_tenant(_cfg(), cli, forzar=True):
                st.success("✅ La bóveda responde correctamente.")
            else:
                st.error("No se pudo conectar:")
                st.code(N.estado_nube(cod)["error"] or "")
        v = st.session_state.f_cli_vault
        with st.form(f"form_vault_{cod}_{v}"):
            nuevo = st.text_input("Cambiar ID de la hoja (bóveda propia del cliente)", cli["Sheet_ID"], key=f"v_s_{cod}_{v}")
            st.caption("La hoja debe estar compartida como Editor con la cuenta de servicio. No mueve datos: solo cambia a dónde apunta.")
            if st.form_submit_button("Guardar ID", **KW):
                N.actualizar("clientes", "Codigo", cod, {"Sheet_ID": nuevo.strip(), "Modo_Boveda": "Propia del cliente" if nuevo.strip() != cli["Sheet_ID"] else cli["Modo_Boveda"]})
                N.log_control(actor, "CAMBIA_BOVEDA", cod)
                flash("ok", "✅ Bóveda actualizada.")
                nueva_version("cli_vault")
                st.rerun()


def pagina_nuevo_cliente():
    titulo("Nuevo cliente", "Cree un geriátrico: se genera su código, su bóveda propia y su primer administrador.")
    ent = st.session_state.get("nuevo_cliente")
    if ent:
        st.success(f"✅ {ent['nombre']} fue creado. **Esta es la única vez que verá la contraseña temporal.**")
        st.code(f"🏥 Geriatría OS — Acceso de {ent['nombre']}\nCódigo del geriátrico: {ent['codigo']}\nUsuario: {ent['usuario']}\n"
                f"Contraseña temporal: {ent['clave']}\n(Deberá cambiarla en su primer ingreso)", language="text")
        if st.button("Entendido, crear otro", key="ent_ok"):
            st.session_state.pop("nuevo_cliente")
            st.rerun()
        return
    v = st.session_state.f_cli_new
    with st.form(f"form_nuevo_{v}"):
        st.markdown("##### Datos del geriátrico")
        a, b, c = st.columns(3)
        nom = a.text_input("Nombre del geriátrico", key=f"n_n_{v}")
        nit = b.text_input("NIT", key=f"n_nit_{v}")
        plan = c.selectbox("Plan", ["Básico", "Estándar", "Pro", "Personalizado"], key=f"n_pl_{v}")
        a, b, c = st.columns(3)
        con_ = a.text_input("Persona de contacto", key=f"n_c_{v}")
        tel = b.text_input("Teléfono / WhatsApp", key=f"n_t_{v}")
        mail = c.text_input("Email", key=f"n_e_{v}")
        st.markdown("##### Suscripción")
        a, b, c, d = st.columns(4)
        mxu = a.number_input("Máx. usuarios activos", min_value=1, max_value=1000, value=5, step=1, key=f"n_mx_{v}")
        precio = b.number_input("Mensualidad (COP)", min_value=0.0, value=0.0, step=1000.0, key=f"n_pr_{v}")
        vence = c.date_input("Vigente hasta", value=N.sumar_meses(N.hoy(), 1), key=f"n_v_{v}")
        gr = d.number_input("Días de gracia", min_value=0, max_value=60, value=3, step=1, key=f"n_g_{v}")
        st.markdown("##### Bóveda de datos")
        modo = st.radio("¿Dónde se guardan sus datos?", ["Central", "Propia del cliente"], horizontal=True, key=f"n_m_{v}",
                        help="Central: carpeta y hoja propias del cliente dentro de SU Drive (el propietario). Propia: el cliente crea una hoja en su Drive y la comparte con la cuenta de servicio.")
        sid = st.text_input("ID de la hoja del cliente (solo modo «Propia del cliente»)", key=f"n_s_{v}")
        st.markdown("##### Primer administrador del geriátrico")
        a, b = st.columns(2)
        au = a.text_input("Usuario", value="admin", key=f"n_au_{v}")
        ap = b.text_input("Contraseña temporal", value=N.clave_temporal(), key=f"n_ap_{v}")
        enviado = st.form_submit_button("CREAR GERIÁTRICO", type="primary", **KW)
    if enviado:
        au_l = au.strip().lower()
        if not nom.strip() or not au_l or " " in au_l or len(ap) < 6:
            st.error("Complete el nombre, un usuario sin espacios y una contraseña temporal de 6+ caracteres.")
            return
        datos = {"Nombre": nom.strip(), "NIT": nit.strip(), "Contacto": con_.strip(), "Telefono": tel.strip(), "Email": mail.strip(),
                 "Plan": plan, "Max_Usuarios": mxu, "Precio_Mensual": precio, "Vence": vence.isoformat(), "Dias_Gracia": gr,
                 "Modo_Boveda": modo, "Sheet_ID": sid.strip()}
        codigo, error = None, None
        try:
            codigo = N.crear_cliente(_cfg(), datos, au_l, ap, st.session_state.usuario)
        except Exception as e:  # incluye fallos de Drive al crear la bóveda
            error = e
        if error is not None:
            st.error(f"No se pudo completar la creación: {error}")
            return
        st.session_state["nuevo_cliente"] = {"nombre": nom.strip(), "codigo": codigo, "usuario": au_l, "clave": ap}
        nueva_version("cli_new")
        st.rerun()


def pagina_pagos():
    titulo("Pagos", "Historial de cobros de todos los geriátricos.")
    pg = N.leer("pagos").sort_values("Fecha", ascending=False)
    if pg.empty:
        st.info("Aún no hay pagos registrados. Se registran desde **Clientes ▸ Estado y pagos**.")
        return
    nombres = N.leer("clientes").set_index("Codigo")["Nombre"].to_dict()
    pg = pg.assign(Geriatrico=pg["Codigo"].map(nombres).fillna("—"), Valor=pg["Monto"].map(N._num))
    st.markdown(kpi(N.cop(pg["Valor"].sum()), "Total cobrado (histórico)"), unsafe_allow_html=True)
    por_mes = pg.assign(Mes=pg["Fecha"].str[:7]).groupby("Mes")["Valor"].sum().sort_index()
    if len(por_mes) >= 1:
        st.markdown("##### Cobrado por mes (COP)")
        st.bar_chart(por_mes)
    tabla(pg[["Fecha", "Geriatrico", "Codigo", "Monto", "Metodo", "Periodo", "Nota", "Registrado_Por"]])
    st.download_button("⬇️ Descargar pagos (CSV)", pg.drop(columns=["Valor"]).to_csv(index=False).encode("utf-8-sig"),
                       file_name="pagos.csv", mime="text/csv")


def pagina_owner_sistema():
    titulo("Sistema", "Conexión con Google, configuración y auditoría del panel.")
    t1, t2 = st.tabs(["🔌 Conexión", "🧾 Auditoría"])
    with t1:
        e = N.estado_control()
        if e["conectado"]:
            st.success(f"✅ Conectado a la hoja de control (modo {e['modo'] or 'demo'}).")
            if e["libro_url"]:
                st.markdown(f"[📄 Abrir hoja de control]({e['libro_url']})")
        else:
            st.error("❌ Sin conexión con Google. La app está en modo de demostración local.")
            st.code(e["error"] or "Aún no se ha intentado conectar.")
            st.markdown(
                "- **Falta la hoja OS_Control / 404**: créela en su Drive y compártala como Editor con el correo de la cuenta de servicio.\n"
                "- **API has not been used / disabled**: active *Google Drive API* y *Google Sheets API*.\n"
                "- **Sin espacio (storageQuota)**: la cuenta de servicio no puede crear archivos; use el modo «Propia del cliente» o cree las hojas a mano.")
        if st.button("🔄 Reintentar conexión", key="reconectar"):
            N.conectar(_cfg(), forzar=True)
            st.rerun()
        with st.expander("Ejemplo de Secrets (Streamlit Cloud ▸ Settings ▸ Secrets)"):
            st.code('owner_user = "tu-usuario"\n'
                    'owner_password = "una-clave-larga-y-segura"      # o usa owner_password_hash\n'
                    'google_folder_id = "ID de tu carpeta de Drive donde se crean las bóvedas"\n'
                    '# control_sheet_id = "ID de la hoja OS_Control (opcional)"\n\n'
                    '[gcp_service_account]\n'
                    'type = "service_account"\n'
                    'project_id = "geriatria-os"\n'
                    'private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"\n'
                    'client_email = "geriatria@geriatria-os.iam.gserviceaccount.com"\n'
                    'token_uri = "https://oauth2.googleapis.com/token"', language="toml")
        with st.expander("Generar hash de contraseña (más seguro que dejarla en texto)"):
            pw = st.text_input("Contraseña a convertir", type="password", key="gen_hash")
            if pw:
                st.code(f'owner_password_hash = "{N.hash_pw(pw)}"', language="toml")
    with t2:
        lg = N.leer("logs_control").sort_values("Fecha_Hora", ascending=False)
        tabla(lg.head(300))


# ══════════════════════════════════════════════════════════════
# ENRUTADOR
# ══════════════════════════════════════════════════════════════
RUTAS = {"Hub": pagina_hub, "Residentes": pagina_residentes, "Vitales": pagina_vitales, "Kardex": pagina_kardex,
         "Escalas": pagina_escalas, "SOAPIE": pagina_soapie, "Admin": pagina_admin,
         "OwnerHub": pagina_owner_hub, "Clientes": pagina_clientes, "NuevoCliente": pagina_nuevo_cliente,
         "Pagos": pagina_pagos, "OwnerSistema": pagina_owner_sistema}

try:
    RUTAS.get(st.session_state.pagina, PAGINAS[0][0] and RUTAS[PAGINAS[0][0]])()
except N.ErrorNube as err:
    st.error(f"⚠️ Problema con la bóveda de datos: {err}")
    st.caption("Sus datos no se perdieron. Espere unos segundos y vuelva a intentar la acción.")
