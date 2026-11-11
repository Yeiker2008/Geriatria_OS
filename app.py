# -*- coding: utf-8 -*-
"""
GERIATRÍA OS · Suite para geriátricos
Secciones: Enfermería · Cocina · Servicios generales · Familias · Administración · Panel de propietarios.
Los datos viven en Google Drive (nucleo.py). Las pantallas están en vistas_*.py y los estilos en ui.py.
"""
import time

import streamlit as st

import nucleo as N

st.set_page_config(page_title="Geriatría OS", page_icon="🏥", layout="wide", initial_sidebar_state="expanded")

import ui as U  # noqa: E402  (después de set_page_config)
import vistas_enfermeria as VE  # noqa: E402
import vistas_owner as VO  # noqa: E402
import vistas_servicios as VS  # noqa: E402
from ui import KW, chip, h  # noqa: E402

MIN_INACTIVIDAD = 20     # minutos sin tocar nada → se cierra la sesión
MIN_INACTIVIDAD_OWNER = 10
HORAS_MAX_SESION = 12

for _k, _v in {"auth": False, "usuario": "", "rol": "", "alias": "", "reg": "", "pagina": "Hub", "tenant": "",
               "forzar_clave": False, "ultima": 0.0, "inicio": 0.0}.items():
    st.session_state.setdefault(_k, _v)

N.usar_tenant(None)   # cada recarga empieza sin geriátrico; solo se fija tras validar la sesión
N.conectar(U.cfg())   # hoja de CONTROL del propietario
N.contexto("", "")


# ══════════════════════════════════════════════════════════════
# REGISTRO DE CADA BOTÓN QUE SE TOCA (para el monitor de actividad)
# ══════════════════════════════════════════════════════════════
def _instalar_registro_de_clics():
    if getattr(st, "_geri_clics", False):
        return
    for nombre in ("button", "form_submit_button", "download_button"):
        orig = getattr(st, nombre)

        def envoltura(label, *a, _orig=orig, _n=nombre, **kw):
            r = _orig(label, *a, **kw)
            if r and st.session_state.get("auth"):
                try:
                    etiqueta = f"{_n.replace('_', ' ')}: {str(label)[:80]}"
                    if st.session_state.get("rol") == "Propietario":
                        N.log_control(st.session_state.usuario, "CLIC", etiqueta)
                    else:
                        N.log(st.session_state.usuario, "CLIC", etiqueta, tipo="CLIC")
                except Exception:
                    pass
            return r
        setattr(st, nombre, envoltura)
    st._geri_clics = True


_instalar_registro_de_clics()


def _ocultar_sidebar():
    st.markdown("<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl'],"
                "[data-testid='collapsedControl']{display:none!important}</style>", unsafe_allow_html=True)


def _cerrar_sesion(aviso=None):
    st.session_state.update(auth=False, usuario="", rol="", alias="", reg="", tenant="", forzar_clave=False, pagina="Hub", ultima=0.0)
    for k in ("nota_inicio", "_cli", "res_sel", "nuevo_cliente"):
        st.session_state.pop(k, None)
    if aviso:
        st.session_state["_aviso_login"] = aviso
    st.rerun()


# ══════════════════════════════════════════════════════════════
# LOGIN ÚNICO (el propietario entra por el mismo formulario con su código)
# ══════════════════════════════════════════════════════════════
def _bloqueado(cod, u):
    s = max(N.segundos_bloqueo(cod, u), N.segundos_bloqueo("codigo", cod))
    if s:
        st.error(f"🔒 Demasiados intentos. Espere {max(1, s // 60)} minuto(s) e intente de nuevo.")
        return True
    return False


def _fallo(cod, u, tenant_ok=False):
    n = N.registrar_fallo(cod, u)
    N.registrar_fallo("codigo", cod, umbral=15)
    if tenant_ok:
        N.log(u or "?", "LOGIN_FALLIDO", f"intento {n}", tipo="SEGURIDAD")
        if n % 5 == 0:
            N.log(u or "?", "BLOQUEO_TEMPORAL", f"{n} intentos fallidos", tipo="SEGURIDAD")
    st.error("Código, usuario o contraseña incorrectos.")


