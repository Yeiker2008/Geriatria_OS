# -*- coding: utf-8 -*-
"""
nucleo.py · Geriatría OS (multi-geriátrico)
-------------------------------------------
Capa de datos con una BÓVEDA (hoja de Google + carpeta) independiente por geriátrico,
una hoja de CONTROL del propietario (clientes, pagos), suscripciones, seguridad,
escalas clínicas y utilidades.

No depende de Streamlit, así que se puede probar por separado.
"""
import calendar
import hashlib
import hmac
import os
import re
import secrets as _pysecrets
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import pandas as pd

# ──────────────────────────────────────────────────────────────
# Hora y fechas (Colombia, UTC-5)
# ──────────────────────────────────────────────────────────────
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Bogota")
except Exception:  # sin tzdata en el servidor
    _TZ = timezone(timedelta(hours=-5))


def ahora():
    return datetime.now(_TZ).replace(tzinfo=None)


def hoy():
    return ahora().date()


def fmt_fh(dt=None):
    return (dt or ahora()).strftime("%Y-%m-%d %H:%M:%S")


def parsear_fecha(s):
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def calcular_edad(fnac):
    f = fnac if isinstance(fnac, date) else parsear_fecha(fnac)
    if not f:
        return None
    h = hoy()
    return h.year - f.year - ((h.month, h.day) < (f.month, f.day))


def sumar_meses(f, n):
    m = f.month - 1 + n
    y, m = f.year + m // 12, m % 12 + 1
    return date(y, m, min(f.day, calendar.monthrange(y, m)[1]))


def nueva_id(prefijo):
    return f"{prefijo}-{uuid.uuid4().hex[:8].upper()}"


def _num(x, defecto=0.0):
    try:
        return float(str(x).replace(",", ".").strip())
    except Exception:
        return defecto


# ──────────────────────────────────────────────────────────────
# Esquemas
# ──────────────────────────────────────────────────────────────
# Tablas de CADA geriátrico (una pestaña por tabla, en la hoja propia de ese geriátrico)
ESQUEMA = {
    "residentes": ["Cedula", "Nombre", "Fecha_Nacimiento", "Sexo", "EPS", "Habitacion",
                   "Diagnosticos", "Alergias", "Acudiente_Nombre", "Acudiente_Tel",
                   "Estado", "F_Ingreso", "F_Egreso", "Motivo_Egreso"],
    "signos_vitales": ["ID", "Cedula", "Fecha_Hora", "TA_Sis", "TA_Dia", "FC", "FR", "Temp",
                       "SatO2", "Glucemia", "Dolor", "Peso", "Alertas", "Autor"],
    "notas_soapie": ["ID_Nota", "Cedula", "Fecha_Hora", "Turno", "Autor", "Subjetivo", "Objetivo",
                     "Analisis", "Plan", "Intervencion", "Evaluacion", "Sello"],
    "kardex_meds": ["ID_Med", "Cedula", "Medicamento", "Dosis", "Via", "Frecuencia", "Horarios",
                    "Indicaciones", "Estado", "Prescrito_Por", "F_Inicio", "F_Suspension"],
    "admin_meds": ["ID", "ID_Med", "Cedula", "Fecha_Hora", "Resultado", "Observacion", "Autor"],
    "escalas": ["ID", "Cedula", "Fecha_Hora", "Escala", "Puntaje", "Interpretacion", "Detalle", "Autor"],
    "usuarios": ["Usuario", "Password", "Rol", "Alias", "Reg_Profesional", "Activo", "Cambiar_Clave"],
    "logs": ["Fecha_Hora", "Usuario", "Accion", "Detalle"],
}

# Tablas del PROPIETARIO (solo él las ve): clientes, pagos y auditoría de su panel
ESQUEMA_CONTROL = {
    "clientes": ["Codigo", "Nombre", "NIT", "Contacto", "Telefono", "Email", "Plan", "Max_Usuarios",
                 "Precio_Mensual", "Estado", "Vence", "Dias_Gracia", "Modo_Boveda", "Sheet_ID",
                 "Carpeta_URL", "Creado", "Notas"],
    "pagos": ["ID", "Codigo", "Fecha", "Monto", "Metodo", "Periodo", "Nota", "Registrado_Por"],
    "logs_control": ["Fecha_Hora", "Actor", "Accion", "Detalle"],
}

NOMBRE_CARPETA = "Geriatria_OS"   # carpeta raíz (solo si se usa OAuth sin google_folder_id)
NOMBRE_CONTROL = "OS_Control"
DATA_DIR = os.environ.get("GERIATRIA_DATA_DIR", "datos_locales")
CONTROL = "__control__"
TTL = 120          # segundos que una tabla de un geriátrico se conserva en memoria
TTL_CONTROL = 45   # el estado de suscripción se revisa más seguido

SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
_DRIVE = "https://www.googleapis.com/drive/v3/files"
_MIME_CARPETA = "application/vnd.google-apps.folder"
_MIME_HOJA = "application/vnd.google-apps.spreadsheet"

_STORES = {}          # tid -> estado de esa bóveda (cada geriátrico tiene el suyo)
_AUTH = {}            # credenciales de Google (compartidas)
_FLAGS = {"cred": False}
_LOCK = threading.RLock()
_CTX = threading.local()


class ErrorNube(Exception):
    """Falla al leer o escribir en Google Sheets."""


def _nuevo_store():
    return {"tablas": {}, "hojas": {}, "enc": {}, "libro": None, "error": None,
            "libro_url": None, "carpeta_url": None, "t_intento": 0.0}


def _store(tid):
    with _LOCK:
        return _STORES.setdefault(tid, _nuevo_store())


def usar_tenant(tid):
    """Fija el geriátrico de ESTA ejecución. La app lo llama al inicio de cada recarga."""
    _CTX.tid = tid or None


def tenant_actual():
    return getattr(_CTX, "tid", None)


def _resolver(nombre, tid=None):
    if nombre in ESQUEMA_CONTROL:
        return CONTROL, ESQUEMA_CONTROL[nombre]
    tid = tid or tenant_actual()
    if not tid:
        raise ErrorNube("No hay un geriátrico activo en esta sesión.")
    return tid, ESQUEMA[nombre]


# ──────────────────────────────────────────────────────────────
# Conexión a Google (credenciales, bóveda de control y bóvedas de clientes)
# ──────────────────────────────────────────────────────────────
def hay_credenciales(cfg):
    return bool(cfg.get("gcp_service_account")
                or (cfg.get("google_client_id") and cfg.get("google_refresh_token")))


def _chk(r):
    if r.status_code >= 400:
        t = r.text[:500]
        if "storageQuota" in t or "storage quota" in t.lower():
            raise RuntimeError(
                "La cuenta de servicio no tiene espacio propio en Drive para crear archivos. Cree la hoja a mano "
                "en su Drive, compártala como Editor con la cuenta de servicio y pegue su ID (modo «Propia del "
                "cliente»), o conecte con OAuth. Detalle: " + t[:200])
        raise RuntimeError(f"Google Drive respondió {r.status_code}: {t}")
    return r


def _listar(drive, q):
    r = _chk(drive.get(_DRIVE, params={"q": q, "fields": "files(id,name,parents)",
                                       "spaces": "drive", "pageSize": 20}))
    return r.json().get("files", [])


def _asegurar_carpeta(drive, nombre, padre=None):
    q = f"name='{nombre}' and mimeType='{_MIME_CARPETA}' and trashed=false"
    if padre:
        q += f" and '{padre}' in parents"
    f = _listar(drive, q)
    if f:
        return f[0]["id"]
    cuerpo = {"name": nombre, "mimeType": _MIME_CARPETA}
    if padre:
        cuerpo["parents"] = [padre]
    return _chk(drive.post(_DRIVE, json=cuerpo)).json()["id"]


def _auth(cfg):
    if _AUTH.get("cliente"):
        return _AUTH
    import gspread
    from google.auth.transport.requests import AuthorizedSession, Request

    sa = cfg.get("gcp_service_account")
    if sa:
        from google.oauth2.service_account import Credentials as SACreds
        sa = dict(sa)
        creds = SACreds.from_service_account_info(sa, scopes=SCOPES)
        modo, email = "servicio", sa.get("client_email", "")
    else:
        from google.oauth2.credentials import Credentials
        faltan = [k for k in ("google_client_id", "google_client_secret", "google_refresh_token") if not cfg.get(k)]
        if faltan:
            raise RuntimeError("Faltan estos valores en Secrets: " + ", ".join(faltan) + " (o configure [gcp_service_account])")
        creds = Credentials(token=None, refresh_token=cfg["google_refresh_token"],
                            token_uri="https://oauth2.googleapis.com/token",
                            client_id=cfg["google_client_id"], client_secret=cfg["google_client_secret"])
        creds.refresh(Request())
        modo, email = "oauth", ""
    _AUTH.update(creds=creds, cliente=gspread.authorize(creds), drive=AuthorizedSession(creds), modo=modo, email=email)
    return _AUTH


