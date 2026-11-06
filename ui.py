# -*- coding: utf-8 -*-
"""
ui.py · Geriatría OS
Estilos y piezas de interfaz compartidas. Pensado para que lo use cualquier persona del equipo
(incluida quien no terminó el bachillerato): letras grandes, botones enormes, colores por sección,
emojis y pasos numerados.
"""
import html
import urllib.parse
from datetime import date

import streamlit as st

import nucleo as N

h = html.escape

try:
    _VER = tuple(int(x) for x in st.__version__.split(".")[:2])
except Exception:
    _VER = (0, 0)
KW = {"width": "stretch"} if _VER >= (1, 50) else {"use_container_width": True}

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# Color de cada sección: (principal, oscuro, fondo suave, emoji)
SECCIONES = {
    "Enfermeria": ("#0F9D7A", "#0A7A5E", "#E3F6EF", "🩺"),
    "Cocina": ("#E8833A", "#C4631C", "#FFF0E3", "🍳"),
    "Aseo": ("#2F80ED", "#1E5FBF", "#E6F0FE", "🧹"),
    "Familias": ("#8E5BD9", "#6E3FB8", "#F1EAFB", "👨‍👩‍👧"),
    "Admin": ("#16325C", "#0B1F3A", "#E8EEF7", "⚙️"),
    "Owner": ("#C9A227", "#9B7C10", "#FBF4DA", "🏢"),
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');
:root{--navy:#0B1F3A;--navy2:#16325C;--acc:#0F9D7A;--acc2:#0A7A5E;--soft:#E3F6EF;--gold:#C9A227;
--bg:#F3F6FA;--ink:#1B2A3F;--muted:#55657C;--line:#D6DEE9;--r:18px}
html{font-size:17px}
.stApp, .stApp p, .stApp label, .stApp li, .stApp td, .stApp th, .stApp input, .stApp textarea,
.stApp button, .stApp [data-baseweb="select"] {font-family:'Plus Jakarta Sans',sans-serif}
.stApp{background:linear-gradient(180deg,#E8EFF7 0%,var(--bg) 260px);color:var(--ink)}
.stApp h1,.stApp h2,.stApp h3{font-family:'Fraunces',serif;color:var(--navy);font-weight:700}
.stApp h5{color:var(--navy);font-weight:800;font-size:1.15rem}
.block-container{padding:1.6rem 2rem 4rem!important;max-width:1400px}
#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important}
[data-testid="stHeader"]{background:transparent}

/* Cabecera de cada sección */
.banner{border-radius:22px;padding:18px 24px;margin:0 0 18px;display:flex;gap:18px;align-items:center;
 background:linear-gradient(135deg,var(--acc),var(--acc2));color:#fff;box-shadow:0 14px 30px -14px var(--acc)}
.banner .em{font-size:3rem;line-height:1;background:rgba(255,255,255,.2);border-radius:18px;padding:10px 14px}
.banner .t{font-family:'Fraunces',serif;font-size:1.9rem;font-weight:700;line-height:1.1}
.banner .s{opacity:.92;font-size:1rem;margin-top:3px}

/* Barra lateral */
[data-testid="stSidebar"]{background:linear-gradient(180deg,var(--navy) 0%,var(--navy2) 100%)}
[data-testid="stSidebar"] *{color:#E6EDF7}
.sb-brand{font-family:'Fraunces',serif;font-size:1.5rem;font-weight:700;color:#fff;margin:.2rem 0 .9rem}
.sb-user{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);border-radius:14px;padding:10px 14px;margin-bottom:1rem}
.sb-tenant{color:#9FB3CC;font-size:.85rem;font-weight:600;margin:-.6rem 0 .9rem}
.sb-alias{font-weight:800;color:#fff;font-size:1.05rem}.sb-rol{font-size:.82rem;color:#C9A227;font-weight:700}
[data-testid="stSidebar"] button[kind="secondary"],[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]{
 background:rgba(255,255,255,.07)!important;border:1px solid rgba(255,255,255,.14)!important;color:#fff!important;
 justify-content:flex-start;box-shadow:none!important;min-height:3rem}
[data-testid="stSidebar"] button[kind="secondary"]:hover{background:rgba(255,255,255,.18)!important}
[data-testid="stSidebar"] button[kind="primary"],[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]{
 background:#fff!important;color:var(--navy)!important;justify-content:flex-start;border:none!important;min-height:3rem}
[data-testid="stSidebar"] button[kind="primary"] p,[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] p{color:var(--navy)!important}

/* Botones GRANDES */
.stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button,.stLinkButton>a{
 border-radius:14px;font-weight:800;font-size:1.05rem;padding:.7rem 1.2rem;min-height:3.1rem;transition:all .15s ease}
button[kind="primary"],button[kind="primaryFormSubmit"],button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"]{
 background:linear-gradient(135deg,var(--acc),var(--acc2))!important;color:#fff!important;border:none!important;
 box-shadow:0 8px 18px -8px var(--acc)!important}
button[kind="primary"] p,button[kind="primaryFormSubmit"] p,button[data-testid="stBaseButton-primary"] p,button[data-testid="stBaseButton-primaryFormSubmit"] p{color:#fff!important}
button[kind="secondary"],button[kind="secondaryFormSubmit"],button[data-testid="stBaseButton-secondary"],button[data-testid="stBaseButton-secondaryFormSubmit"],.stLinkButton>a{
 background:#fff;color:var(--navy);border:2px solid var(--line)}
.stButton>button:hover,.stLinkButton>a:hover{transform:translateY(-2px);border-color:var(--acc)}
.stButton>button:active{transform:scale(.98)}

/* Azulejos del inicio */
[class*="st-key-tile_"] button{min-height:7.2rem!important;font-size:1.25rem!important;border-radius:22px!important;
 background:#fff!important;border:2px solid var(--line)!important;color:var(--navy)!important;white-space:normal;
 box-shadow:0 10px 24px -14px rgba(11,31,58,.35)!important}
[class*="st-key-tile_"] button p{font-size:1.25rem!important;color:var(--navy)!important;line-height:1.3}
[class*="st-key-tile_"] button:hover{border-color:var(--acc)!important;background:var(--soft)!important}

/* Botones de acción rápida en filas (Dar medicamento, etc.) */
[class*="st-key-dar_"] button{background:linear-gradient(135deg,#0F9D7A,#0A7A5E)!important;color:#fff!important;border:none!important;min-height:3.4rem}
[class*="st-key-dar_"] button p{color:#fff!important;font-size:1.1rem!important}

/* Campos */
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="select"]>div{
 background:#fff!important;border-radius:12px!important;border:2px solid #AAB7C8!important}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within,[data-baseweb="select"]:focus-within>div{
 border-color:var(--acc)!important;box-shadow:0 0 0 4px var(--soft)!important}
.stApp input,.stApp textarea{color:#0F172A!important;font-weight:500;font-size:1.02rem!important}
[data-testid="stWidgetLabel"] p,.stApp label p{color:var(--navy)!important;font-weight:700!important;font-size:1rem!important}
[data-testid="stRadio"] label{background:#fff;border:2px solid var(--line);border-radius:12px;padding:6px 14px;margin:2px 4px 2px 0}
[data-testid="stRadio"] label:has(input:checked){background:var(--soft);border-color:var(--acc)}

/* Formularios y pestañas */
[data-testid="stForm"]{background:#fff;border:1px solid var(--line)!important;border-radius:var(--r)!important;
 padding:22px 24px!important;box-shadow:0 10px 28px -12px rgba(11,31,58,.14)}
button[data-baseweb="tab"]{height:3.2rem;padding:0 18px}
button[data-baseweb="tab"] p{font-weight:800;font-size:1.05rem}
button[data-baseweb="tab"][aria-selected="true"]{background:var(--soft);border-radius:12px 12px 0 0}
[data-baseweb="tab-highlight"]{background:var(--acc)!important;height:4px!important}

/* Tarjetas */
.kpi{background:#fff;border:1px solid var(--line);border-left:6px solid var(--acc);border-radius:var(--r);
 padding:16px 18px;box-shadow:0 8px 22px -10px rgba(11,31,58,.18);margin-bottom:10px}
.kpi .n{font-family:'Fraunces',serif;font-size:2.3rem;font-weight:700;color:var(--navy);line-height:1}
.kpi .l{color:var(--muted);font-size:.9rem;font-weight:700;margin-top:6px}
.kpi.warn{border-left-color:var(--gold)}.kpi.crit{border-left-color:#D64545}
.ficha{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:14px 20px;margin:4px 0 16px;
 display:flex;gap:16px;align-items:center;flex-wrap:wrap;box-shadow:0 8px 22px -12px rgba(11,31,58,.18)}
.avatar{width:58px;height:58px;border-radius:50%;background:linear-gradient(135deg,var(--acc),var(--navy2));color:#fff;
 display:flex;align-items:center;justify-content:center;font-weight:800;font-size:1.2rem;flex:none}
.ficha .nom{font-weight:800;font-size:1.2rem;color:var(--navy)}
.ficha .sub2{color:var(--muted);font-size:.9rem;margin-top:2px}
.ficha .der{margin-left:auto;text-align:right}
.chip{display:inline-block;padding:5px 13px;border-radius:999px;font-size:.85rem;font-weight:800;margin:2px 4px 2px 0}
.chip-ok{background:#E3F6EF;color:#0A7A5E}.chip-warn{background:#FFF3D6;color:#8A6A00}.chip-crit{background:#FDECEC;color:#A12828}
.chip-info{background:#E6F0FE;color:#1E5FBF}
.puntaje{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:16px 20px;margin:10px 0;display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.puntaje .n{font-family:'Fraunces',serif;font-size:2.4rem;font-weight:700;color:var(--navy)}
.aviso{border-radius:16px;padding:14px 18px;margin:8px 0;font-weight:700;font-size:1.02rem;border-left:7px solid}
.aviso.crit{background:#FDECEC;border-color:#D64545;color:#8F1F1F}.aviso.warn{background:#FFF3D6;border-color:#E0A800;color:#7A5C00}
.aviso.ok{background:#E3F6EF;border-color:#0F9D7A;color:#0A6B52}.aviso.info{background:#E6F0FE;border-color:#2F80ED;color:#1E4F9A}
.dosis{background:#fff;border:2px solid var(--line);border-radius:18px;padding:12px 16px;margin:8px 0}
.dosis.Atrasado{border-color:#D64545;background:#FFF6F6}.dosis.Ahora{border-color:#E0A800;background:#FFFBEA}
.dosis.Dado{border-color:#9BD8C4;background:#F4FBF8}.dosis.No-dado{border-color:#E7B4B4;background:#FFF6F6}
.dosis .hora{font-family:'Fraunces',serif;font-size:1.9rem;font-weight:700;color:var(--navy);line-height:1}
.dosis .med{font-size:1.12rem;font-weight:800;color:var(--navy)}.dosis .det{color:var(--muted);font-size:.93rem}
.login-logo{text-align:center;font-size:3.8rem;margin-top:2.4rem}
.login-sub{text-align:center;color:var(--muted);margin:-.2rem 0 1rem;font-size:1.02rem}
.term{background:#0D1117;color:#C9D1D9;border-radius:14px;padding:14px 18px;font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;
 font-size:.82rem;line-height:1.65;max-height:520px;overflow:auto;border:1px solid #30363D;white-space:pre-wrap;word-break:break-word}
.term .t{color:#7D8590}.term .u{color:#58A6FF;font-weight:700}.term .c{color:#E3B341}.term .d{color:#3FB950}
.term .s{color:#F85149;font-weight:700}.term .v{color:#A5A5FF}
</style>
"""


def inyectar_css(seccion="Enfermeria"):
    p, o, soft, _ = SECCIONES.get(seccion, SECCIONES["Enfermeria"])
    st.markdown(CSS + f"<style>:root{{--acc:{p};--acc2:{o};--soft:{soft}}}</style>", unsafe_allow_html=True)


# ── piezas ─────────────────────────────────────────────────────
def bloque(s):
    """HTML en una sola línea (evita que Markdown lo tome como código)."""
    return "".join(l.strip() for l in s.strip().splitlines())


def cfg():
    try:
        return dict(st.secrets)
    except Exception:
        return {}


def cli():
    return st.session_state.get("_cli")


def rol():
    return st.session_state.get("rol", "")


def quien():
    return st.session_state.get("alias", "")


def firma():
    return f"{st.session_state.alias} ({st.session_state.reg})".replace(" ()", "")


def banner(seccion, titulo, sub=""):
    _, _, _, em = SECCIONES.get(seccion, SECCIONES["Enfermeria"])
    st.markdown(bloque(f"<div class='banner'><div class='em'>{em}</div><div><div class='t'>{h(titulo)}</div>"
                       f"<div class='s'>{h(sub)}</div></div></div>"), unsafe_allow_html=True)


def kpi(n, etiqueta, tono=""):
    return f"<div class='kpi {tono}'><div class='n'>{n}</div><div class='l'>{h(etiqueta)}</div></div>"


def chip(texto, nivel="ok"):
    return f"<span class='chip chip-{nivel}'>{h(texto)}</span>"


def aviso(texto, nivel="warn"):
    st.markdown(f"<div class='aviso {nivel}'>{h(texto)}</div>", unsafe_allow_html=True)


def flash(tipo, msg):
    st.session_state["_flash"] = (tipo, msg)


def mostrar_flash():
    f = st.session_state.pop("_flash", None)
    if f:
        aviso(f[1], {"ok": "ok", "warn": "warn", "err": "crit"}[f[0]])


def ver(form):
    """Contador que se incrementa tras guardar: así el formulario queda limpio."""
    return st.session_state.setdefault(f"f_{form}", 0)


def nueva_version(form):
    st.session_state[f"f_{form}"] = ver(form) + 1


def ayuda(pasos, titulo="❓ ¿Cómo se hace? (toque aquí)"):
    with st.expander(titulo):
        for i, p in enumerate(pasos, 1):
            st.markdown(f"**{i}.** {p}")


def tabla(df, **kw):
    st.dataframe(df, hide_index=True, **KW, **kw)


def enlace(etiqueta, url, key=None):
    if hasattr(st, "link_button"):
        st.link_button(etiqueta, url, **KW)
    else:
        st.markdown(f"[{etiqueta}]({url})")


def wa_link(tel, texto=""):
    d = "".join(ch for ch in str(tel) if ch.isdigit())
    if not d:
        return ""
    d = d if len(d) > 10 else "57" + d
    return f"https://wa.me/{d}" + (f"?text={urllib.parse.quote(texto)}" if texto else "")


def selector_fecha(etiqueta, defecto, clave):
    """Día / Mes / Año en listas: mucho más cómodo que el calendario para años antiguos."""
    st.markdown(f"<p style='margin:0 0 4px;font-weight:700;font-size:1rem;color:#0B1F3A'>{etiqueta}</p>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.7, 1.2])
    anios = list(range(N.hoy().year, 1899, -1))
    d = c1.selectbox("Día", list(range(1, 32)), index=defecto.day - 1, key=f"{clave}_d")
    m = c2.selectbox("Mes", list(range(1, 13)), index=defecto.month - 1, format_func=lambda x: MESES[x - 1], key=f"{clave}_m")
    a = c3.selectbox("Año", anios, index=anios.index(defecto.year) if defecto.year in anios else 0, key=f"{clave}_a")
    try:
        f = date(a, m, d)
    except ValueError:
        return None
    return f if f <= N.hoy() else None


def selector_residente(clave, solo_activos=True, etiqueta="¿De quién se trata?"):
    df = N.leer("residentes")
    if solo_activos:
        df = df[df["Estado"] != "Egresado"]
    if df.empty:
        st.info("Aún no hay residentes registrados. Cree una admisión en **👴 Residentes**.")
        return None
    opciones = df["Cedula"].tolist()
    etq = {r.Cedula: f"👤 {r.Nombre} · Hab. {r.Habitacion or '—'} · CC {r.Cedula}" for r in df.itertuples()}
    k = f"sel_{clave}"
    if st.session_state.get(k) not in opciones:
        previo = st.session_state.get("res_sel")
        st.session_state[k] = previo if previo in opciones else opciones[0]
    sel = st.selectbox(etiqueta, opciones, format_func=lambda c: etq.get(c, c), key=k)
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
    sin = alerg.lower() in ("", "ninguna", "no", "n/a", "ninguna conocida")
    chip_al = chip("Sin alergias reportadas", "ok") if sin else chip(f"⚠ ALERGIA: {alerg}", "crit")
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


def tiles(items, columnas=3):
    """Azulejos grandes. items = [(clave_pagina, emoji, texto)]. Devuelve la clave tocada o None."""
    elegido = None
    cols = st.columns(columnas)
    for i, (clave, em, texto) in enumerate(items):
        if cols[i % columnas].button(f"{em}  {texto}", key=f"tile_{clave}", **KW):
            elegido = clave
    return elegido


def capturar_foto(clave, etiqueta="Foto"):
    """Foto con la cámara del celular o subida desde la galería. Devuelve bytes o None."""
    t1, t2 = st.tabs(["📷 Tomar foto", "🖼 Elegir de la galería"])
    with t1:
        cam = st.camera_input(etiqueta, key=f"cam_{clave}", label_visibility="collapsed")
    with t2:
        up = st.file_uploader(etiqueta, type=["jpg", "jpeg", "png", "webp"], key=f"up_{clave}", label_visibility="collapsed")
    src = cam or up
    return src.getvalue() if src else None


@st.cache_data(ttl=600, show_spinner=False, max_entries=200)
def _bytes_archivo(tid, archivo_id, _fila):
    return N.leer_archivo(cfg(), _fila)


def bytes_de(archivo_id):
    """Bytes de un archivo del expediente (con caché de 10 min)."""
    fila = N.buscar_archivo(archivo_id)
    if not fila:
        return None, None
    try:
        return _bytes_archivo(N.tenant_actual(), archivo_id, fila), fila
    except Exception:
        return None, fila