def _login():
    cfg = U.cfg()
    if N.hay_credenciales(cfg) and not N.estado_control()["conectado"]:
        st.error("No hay conexión con la bóveda de datos en este momento. Intente de nuevo en un minuto.")
        if st.button("🔄 Reintentar", key="reint_login", **KW):
            N.conectar(cfg, forzar=True)
            st.rerun()
        return
    if not N.hay_credenciales(cfg):
        st.info("🧪 Modo demostración local · código `OWNER` · usuario `owner` · contraseña `owner123`")
    with st.form("login"):
        cod = st.text_input("🏥 Código", placeholder="GER-XXXXXX")
        u = st.text_input("👤 Usuario")
        p = st.text_input("🔑 Contraseña", type="password")
        ok = st.form_submit_button("ENTRAR", type="primary", **KW)
    if not ok:
        return
    cod, u = cod.strip().upper(), u.strip().lower()
    if _bloqueado(cod, u):
        return
    # ── propietario
    if N.es_codigo_owner(cfg, cod):
        if not N.owner_configurado(cfg) and N.hay_credenciales(cfg):
            st.error("El acceso de propietario aún no está configurado en Secrets (owners / owner_password_hash).")
            return
        if N.verificar_owner(cfg, u, p):
            N.limpiar_fallos(cod, u)
            st.session_state.update(auth=True, tenant="", usuario=u, rol="Propietario", alias=u.title(), reg="", pagina="OwnerHub",
                                    forzar_clave=False, ultima=time.time(), inicio=time.time())
            N.log_control(u, "LOGIN_PROPIETARIO")
            st.rerun()
        N.log_control(u or "?", "LOGIN_FALLIDO_PROPIETARIO")
        _fallo(cod, u)
        return
    # ── geriátrico
    try:
        cli = N.buscar_cliente(cod)
        if cli is None:
            _fallo(cod, u)
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
            _fallo(cod, u, tenant_ok=True)
            return
    except N.ErrorNube as e:
        st.error(f"Problema con la bóveda de datos: {e}")
        return
    N.limpiar_fallos(cod, u)
    st.session_state.update(auth=True, tenant=cli["Codigo"], usuario=r["Usuario"], rol=r["Rol"], alias=r["Alias"] or r["Usuario"],
                            reg=r["Reg_Profesional"], pagina="Hub", ultima=time.time(), inicio=time.time(),
                            forzar_clave=str(r.get("Cambiar_Clave", "")).upper() == "SI")
    N.contexto(r["Rol"], "Login")
    N.log(r["Usuario"], "LOGIN", tipo="SEGURIDAD")
    st.rerun()


def pantalla_login():
    _ocultar_sidebar()
    U.inyectar_css("Admin")
    _, c, _ = st.columns([1, 1.15, 1])
    with c:
        st.markdown("<div class='login-logo'>🏥</div><h1 style='text-align:center'>Geriatría OS</h1>"
                    "<p class='login-sub'>Ingrese con su código, usuario y contraseña</p>", unsafe_allow_html=True)
        aviso = st.session_state.pop("_aviso_login", None)
        if aviso:
            st.error(aviso)
        _login()


if not st.session_state.auth:
    pantalla_login()
    st.stop()

# ══════════════════════════════════════════════════════════════
# SESIÓN ACTIVA: tiempo de inactividad y servicio vigente en CADA recarga
# ══════════════════════════════════════════════════════════════
ES_OWNER = st.session_state.rol == "Propietario"
_limite = (MIN_INACTIVIDAD_OWNER if ES_OWNER else MIN_INACTIVIDAD) * 60
_ahora = time.time()
if (_ahora - st.session_state.ultima > _limite) or (_ahora - st.session_state.inicio > HORAS_MAX_SESION * 3600):
    try:
        if not ES_OWNER:
            N.usar_tenant(st.session_state.tenant)
            N.log(st.session_state.usuario, "SESION_EXPIRADA", tipo="SEGURIDAD")
    except Exception:
        pass
    _cerrar_sesion("🔒 Su sesión se cerró por inactividad. Ingrese de nuevo.")