def _asegurar_pestanas(libro, store, esquema):
    existentes = {w.title: w for w in libro.worksheets()}
    nombres = list(esquema)
    if not any(n in existentes for n in nombres):  # libro nuevo: la hoja inicial pasa a ser la primera tabla
        libro.sheet1.update_title(nombres[0])
        existentes = {w.title: w for w in libro.worksheets()}
    enc = {}
    for nombre, cols in esquema.items():
        ws = existentes.get(nombre)
        if ws is None:
            ws = libro.add_worksheet(title=nombre, rows=500, cols=max(len(cols) + 2, 12))
        fila1 = [c.strip() for c in ws.row_values(1)]
        if not any(fila1):
            ws.append_row(list(cols), value_input_option="RAW")
            fila1 = list(cols)
        else:
            for c in cols:  # columnas nuevas del esquema se añaden al final
                if c not in fila1:
                    fila1.append(c)
                    ws.update_cell(1, len(fila1), c)
        enc[nombre] = fila1
        store["hojas"][nombre] = ws
    store["enc"] = enc


def _buscar_o_crear_control(cfg, a):
    f = _listar(a["drive"], f"name='{NOMBRE_CONTROL}' and mimeType='{_MIME_HOJA}' and trashed=false")
    if f:
        return f[0]["id"]
    padre = cfg.get("google_folder_id")
    if a["modo"] == "servicio" and not padre:
        raise RuntimeError(
            f"No se encontró la hoja '{NOMBRE_CONTROL}'. Créela en su Drive y compártala como Editor con "
            f"{a['email']}, o ponga control_sheet_id (y google_folder_id) en Secrets.")
    raiz = padre or _asegurar_carpeta(a["drive"], NOMBRE_CARPETA)
    return _chk(a["drive"].post(_DRIVE, json={"name": NOMBRE_CONTROL, "mimeType": _MIME_HOJA, "parents": [raiz]})).json()["id"]


def conectar(cfg, forzar=False):
    """Conecta la hoja de CONTROL del propietario. Devuelve el libro o None (motivo en estado_control())."""
    with _LOCK:
        s = _store(CONTROL)
        if forzar:
            _AUTH.clear()
            for k in list(_STORES):
                _STORES[k] = _nuevo_store()
            s = _store(CONTROL)
        _FLAGS["cred"] = hay_credenciales(cfg)
        if s["libro"] is not None:
            return s["libro"]
        if not _FLAGS["cred"]:
            s["error"] = "No hay credenciales de Google en Secrets: modo de demostración local."
            return None
        if time.time() - s["t_intento"] < 60:
            return None
        s["t_intento"] = time.time()
        try:
            a = _auth(cfg)
            sid = cfg.get("control_sheet_id") or _buscar_o_crear_control(cfg, a)
            libro = a["cliente"].open_by_key(sid)
            _asegurar_pestanas(libro, s, ESQUEMA_CONTROL)
            s.update(libro=libro, error=None, libro_url=libro.url)
            return libro
        except Exception as e:
            s["libro"] = None
            s["error"] = f"{type(e).__name__}: {e}"
            return None


def nube_activa():
    return _store(CONTROL)["libro"] is not None


def abrir_tenant(cfg, cli, forzar=False):
    """Conecta la bóveda de UN geriátrico (por su Sheet_ID). True si queda lista."""
    tid = cli["Codigo"]
    with _LOCK:
        s = _store(tid)
        if forzar:
            _STORES[tid] = s = _nuevo_store()
        if s["libro"] is not None or not nube_activa():
            return True  # ya abierta, o modo demostración local
        if time.time() - s["t_intento"] < 30:
            return False
        s["t_intento"] = time.time()
        sid = str(cli.get("Sheet_ID", "")).strip()
        if not sid:
            s["error"] = "Este geriátrico no tiene bóveda asignada (falta Sheet_ID)."
            return False
        try:
            a = _auth(cfg)
            libro = a["cliente"].open_by_key(sid)
            _asegurar_pestanas(libro, s, ESQUEMA)
            s.update(libro=libro, error=None, libro_url=libro.url, carpeta_url=cli.get("Carpeta_URL") or None)
            return True
        except Exception as e:
            s["libro"] = None
            s["error"] = f"{type(e).__name__}: {e}"
            return False


def crear_boveda(cfg, codigo, nombre):
    """Crea carpeta + hoja propias del geriátrico. Devuelve (sheet_id, carpeta_url)."""
    a = _auth(cfg)
    padre = cfg.get("google_folder_id")
    if a["modo"] == "servicio" and not padre:
        raise RuntimeError("Falta google_folder_id en Secrets (ID de una carpeta suya compartida con la cuenta de servicio).")
    raiz = padre or _asegurar_carpeta(a["drive"], NOMBRE_CARPETA)
    carpeta = _chk(a["drive"].post(_DRIVE, json={"name": f"{codigo} · {nombre}", "mimeType": _MIME_CARPETA,
                                                 "parents": [raiz]})).json()["id"]
    hoja = _chk(a["drive"].post(_DRIVE, json={"name": f"DB_{codigo}", "mimeType": _MIME_HOJA,
                                              "parents": [carpeta]})).json()["id"]
    return hoja, f"https://drive.google.com/drive/folders/{carpeta}"