st.session_state.ultima = _ahora

CLI = None
if not ES_OWNER:
    try:
        CLI = N.buscar_cliente(st.session_state.tenant)
        _ok, _motivo, _dias = N.estado_servicio(CLI) if CLI else (False, "Cuenta no encontrada.", None)
        if not _ok:
            _cerrar_sesion(f"⛔ {_motivo} Comuníquese con su proveedor para reactivar el servicio.")
        if not N.abrir_tenant(U.cfg(), CLI):
            st.error("No se pudo abrir la bóveda de datos de este geriátrico. Intente de nuevo en unos segundos.")
            st.stop()
        N.usar_tenant(CLI["Codigo"])
        st.session_state["_cli"] = CLI
    except N.ErrorNube as e:
        st.error(f"⚠️ Problema con la bóveda de datos: {e}")
        st.stop()


def pantalla_cambio_clave():
    _ocultar_sidebar()
    U.inyectar_css("Admin")
    _, c, _ = st.columns([1, 1.15, 1])
    estricta = st.session_state.rol == N.R_ADMIN
    with c:
        st.markdown("<div class='login-logo'>🔐</div><h2 style='text-align:center'>Cree su contraseña personal</h2>"
                    "<p class='login-sub'>Por seguridad debe cambiar la clave temporal antes de continuar.</p>", unsafe_allow_html=True)
        with st.form("form_pw_forzado"):
            n1 = st.text_input(f"Nueva contraseña ({'12' if estricta else '8'}+ caracteres con letras y números)", type="password")
            n2 = st.text_input("Repetir contraseña", type="password")
            ok = st.form_submit_button("GUARDAR Y CONTINUAR", type="primary", **KW)
        if ok:
            problema = N.validar_clave(n1, estricta)
            if problema:
                st.error(problema)
            elif n1 != n2:
                st.error("Las dos contraseñas deben ser iguales.")
            else:
                N.actualizar("usuarios", "Usuario", st.session_state.usuario, {"Password": N.hash_pw(n1), "Cambiar_Clave": "NO"})
                N.log(st.session_state.usuario, "CAMBIO_CLAVE", tipo="SEGURIDAD")
                st.session_state.forzar_clave = False
                st.rerun()
        if st.button("Cancelar y salir", key="salir_forzado", **KW):
            _cerrar_sesion()


if st.session_state.forzar_clave and not ES_OWNER:
    pantalla_cambio_clave()
    st.stop()

# ══════════════════════════════════════════════════════════════
# MENÚ SEGÚN EL ROL
# ══════════════════════════════════════════════════════════════
SEC_DE = {"Residentes": "Enfermeria", "Medicamentos": "Enfermeria", "Vitales": "Enfermeria", "SOAPIE": "Enfermeria", "Kardex": "Enfermeria",
          "Pertenencias": "Enfermeria", "Salidas": "Enfermeria", "Escalas": "Enfermeria", "Cocina": "Cocina", "Aseo": "Aseo",
          "Familias": "Familias", "Contratos": "Familias", "Archivos": "Admin", "Monitor": "Admin", "Admin": "Admin"}
SEC_ROL = {N.R_ENF: "Enfermeria", N.R_AUX: "Enfermeria", N.R_MED: "Enfermeria", N.R_COC: "Cocina", N.R_AUXC: "Cocina",
           N.R_ASEO: "Aseo", N.R_FAM: "Familias", N.R_ADMIN: "Admin"}

if ES_OWNER:
    PAGINAS = [("OwnerHub", "📈", "Resumen"), ("Ranking", "🏆", "Mejores geriátricos"), ("Clientes", "🏢", "Clientes"),
               ("NuevoCliente", "➕", "Nuevo cliente"), ("Pagos", "💳", "Pagos"), ("OwnerSistema", "🛠", "Sistema")]
    MARCA = "Panel de propietarios"
else:
    PAGINAS = N.paginas_permitidas(st.session_state.rol, CLI)
    MARCA = CLI["Nombre"]
if st.session_state.pagina not in [p[0] for p in PAGINAS]:
    if st.session_state.pagina not in ("Hub", "OwnerHub"):
        try:
            N.log(st.session_state.usuario, "ACCESO_DENEGADO", st.session_state.pagina, tipo="SEGURIDAD") if not ES_OWNER else None
        except Exception:
            pass
    st.session_state.pagina = PAGINAS[0][0]
PAG = st.session_state.pagina
_seccion = "Owner" if ES_OWNER else SEC_DE.get(PAG, SEC_ROL.get(st.session_state.rol, "Enfermeria"))
U.inyectar_css(_seccion)
N.contexto(st.session_state.rol, PAG)

if st.session_state.get("_ult_pag") != PAG:
    st.session_state["_ult_pag"] = PAG
    try:
        if ES_OWNER:
            N.log_control(st.session_state.usuario, "PANTALLA", PAG)
        else:
            N.log(st.session_state.usuario, "ABRE_PANTALLA", PAG, tipo="PANTALLA")
    except Exception:
        pass

with st.sidebar:
    st.markdown(U.bloque(f"""<div class="sb-brand">🏥 Geriatría OS</div><div class="sb-tenant">{h(MARCA)}</div><div class="sb-user">
        <div class="sb-alias">{h(st.session_state.alias)}</div><div class="sb-rol">{h(st.session_state.rol)}</div></div>"""), unsafe_allow_html=True)
    for clave, icono, nombre in PAGINAS:
        if st.button(f"{icono}  {nombre}", key=f"nav_{clave}", type="primary" if PAG == clave else "secondary", **KW):
            st.session_state.pagina = clave
            st.rerun()
    st.markdown("---")
    _e = N.estado_control() if ES_OWNER else N.estado_nube()
    st.markdown(chip("☁️ Bóveda conectada", "ok") if _e["conectado"] else chip("💾 Modo demostración local", "crit"), unsafe_allow_html=True)
    if st.button("🚪  Cerrar sesión", key="nav_salir", **KW):
        if ES_OWNER:
            N.log_control(st.session_state.usuario, "LOGOUT_PROPIETARIO")
        else:
            N.log(st.session_state.usuario, "LOGOUT", tipo="SEGURIDAD")
        _cerrar_sesion()
    if hasattr(st, "fragment"):
        @st.fragment(run_every=60)
        def _vigilante():
            if time.time() - st.session_state.get("ultima", 0) > _limite:
                st.rerun()
        _vigilante()

def barra_superior():
    """Menú SIEMPRE visible arriba (no depende de la barra lateral, que en el celular se puede perder)."""
    try:
        cont = st.container(key="barra_top")
    except TypeError:
        cont = st.container()
    inicio = PAGINAS[0][0]
    with cont:
        c1, c2, c3 = st.columns([1.3, 1.3, 2.4])
        if PAG != inicio and c1.button("🏠 Inicio", key="top_inicio", **KW):
            st.session_state.pagina = inicio
            st.rerun()
        pop = c2.popover("☰ Menú", **KW) if hasattr(st, "popover") else c2.expander("☰ Menú")
        with pop:
            for clave, icono, nombre in PAGINAS:
                if st.button(f"{icono}  {nombre}", key=f"top_{clave}", type="primary" if PAG == clave else "secondary", **KW):
                    st.session_state.pagina = clave
                    st.rerun()
            if st.button("🚪  Cerrar sesión", key="top_salir", **KW):
                if ES_OWNER:
                    N.log_control(st.session_state.usuario, "LOGOUT_PROPIETARIO")
                else:
                    N.log(st.session_state.usuario, "LOGOUT", tipo="SEGURIDAD")
                _cerrar_sesion()
        nombre_pag = next((f"{i} {n}" for k, i, n in PAGINAS if k == PAG), "")
        c3.markdown(f"<div style='padding-top:.55rem;font-weight:800;color:#0B1F3A;text-align:right'>{h(nombre_pag)}</div>", unsafe_allow_html=True)