def estado_control():
    s = _store(CONTROL)
    return {"conectado": s["libro"] is not None, "error": s["error"], "libro_url": s["libro_url"],
            "modo": _AUTH.get("modo"), "email": _AUTH.get("email")}


def estado_nube(tid=None):
    tid = tid or tenant_actual()
    if not tid:
        return estado_control()
    s = _store(tid)
    return {"conectado": s["libro"] is not None, "error": s["error"],
            "libro_url": s["libro_url"], "carpeta_url": s["carpeta_url"]}


# ──────────────────────────────────────────────────────────────
# Lectura / escritura de tablas (siempre dentro de la bóveda del geriátrico activo)
# ──────────────────────────────────────────────────────────────
def _libro(tid):
    """Libro de esa bóveda; None = modo demostración local; lanza ErrorNube si debería haber nube y no la hay."""
    ctrl = _store(CONTROL)
    if ctrl["libro"] is None:
        if _FLAGS["cred"]:
            raise ErrorNube("Sin conexión con la bóveda de datos. " + (ctrl["error"] or ""))
        return None
    if tid == CONTROL:
        return ctrl["libro"]
    s = _store(tid)
    if s["libro"] is None:
        raise ErrorNube("La bóveda de este geriátrico no está conectada. " + (s["error"] or ""))
    return s["libro"]


def _normalizar(df, cols):
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    extras = [c for c in df.columns if c not in cols]
    return df[list(cols) + extras].fillna("").astype(str).reset_index(drop=True)


def _csv_path(tid, nombre):
    seguro = "_control" if tid == CONTROL else re.sub(r"[^A-Za-z0-9_-]", "_", tid)
    return os.path.join(DATA_DIR, seguro, f"db_{nombre}.csv")


def _leer_csv(tid, nombre, cols):
    p = _csv_path(tid, nombre)
    df = pd.read_csv(p, dtype=str, keep_default_na=False) if os.path.exists(p) else pd.DataFrame(columns=cols)
    return _normalizar(df, cols)


def _guardar_csv(tid, nombre, df):
    p = _csv_path(tid, nombre)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    df.to_csv(p, index=False)


def _hoja(tid, nombre):
    s = _store(tid)
    if nombre not in s["hojas"]:
        s["hojas"][nombre] = s["libro"].worksheet(nombre)
    return s["hojas"][nombre]


def _leer_cloud(tid, nombre, cols):
    vals = _hoja(tid, nombre).get_all_values()
    if vals:
        enc = [h.strip() for h in vals[0]]
        filas = [(list(f) + [""] * len(enc))[:len(enc)] for f in vals[1:] if any(str(x).strip() for x in f)]
        df = pd.DataFrame(filas, columns=enc)
    else:
        df = pd.DataFrame(columns=cols)
    return _normalizar(df, cols), len(vals)


def leer(nombre, fresco=False, tid=None):
    tid, cols = _resolver(nombre, tid)
    s = _store(tid)
    c = s["tablas"].get(nombre)
    ttl = TTL_CONTROL if tid == CONTROL else TTL
    if c and not fresco and time.time() - c[0] < ttl:
        return c[1].copy()
    if _libro(tid) is None:
        return _leer_csv(tid, nombre, cols)
    try:
        df, _ = _leer_cloud(tid, nombre, cols)
    except Exception as e:
        s["hojas"].pop(nombre, None)
        if c and not fresco:
            return c[1].copy()  # datos en memoria mientras Google responde
        raise ErrorNube(f"No se pudo leer '{nombre}' en Google Sheets: {e}") from e
    s["tablas"][nombre] = (time.time(), df)
    return df.copy()


def agregar(nombre, fila, tid=None):
    """Agrega UNA fila al final (no reescribe la tabla)."""
    tid, cols = _resolver(nombre, tid)
    with _LOCK:
        s = _store(tid)
        if _libro(tid) is None:
            df = _leer_csv(tid, nombre, cols)
            df = pd.concat([df, pd.DataFrame([{k: str(v) for k, v in fila.items()}])], ignore_index=True)
            _guardar_csv(tid, nombre, _normalizar(df, cols))
        else:
            enc = s["enc"].get(nombre) or cols
            try:
                _hoja(tid, nombre).append_row([str(fila.get(c, "")) for c in enc], value_input_option="RAW")
            except Exception as e:
                s["hojas"].pop(nombre, None)
                raise ErrorNube(f"No se pudo guardar en Google Sheets ('{nombre}'): {e}") from e
        s["tablas"].pop(nombre, None)


def actualizar(nombre, col_clave, valor, cambios, tid=None):
    """Modifica campos de la fila cuya col_clave == valor."""
    tid, cols = _resolver(nombre, tid)
    with _LOCK:
        s = _store(tid)
        n_total = 0
        libro = _libro(tid)
        if libro is None:
            df = _leer_csv(tid, nombre, cols)
        else:
            try:
                df, n_total = _leer_cloud(tid, nombre, cols)
            except Exception as e:
                raise ErrorNube(f"No se pudo leer '{nombre}' en Google Sheets: {e}") from e
        mask = df[col_clave].astype(str) == str(valor)
        if not mask.any():
            raise KeyError(f"No existe {col_clave}={valor} en {nombre}")
        for c, v in cambios.items():
            if c not in df.columns:
                df[c] = ""
            df.loc[mask, c] = str(v)
        if libro is None:
            _guardar_csv(tid, nombre, df)
        else:
            enc = s["enc"].get(nombre) or cols
            datos = [list(enc)] + df.reindex(columns=enc).fillna("").astype(str).values.tolist()
            while len(datos) < n_total:  # conserva el largo para no dejar filas viejas sueltas
                datos.append([""] * len(enc))
            try:
                _hoja(tid, nombre).update(range_name="A1", values=datos)
            except Exception as e:
                s["hojas"].pop(nombre, None)
                raise ErrorNube(f"No se pudo actualizar '{nombre}' en Google Sheets: {e}") from e
        s["tablas"].pop(nombre, None)


def resumen_tablas(tid=None):
    return {t: len(leer(t, tid=tid)) for t in ESQUEMA}


def log(usuario, accion, detalle="", tid=None):
    """Auditoría del geriátrico. Nunca debe romper la app."""
    try:
        agregar("logs", {"Fecha_Hora": fmt_fh(), "Usuario": usuario, "Accion": accion,
                         "Detalle": str(detalle)[:300]}, tid=tid)
    except Exception:
        pass


def log_control(actor, accion, detalle=""):
    try:
        agregar("logs_control", {"Fecha_Hora": fmt_fh(), "Actor": actor, "Accion": accion,
                                 "Detalle": str(detalle)[:300]})
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────
# Usuarios de un geriátrico y contraseñas
# ──────────────────────────────────────────────────────────────
def hash_pw(pw, sal=None):
    sal = sal or _pysecrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), sal.encode(), 120_000).hex()
    return f"pbkdf2${sal}${h}"


def verificar_pw(pw, guardado):
    guardado = str(guardado)
    if guardado.startswith("pbkdf2$"):
        try:
            _, sal, h = guardado.split("$")
        except ValueError:
            return False
        return hmac.compare_digest(hash_pw(pw, sal).split("$")[2], h)
    return hmac.compare_digest(pw.encode("utf-8"), guardado.encode("utf-8"))  # clave en texto plano


def autenticar(usuario, password):
    """Autentica contra los usuarios del geriátrico activo."""
    df = leer("usuarios")
    f = df[(df["Usuario"].str.lower() == str(usuario).strip().lower()) & (df["Activo"].str.upper() != "NO")]
    if f.empty:
        return None
    reg = f.iloc[0]
    if not verificar_pw(password, reg["Password"]):
        return None
    if not str(reg["Password"]).startswith("pbkdf2$"):  # migra claves antiguas
        actualizar("usuarios", "Usuario", reg["Usuario"], {"Password": hash_pw(password)})
    return reg.to_dict()


# ──────────────────────────────────────────────────────────────
# PROPIETARIO: acceso, clientes, suscripciones y pagos
# ──────────────────────────────────────────────────────────────
def owner_configurado(cfg):
    return bool(cfg.get("owner_password") or cfg.get("owner_password_hash"))


def verificar_owner(cfg, usuario, password):
    u, p = str(usuario).strip().lower(), str(password)
    if not owner_configurado(cfg):
        if hay_credenciales(cfg):
            return False  # en producción el acceso del propietario exige configurarlo en Secrets
        return u == "owner" and p == "owner123"  # solo demostración local
    ok_u = hmac.compare_digest(u.encode(), str(cfg.get("owner_user") or "owner").strip().lower().encode())
    ok_p = verificar_pw(p, cfg.get("owner_password_hash") or cfg.get("owner_password"))
    return ok_u and ok_p


def buscar_cliente(codigo):
    cod = str(codigo).strip().upper()
    if not cod:
        return None
    df = leer("clientes")
    f = df[df["Codigo"].str.upper() == cod]
    return None if f.empty else f.iloc[0].to_dict()