barra_superior()
U.mostrar_flash()
if not ES_OWNER and not N.estado_nube()["conectado"]:
    st.warning("💾 **Modo demostración local.** Los datos se guardan solo en este servidor y pueden perderse al reiniciar la app.")


# ══════════════════════════════════════════════════════════════
# INICIO (cada rol ve lo suyo)
# ══════════════════════════════════════════════════════════════
def _cambiar_clave():
    estricta = st.session_state.rol == N.R_ADMIN
    with st.expander("🔑 Cambiar mi contraseña"):
        v = U.ver("pw")
        with st.form(f"form_pw_{v}"):
            actual = st.text_input("Contraseña actual", type="password", key=f"pw_a_{v}")
            nueva = st.text_input(f"Nueva contraseña ({'12' if estricta else '8'}+ caracteres con letras y números)", type="password", key=f"pw_n_{v}")
            conf = st.text_input("Repetir nueva contraseña", type="password", key=f"pw_c_{v}")
            if st.form_submit_button("ACTUALIZAR CONTRASEÑA", type="primary"):
                problema = N.validar_clave(nueva, estricta)
                if N.autenticar(st.session_state.usuario, actual) is None:
                    st.error("La contraseña actual no es correcta.")
                elif problema:
                    st.error(problema)
                elif nueva != conf:
                    st.error("Las dos contraseñas nuevas deben ser iguales.")
                else:
                    N.actualizar("usuarios", "Usuario", st.session_state.usuario, {"Password": N.hash_pw(nueva), "Cambiar_Clave": "NO"})
                    N.log(st.session_state.usuario, "CAMBIO_CLAVE", tipo="SEGURIDAD")
                    U.flash("ok", "✅ Contraseña actualizada.")
                    U.nueva_version("pw")
                    st.rerun()


def pagina_hub():
    rol = st.session_state.rol
    U.banner(SEC_ROL.get(rol, "Enfermeria"), f"Hola, {st.session_state.alias} 👋", f"{N.hoy().strftime('%d/%m/%Y')} · {rol}")
    if rol == N.R_ADMIN and CLI:
        _o, _m, _d = N.estado_servicio(CLI)
        if _d is not None and _d <= 7:
            U.aviso("💳 Su suscripción " + (f"vence en {_d} días" if _d >= 0 else "está en periodo de gracia") + ". Contacte a su proveedor para renovar.", "warn")

    def ver(p):
        return N.puede_ver(rol, CLI, p)

    # ── Alertas: cada persona ve solo las de su sección
    if ver("Medicamentos"):
        dosis = N.dosis_hoy()
        atr = [d for d in dosis if d["Estado"] == "Atrasado"]
        ahora_ = [d for d in dosis if d["Estado"] == "Ahora"]
        if atr:
            U.aviso(f"🔴 Hay {len(atr)} dosis ATRASADAS: " + ", ".join(f"{d['Residente']} ({d['Medicamento']} {d['Hora']})" for d in atr[:4]) + ("…" if len(atr) > 4 else ""), "crit")
        if ahora_:
            U.aviso(f"🟡 {len(ahora_)} medicinas son para esta hora.", "warn")
        sm = N.stock_meds()
        res = N.leer("residentes").set_index("Cedula")["Nombre"].to_dict()
        for x in sm[sm["Nivel"] != "ok"].head(5).to_dict("records"):
            U.aviso(f"{'🔴' if x['Nivel'] == 'crit' else '🟡'} Medicina por acabarse: {x['Medicamento']} de {res.get(x['Cedula'], x['Cedula'])} (quedan {x['Stock']:g})", x["Nivel"])
        sal = N.leer("salidas")
        fuera = sal[sal["Estado"] == "En salida"]
        if not fuera.empty:
            U.aviso("🚪 Residentes fuera ahora: " + ", ".join(res.get(c, c) for c in fuera["Cedula"]), "info")
        vit = N.leer("signos_vitales")
        crit = vit[vit["Fecha_Hora"].str.startswith(N.hoy().isoformat()) & vit["Alertas"].str.contains("🔴", regex=False)]
        if not crit.empty:
            U.aviso(f"🚨 {len(crit)} registros de signos vitales con alerta crítica hoy.", "crit")
    if ver("Cocina"):
        VS._alertas_stock("Cocina", "en COCINA")
    if ver("Aseo"):
        VS._alertas_stock("Aseo", "de ASEO")
    if ver("Familias"):
        for x in N.alertas_pago(5)[:6]:
            d = x["Dias"]
            U.aviso(f"{'🔴' if d < 0 else '🟡'} Pago de {x['Nombre']}: " + (f"vencido hace {-d} días" if d < 0 else "vence hoy" if d == 0 else f"vence en {d} días"), "crit" if d < 0 else "warn")

    # ── Cifras rápidas para quien ve enfermería
    if ver("Residentes") and rol != N.R_FAM:
        res = N.leer("residentes")
        act = res[res["Estado"] != "Egresado"]
        vit = N.leer("signos_vitales")
        hoy_s = N.hoy().isoformat()
        v_hoy = vit[vit["Fecha_Hora"].str.startswith(hoy_s)]
        c = st.columns(4)
        c[0].markdown(U.kpi(len(act), "👴 Residentes activos"), unsafe_allow_html=True)
        c[1].markdown(U.kpi(len(v_hoy), "🩺 Signos vitales hoy"), unsafe_allow_html=True)
        c[2].markdown(U.kpi(int(N.leer("notas_soapie")["Fecha_Hora"].str.startswith(hoy_s).sum()), "📝 Notas de hoy"), unsafe_allow_html=True)
        pend = act[~act["Cedula"].isin(v_hoy["Cedula"])]
        c[3].markdown(U.kpi(len(pend), "⏳ Sin signos hoy", "warn" if len(pend) else ""), unsafe_allow_html=True)

    st.markdown("### ¿Qué quiere hacer?")
    items = [(k, i, n) for k, i, n in PAGINAS if k != "Hub"]
    elegido = U.tiles(items, columnas=3)
    if elegido:
        st.session_state.pagina = elegido
        st.rerun()
    _cambiar_clave()


RUTAS = {"Hub": pagina_hub, "Residentes": VE.pagina_residentes, "Medicamentos": VE.pagina_medicamentos, "Vitales": VE.pagina_vitales,
         "SOAPIE": VE.pagina_soapie, "Kardex": VE.pagina_kardex, "Pertenencias": VE.pagina_pertenencias, "Salidas": VE.pagina_salidas,
         "Escalas": VE.pagina_escalas, "Cocina": VS.pagina_cocina, "Aseo": VS.pagina_aseo, "Familias": VS.pagina_familias,
         "Contratos": VS.pagina_contratos, "Archivos": VS.pagina_archivos, "Monitor": VS.pagina_monitor, "Admin": VS.pagina_admin,
         "OwnerHub": VO.pagina_owner_hub, "Ranking": VO.pagina_ranking, "Clientes": VO.pagina_clientes,
         "NuevoCliente": VO.pagina_nuevo_cliente, "Pagos": VO.pagina_pagos, "OwnerSistema": VO.pagina_owner_sistema}

try:
    RUTAS[PAG]()
except N.ErrorNube as err:
    st.error(f"⚠️ Problema con la bóveda de datos: {err}")
    st.caption("Sus datos no se perdieron. Espere unos segundos y vuelva a intentar la acción.")
except PermissionError as err:
    st.error(f"🔒 {err}")
except Exception as err:   # nunca mostrar detalles técnicos al usuario; quedan en la auditoría
    try:
        if ES_OWNER:
            N.log_control(st.session_state.usuario, "ERROR", f"{PAG}: {type(err).__name__}")
        else:
            N.log(st.session_state.usuario, "ERROR", f"{PAG}: {type(err).__name__}: {str(err)[:150]}", tipo="SEGURIDAD")
    except Exception:
        pass
    st.error("⚠️ Algo salió mal en esta pantalla. Intente de nuevo; si sigue pasando avise a administración.")