def estado_servicio(cli):
    """(tiene_acceso, motivo, dias_para_vencer|None)"""
    if str(cli.get("Estado", "")).strip() != "Activo":
        return False, "El servicio está suspendido.", None
    v = parsear_fecha(cli.get("Vence", ""))
    if v is None:
        return True, "", None
    dias = (v - hoy()).days
    gracia = int(_num(cli.get("Dias_Gracia", 0)))
    if dias + gracia < 0:
        return False, f"La suscripción venció el {v.strftime('%d/%m/%Y')}.", dias
    return True, "", dias


def etiqueta_servicio(cli):
    """(texto, nivel) para mostrar el estado de un cliente."""
    ok, _, dias = estado_servicio(cli)
    if str(cli.get("Estado", "")).strip() != "Activo":
        return "Suspendido", "crit"
    if dias is None:
        return "Activo · sin vencimiento", "ok"
    if not ok:
        return f"Vencido hace {-dias} d", "crit"
    if dias < 0:
        return f"En gracia · venció hace {-dias} d", "warn"
    if dias <= 7:
        return f"Vence en {dias} d", "warn"
    return f"Vigente · {dias} d", "ok"


_ALF = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generar_codigo():
    existentes = set(leer("clientes")["Codigo"].str.upper())
    while True:
        c = "GER-" + "".join(_pysecrets.choice(_ALF) for _ in range(6))
        if c not in existentes:
            return c


def clave_temporal():
    return "".join(_pysecrets.choice(_ALF) for _ in range(10))


def crear_cliente(cfg, datos, admin_user, admin_pw, actor="propietario"):
    """Alta de un geriátrico: código, bóveda propia y su primer administrador. Devuelve el código."""
    codigo = generar_codigo()
    modo = datos.get("Modo_Boveda", "Central")
    sheet_id, carpeta = str(datos.get("Sheet_ID", "")).strip(), ""
    if nube_activa():
        if modo == "Central":
            sheet_id, carpeta = crear_boveda(cfg, codigo, datos["Nombre"])
        elif not sheet_id:
            raise ErrorNube("En modo «Propia del cliente» debe pegar el ID de la hoja que el cliente compartió.")
    fila = {c: "" for c in ESQUEMA_CONTROL["clientes"]}
    fila.update(datos, Codigo=codigo, Estado="Activo", Modo_Boveda=modo, Sheet_ID=sheet_id,
                Carpeta_URL=carpeta, Creado=hoy().isoformat())
    agregar("clientes", fila)
    log_control(actor, "CREA_CLIENTE", f"{codigo} · {datos['Nombre']} · {modo}")
    if not abrir_tenant(cfg, fila, forzar=True):
        raise ErrorNube(f"Cliente {codigo} creado, pero no se pudo abrir su bóveda: {estado_nube(codigo)['error']}")
    agregar("usuarios", {"Usuario": admin_user.strip().lower(), "Password": hash_pw(admin_pw), "Rol": "Administrador",
                         "Alias": "Administrador", "Reg_Profesional": "", "Activo": "SI", "Cambiar_Clave": "SI"}, tid=codigo)
    return codigo


def registrar_pago(codigo, monto, meses, metodo, nota="", actor="propietario"):
    """Registra un pago y extiende la vigencia (reactiva si estaba suspendido)."""
    cli = buscar_cliente(codigo)
    if cli is None:
        raise KeyError(codigo)
    base = max(parsear_fecha(cli["Vence"]) or hoy(), hoy())
    nueva = sumar_meses(base, int(meses))
    agregar("pagos", {"ID": nueva_id("PG"), "Codigo": codigo, "Fecha": hoy().isoformat(), "Monto": monto,
                      "Metodo": metodo, "Periodo": f"{base.isoformat()} → {nueva.isoformat()}", "Nota": nota,
                      "Registrado_Por": actor})
    actualizar("clientes", "Codigo", codigo, {"Vence": nueva.isoformat(), "Estado": "Activo"})
    log_control(actor, "PAGO", f"{codigo} · {monto} · hasta {nueva.isoformat()}")
    return nueva


def cop(n):
    return "$ " + f"{int(round(_num(n))):,}".replace(",", ".")


# ──────────────────────────────────────────────────────────────
# Sello de integridad de las notas SOAPIE
# ──────────────────────────────────────────────────────────────
_CAMPOS_SELLO = ["ID_Nota", "Cedula", "Fecha_Hora", "Turno", "Autor", "Subjetivo", "Objetivo",
                 "Analisis", "Plan", "Intervencion", "Evaluacion"]


def sello_nota(r):
    base = "|".join(str(r.get(c, "")).replace("\r\n", "\n").strip() for c in _CAMPOS_SELLO)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:20].upper()


# ──────────────────────────────────────────────────────────────
# Signos vitales: alertas automáticas (adulto mayor)
# ──────────────────────────────────────────────────────────────
def evaluar_signos(sis, dia, fc, fr, temp, sat, glu, dolor):
    """Devuelve lista de (texto, nivel) con nivel 'crit' o 'warn'. 0 = no medido."""
    a = []
    if sis >= 180 or dia >= 120:
        a.append(("Crisis hipertensiva", "crit"))
    elif sis >= 140 or dia >= 90:
        a.append(("Hipertensión", "warn"))
    elif sis < 90 or dia < 60:
        a.append(("Hipotensión", "crit" if sis < 80 else "warn"))
    if fc > 120 or 0 < fc < 40:
        a.append(("Frecuencia cardíaca crítica", "crit"))
    elif fc > 100:
        a.append(("Taquicardia", "warn"))
    elif 0 < fc < 60:
        a.append(("Bradicardia", "warn"))
    if fr > 28 or 0 < fr < 8:
        a.append(("Frecuencia respiratoria crítica", "crit"))
    elif fr > 20:
        a.append(("Taquipnea", "warn"))
    elif 0 < fr < 12:
        a.append(("Bradipnea", "warn"))
    if temp >= 39:
        a.append(("Fiebre alta", "crit"))
    elif temp >= 38:
        a.append(("Fiebre", "warn"))
    elif temp >= 37.5:
        a.append(("Febrícula", "warn"))
    elif 0 < temp < 35.5:
        a.append(("Hipotermia", "crit"))
    if 0 < sat < 90:
        a.append(("Hipoxemia", "crit"))
    elif 0 < sat < 94:
        a.append(("Saturación baja", "warn"))
    if glu:
        if glu < 70:
            a.append(("Hipoglucemia", "crit"))
        elif glu > 250:
            a.append(("Hiperglucemia severa", "crit"))
        elif glu > 180:
            a.append(("Hiperglucemia", "warn"))
    if dolor >= 7:
        a.append(("Dolor severo", "crit"))
    elif dolor >= 4:
        a.append(("Dolor moderado", "warn"))
    return a


# ──────────────────────────────────────────────────────────────
# Escalas de valoración geriátrica
# ──────────────────────────────────────────────────────────────
_SN = [("No", 0), ("Sí", 1)]

ESCALAS = {
    "Barthel": {
        "titulo": "Índice de Barthel · actividades básicas de la vida diaria (0-100)",
        "items": [
            {"k": "comer", "t": "Comer", "o": [("Incapaz / dependiente", 0), ("Necesita ayuda (cortar, untar…)", 5), ("Independiente", 10)]},
            {"k": "lavarse", "t": "Lavarse (bañarse)", "o": [("Dependiente", 0), ("Independiente", 5)]},
            {"k": "vestirse", "t": "Vestirse", "o": [("Dependiente", 0), ("Necesita ayuda", 5), ("Independiente", 10)]},
            {"k": "arreglarse", "t": "Arreglarse (aseo personal)", "o": [("Necesita ayuda", 0), ("Independiente", 5)]},
            {"k": "deposicion", "t": "Control de deposición", "o": [("Incontinente", 0), ("Accidente ocasional", 5), ("Continente", 10)]},
            {"k": "miccion", "t": "Control de micción", "o": [("Incontinente / sondado", 0), ("Accidente ocasional", 5), ("Continente", 10)]},
            {"k": "retrete", "t": "Uso del retrete", "o": [("Dependiente", 0), ("Necesita ayuda", 5), ("Independiente", 10)]},
            {"k": "traslado", "t": "Traslado sillón ↔ cama", "o": [("Incapaz", 0), ("Gran ayuda", 5), ("Mínima ayuda", 10), ("Independiente", 15)]},
            {"k": "deambulacion", "t": "Deambulación", "o": [("Inmóvil", 0), ("Independiente en silla de ruedas", 5), ("Anda con ayuda", 10), ("Independiente", 15)]},
            {"k": "escaleras", "t": "Subir y bajar escaleras", "o": [("Incapaz", 0), ("Necesita ayuda", 5), ("Independiente", 10)]},
        ],
    },
    "Braden": {
        "titulo": "Escala de Braden · riesgo de úlceras por presión (6-23)",
        "items": [
            {"k": "percepcion", "t": "Percepción sensorial", "o": [("Completamente limitada", 1), ("Muy limitada", 2), ("Ligeramente limitada", 3), ("Sin limitaciones", 4)]},
            {"k": "humedad", "t": "Exposición a la humedad", "o": [("Constantemente húmeda", 1), ("Muy húmeda", 2), ("Ocasionalmente húmeda", 3), ("Raramente húmeda", 4)]},
            {"k": "actividad", "t": "Actividad", "o": [("Encamado", 1), ("En silla", 2), ("Deambula ocasionalmente", 3), ("Deambula con frecuencia", 4)]},
            {"k": "movilidad", "t": "Movilidad", "o": [("Completamente inmóvil", 1), ("Muy limitada", 2), ("Ligeramente limitada", 3), ("Sin limitaciones", 4)]},
            {"k": "nutricion", "t": "Nutrición", "o": [("Muy pobre", 1), ("Probablemente inadecuada", 2), ("Adecuada", 3), ("Excelente", 4)]},
            {"k": "roce", "t": "Roce y peligro de lesiones", "o": [("Problema", 1), ("Problema potencial", 2), ("No existe problema aparente", 3)]},
        ],
    },
    "Downton": {
        "titulo": "Escala de Downton · riesgo de caídas (≥3 = riesgo alto)",
        "items": [
            {"k": "caidas", "t": "Caídas previas", "o": _SN},
            {"k": "m_sedantes", "t": "Medicamento: tranquilizantes / sedantes", "o": _SN},
            {"k": "m_diureticos", "t": "Medicamento: diuréticos", "o": _SN},
            {"k": "m_hipotensores", "t": "Medicamento: hipotensores (no diuréticos)", "o": _SN},
            {"k": "m_parkinson", "t": "Medicamento: antiparkinsonianos", "o": _SN},
            {"k": "m_antidep", "t": "Medicamento: antidepresivos", "o": _SN},
            {"k": "m_otros", "t": "Medicamento: otros que afecten el equilibrio", "o": _SN},
            {"k": "d_visual", "t": "Déficit sensorial: alteración visual", "o": _SN},
            {"k": "d_auditivo", "t": "Déficit sensorial: alteración auditiva", "o": _SN},
            {"k": "d_extrem", "t": "Déficit sensorial: alteración en extremidades", "o": _SN},
            {"k": "mental", "t": "Estado mental", "o": [("Orientado", 0), ("Confuso", 1)]},
            {"k": "marcha", "t": "Deambulación", "o": [("Normal", 0), ("Segura con ayuda", 1), ("Insegura (con o sin ayuda)", 1), ("Imposible", 1)]},
            {"k": "edad70", "t": "Edad ≥ 70 años", "o": _SN},
        ],
    },
    "Pfeiffer": {
        "titulo": "Cuestionario de Pfeiffer (SPMSQ) · deterioro cognitivo (errores)",
        "items": [{"k": f"p{i}", "t": t, "o": [("Correcta", 0), ("Error", 1)]} for i, t in enumerate([
            "¿Qué día es hoy? (día, mes y año)",
            "¿Qué día de la semana es hoy?",
            "¿Cuál es el nombre de este lugar?",
            "¿Cuál es su número de teléfono? (o su dirección)",
            "¿Qué edad tiene?",
            "¿Cuál es su fecha de nacimiento?",
            "¿Quién es el presidente actual del país?",
            "¿Quién fue el presidente anterior?",
            "¿Cuál es el apellido de soltera de su madre?",
            "Restar de 3 en 3 desde 20 hacia atrás",
        ], start=1)],
    },
}

EDUCACION = {"primaria": "Primaria o menos", "media": "Secundaria / bachillerato", "superior": "Estudios superiores"}


def interpretar(escala, p, extra=None):
    """Devuelve (texto, nivel) con nivel 'ok' | 'warn' | 'crit'."""
    if escala == "Barthel":
        if p >= 100:
            return "Independiente", "ok"
        if p >= 91:
            return "Dependencia leve", "ok"
        if p >= 61:
            return "Dependencia moderada", "warn"
        if p >= 21:
            return "Dependencia severa", "crit"
        return "Dependencia total", "crit"
    if escala == "Braden":
        if p >= 19:
            return "Sin riesgo de úlcera por presión", "ok"
        if p >= 15:
            return "Riesgo bajo", "warn"
        if p >= 13:
            return "Riesgo moderado", "warn"
        if p >= 10:
            return "Riesgo alto", "crit"
        return "Riesgo muy alto", "crit"
    if escala == "Downton":
        return ("Alto riesgo de caídas", "crit") if p >= 3 else ("Bajo riesgo de caídas", "ok")
    if escala == "Pfeiffer":
        aj = max(0, min(10, p + {"primaria": -1, "superior": 1}.get(extra, 0)))
        if aj <= 2:
            t, n = "Función intelectual normal", "ok"
        elif aj <= 4:
            t, n = "Deterioro cognitivo leve", "warn"
        elif aj <= 7:
            t, n = "Deterioro cognitivo moderado", "crit"
        else:
            t, n = "Deterioro cognitivo severo", "crit"
        return f"{t} (errores ajustados por escolaridad: {aj})", n
    return "", "ok"
