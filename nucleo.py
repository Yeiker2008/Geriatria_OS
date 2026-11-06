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
import json
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
                   "Estado", "F_Ingreso", "F_Egreso", "Motivo_Egreso",
                   "Mensualidad", "Pagado_Hasta"],
    "signos_vitales": ["ID", "Cedula", "Fecha_Hora", "TA_Sis", "TA_Dia", "FC", "FR", "Temp",
                       "SatO2", "Glucemia", "Dolor", "Peso", "Alertas", "Autor"],
    "notas_soapie": ["ID_Nota", "Cedula", "Fecha_Hora", "Turno", "Autor", "Subjetivo", "Objetivo",
                     "Analisis", "Plan", "Intervencion", "Evaluacion", "Sello", "Hora_Inicio"],
    "kardex_meds": ["ID_Med", "Cedula", "Medicamento", "Dosis", "Via", "Frecuencia", "Horarios",
                    "Indicaciones", "Estado", "Prescrito_Por", "F_Inicio", "F_Suspension", "Unidades_Dosis"],
    "admin_meds": ["ID", "ID_Med", "Cedula", "Fecha_Hora", "Resultado", "Observacion", "Autor",
                   "Hora_Programada", "Turno", "Minutos_Desvio"],
    "escalas": ["ID", "Cedula", "Fecha_Hora", "Escala", "Puntaje", "Interpretacion", "Detalle", "Autor"],
    # --- Enfermería: inventarios por residente ---
    "mov_meds": ["ID", "Cedula", "Medicamento", "Tipo", "Cantidad", "Fecha_Hora", "Autor", "Nota"],
    "pertenencias": ["ID", "Cedula", "Fecha_Hora", "Tipo", "Descripcion", "Cantidad", "Estado",
                     "Archivo_ID", "Autor"],
    "aseo_personal": ["ID", "Cedula", "Fecha_Hora", "Articulo", "Tipo", "Cantidad", "Origen", "Autor", "Nota"],
    "salidas": ["ID", "Cedula", "F_Salida", "Motivo", "Destino", "Acompanante", "Items_Salida",
                "Autor_Salida", "Estado", "F_Retorno", "Items_Retorno", "Observacion_Retorno",
                "Autor_Retorno", "Faltantes"],
    # --- Cocina y Servicios generales (misma estructura, columna Seccion) ---
    "inv_productos": ["Seccion", "Producto", "Unidad", "Minimo", "Consumo_Diario", "Activo"],
    "inv_mov": ["ID", "Seccion", "Producto", "Tipo", "Cantidad", "Fecha_Hora", "Uso", "Dias_Estimados", "Autor"],
    "tareas_aseo": ["ID", "Fecha_Hora", "Seccion", "Area", "Tipo", "Descripcion", "Productos", "Autor", "Rol"],
    "indicaciones": ["ID", "Seccion", "Fecha_Hora", "Titulo", "Texto", "Autor", "Activa"],
    # --- Familias ---
    "pagos_familia": ["ID", "Cedula", "Fecha", "Monto", "Metodo", "Pagado_Hasta", "Dias_Atraso", "Autor"],
    "comunicaciones": ["ID", "Cedula", "Fecha_Hora", "Tipo", "Canal", "Mensaje", "Autor"],
    "plantillas_contrato": ["ID", "Nombre", "Archivo_ID", "Fecha_Hora", "Autor"],
    "contratos": ["ID", "Cedula", "Plantilla", "Fecha_Hora", "Archivo_ID", "Autor"],
    # --- Archivos (índice de todo lo que vive en la carpeta del geriátrico) ---
    "archivos": ["ID", "Cedula", "Categoria", "Nombre", "Drive_ID", "Ruta_Local", "Fecha_Hora", "Autor", "Tamano"],
    "usuarios": ["Usuario", "Password", "Rol", "Alias", "Reg_Profesional", "Activo", "Cambiar_Clave"],
    "logs": ["Fecha_Hora", "Usuario", "Accion", "Detalle", "Rol", "Pagina", "Tipo"],
}

# Tablas que NO se pueden modificar una vez escritas (ley: notas y registros clínicos inalterables)
PROTEGIDAS = {"notas_soapie", "signos_vitales", "admin_meds", "escalas", "logs", "mov_meds",
              "aseo_personal", "inv_mov", "pagos_familia", "comunicaciones"}

# Tablas del PROPIETARIO (solo él las ve): clientes, pagos y auditoría de su panel
ESQUEMA_CONTROL = {
    "clientes": ["Codigo", "Nombre", "NIT", "Contacto", "Telefono", "Email", "Plan", "Max_Usuarios",
                 "Precio_Mensual", "Estado", "Vence", "Dias_Gracia", "Modo_Boveda", "Sheet_ID",
                 "Carpeta_URL", "Creado", "Notas", "Max_Residentes", "Modulos", "Roles_Permitidos"],
    "pagos": ["ID", "Codigo", "Fecha", "Monto", "Metodo", "Periodo", "Nota", "Registrado_Por", "Dias_Atraso"],
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
    q = f"name='{nombre.replace(chr(92), chr(92) * 2).replace(chr(39), chr(92) + chr(39))}' and mimeType='{_MIME_CARPETA}' and trashed=false"
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
    if nombre in PROTEGIDAS:
        raise PermissionError(f"Los registros de '{nombre}' son inalterables y no se pueden modificar.")
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
                _hoja(tid, nombre).update(range_name="A1", values=datos, value_input_option="RAW")
            except Exception as e:
                s["hojas"].pop(nombre, None)
                raise ErrorNube(f"No se pudo actualizar '{nombre}' en Google Sheets: {e}") from e
        s["tablas"].pop(nombre, None)


def resumen_tablas(tid=None):
    return {t: len(leer(t, tid=tid)) for t in ESQUEMA}


def contexto(rol="", pagina=""):
    """La app fija aquí el rol y la pantalla actuales; quedan escritos en cada registro de auditoría."""
    _CTX.rol, _CTX.pagina = rol, pagina


def log(usuario, accion, detalle="", tid=None, tipo="DATO"):
    """Auditoría del geriátrico. Nunca debe romper la app."""
    try:
        agregar("logs", {"Fecha_Hora": fmt_fh(), "Usuario": usuario, "Accion": accion,
                         "Detalle": str(detalle)[:300], "Rol": getattr(_CTX, "rol", ""),
                         "Pagina": getattr(_CTX, "pagina", ""), "Tipo": tipo}, tid=tid)
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
_ITER = 310_000     # vueltas de PBKDF2 para claves nuevas
_ITER_VIEJO = 120_000  # formato anterior: pbkdf2$sal$hash


def hash_pw(pw, sal=None, iteraciones=None):
    sal = sal or _pysecrets.token_hex(16)
    it = iteraciones or _ITER
    h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), sal.encode(), it).hex()
    return f"pbkdf2${it}${sal}${h}"


def verificar_pw(pw, guardado):
    guardado = str(guardado)
    if guardado.startswith("pbkdf2$"):
        partes = guardado.split("$")
        try:
            if len(partes) == 4:
                _, it, sal, h = partes
                it = int(it)
            else:
                _, sal, h = partes
                it = _ITER_VIEJO
        except ValueError:
            return False
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), sal.encode(), it).hex()
        return hmac.compare_digest(calc, h)
    return hmac.compare_digest(pw.encode("utf-8"), guardado.encode("utf-8"))  # clave en texto plano (migración)


def necesita_rehash(guardado):
    g = str(guardado)
    return not (g.startswith("pbkdf2$") and len(g.split("$")) == 4 and int(g.split("$")[1]) >= _ITER)


def validar_clave(pw, estricta=False):
    """Devuelve None si la clave es aceptable, o el motivo por el que no."""
    minimo = 12 if estricta else 8
    if len(pw) < minimo:
        return f"Debe tener al menos {minimo} caracteres."
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Debe combinar letras y números."
    if pw.lower() in {"12345678", "password1", "contrasena1", "geriatria1", "admin1234", "123456789a"}:
        return "Esa clave es muy fácil de adivinar."
    return None


_DUMMY = hash_pw("relleno-para-igualar-tiempos")


def autenticar(usuario, password):
    """Autentica contra los usuarios del geriátrico activo."""
    df = leer("usuarios")
    f = df[(df["Usuario"].str.lower() == str(usuario).strip().lower()) & (df["Activo"].str.upper() != "NO")]
    if f.empty:
        verificar_pw(password, _DUMMY)  # mismo tiempo de respuesta: no revela si el usuario existe
        return None
    reg = f.iloc[0]
    if not verificar_pw(password, reg["Password"]):
        return None
    if necesita_rehash(reg["Password"]):  # migra claves antiguas al formato más fuerte
        actualizar("usuarios", "Usuario", reg["Usuario"], {"Password": hash_pw(password)})
    return reg.to_dict()


# ──────────────────────────────────────────────────────────────
# PROPIETARIO: acceso, clientes, suscripciones y pagos
# ──────────────────────────────────────────────────────────────
def _owners(cfg):
    """Propietarios habilitados: {usuario: clave_o_hash}. Soporta uno solo (owner_user/owner_password)
    o varios socios con la sección [owners.<usuario>] password_hash = "..." en Secrets."""
    out = {}
    try:
        for u, v in dict(cfg.get("owners") or {}).items():
            v = dict(v) if not isinstance(v, str) else {"password_hash": v}
            pw = v.get("password_hash") or v.get("password")
            if pw:
                out[str(u).strip().lower()] = pw
    except Exception:
        pass
    pw = cfg.get("owner_password_hash") or cfg.get("owner_password")
    if pw:
        out.setdefault(str(cfg.get("owner_user") or "owner").strip().lower(), pw)
    return out


def owner_configurado(cfg):
    return bool(_owners(cfg))


def es_codigo_owner(cfg, codigo):
    """¿El «código del geriátrico» escrito es en realidad el código secreto del propietario?"""
    esperado = str(cfg.get("owner_code") or ("OWNER" if not hay_credenciales(cfg) else "")).strip().upper()
    if not esperado:
        return False
    return hmac.compare_digest(str(codigo).strip().upper().encode(), esperado.encode())


def verificar_owner(cfg, usuario, password):
    u, p = str(usuario).strip().lower(), str(password)
    owners = _owners(cfg)
    if not owners:
        if hay_credenciales(cfg):
            return False  # en producción el acceso del propietario exige configurarlo en Secrets
        return u == "owner" and p == "owner123"  # solo demostración local
    guardado = owners.get(u)
    if guardado is None:
        verificar_pw(p, _DUMMY)
        return False
    return verificar_pw(p, guardado)


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
    vence_ant = parsear_fecha(cli["Vence"])
    atraso = (hoy() - vence_ant).days if vence_ant else ""   # >0 = pagó tarde · <=0 = a tiempo o adelantado
    base = max(vence_ant or hoy(), hoy())
    nueva = sumar_meses(base, int(meses))
    agregar("pagos", {"ID": nueva_id("PG"), "Codigo": codigo, "Fecha": hoy().isoformat(), "Monto": monto,
                      "Metodo": metodo, "Periodo": f"{base.isoformat()} → {nueva.isoformat()}", "Nota": nota,
                      "Registrado_Por": actor, "Dias_Atraso": atraso})
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
    if str(r.get("Hora_Inicio", "")).strip():  # las notas antiguas no la tienen: su sello no cambia
        base += "|" + str(r["Hora_Inicio"]).strip()
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


# ──────────────────────────────────────────────────────────────
# Planes, módulos, roles y permisos
# ──────────────────────────────────────────────────────────────
MODULOS = {"Enfermeria": "🩺 Enfermería", "Cocina": "🍳 Cocina", "Aseo": "🧹 Servicios generales",
           "Familias": "👨‍👩‍👧 Familias", "Contratos": "📄 Contratos", "Archivos": "🗂 Archivos",
           "Monitor": "🖥 Monitor de actividad"}

R_ADMIN, R_ENF, R_AUX, R_MED = "Administrador", "Enfermero/a", "Auxiliar de enfermería", "Médico/a"
R_COC, R_AUXC, R_ASEO, R_FAM = "Cocinero/a", "Auxiliar de cocina", "Servicios generales", "Trabajo social / Familias"
ROLES_TODOS = [R_ADMIN, R_ENF, R_AUX, R_MED, R_COC, R_AUXC, R_ASEO, R_FAM]

PLANES = {
    "Básico": {"max_usuarios": 7, "max_residentes": 15, "modulos": ["Enfermeria"],
               "roles": [R_ADMIN, R_ENF, R_AUX],
               "beneficios": ["Hasta 15 residentes y 7 usuarios", "Enfermería completa (notas, kardex, signos)"]},
    "Estándar": {"max_usuarios": 15, "max_residentes": 30, "modulos": ["Enfermeria", "Cocina", "Aseo"],
                 "roles": [R_ADMIN, R_ENF, R_AUX, R_COC, R_AUXC, R_ASEO],
                 "beneficios": ["Hasta 30 residentes y 15 usuarios", "Cocina y servicios generales"]},
    "Pro": {"max_usuarios": 30, "max_residentes": 60,
            "modulos": ["Enfermeria", "Cocina", "Aseo", "Familias", "Archivos"],
            "roles": [R_ADMIN, R_ENF, R_AUX, R_MED, R_COC, R_AUXC, R_ASEO, R_FAM],
            "beneficios": ["Hasta 60 residentes y 30 usuarios", "Familias: alertas y reportes por WhatsApp",
                           "Explorador de archivos", "Rol de médico"]},
    "Premium": {"max_usuarios": 80, "max_residentes": 150, "modulos": list(MODULOS),
                "roles": list(ROLES_TODOS),
                "beneficios": ["Hasta 150 residentes y 80 usuarios", "Generador de contratos",
                               "Monitor de actividad en tiempo real", "Aparece en el ranking de recomendados",
                               "Soporte prioritario"]},
    "Personalizado": {"max_usuarios": 10, "max_residentes": 25, "modulos": ["Enfermeria"],
                      "roles": [R_ADMIN, R_ENF, R_AUX], "beneficios": ["Se arma a la medida"]},
}

# Qué roles entran a cada pantalla. El Administrador entra a todas (si el plan incluye el módulo).
PAGINAS_GERIATRICO = [
    # clave, icono, nombre, módulo, roles permitidos (None = todos)
    ("Hub", "🏠", "Inicio", None, None),
    ("Residentes", "👴", "Residentes", "Enfermeria", {R_ADMIN, R_ENF, R_AUX, R_MED, R_FAM}),
    ("Medicamentos", "💊", "Dar medicamentos", "Enfermeria", {R_ADMIN, R_ENF, R_AUX, R_MED}),
    ("Vitales", "🩺", "Signos vitales", "Enfermeria", {R_ADMIN, R_ENF, R_AUX, R_MED}),
    ("SOAPIE", "📝", "Notas de enfermería", "Enfermeria", {R_ADMIN, R_ENF, R_AUX, R_MED}),
    ("Kardex", "📋", "Kardex y stock de medicinas", "Enfermeria", {R_ADMIN, R_ENF, R_AUX, R_MED}),
    ("Pertenencias", "🎒", "Pertenencias y aseo personal", "Enfermeria", {R_ADMIN, R_ENF, R_AUX}),
    ("Salidas", "🚪", "Salidas y regresos", "Enfermeria", {R_ADMIN, R_ENF, R_AUX}),
    ("Escalas", "📊", "Escalas geriátricas", "Enfermeria", {R_ADMIN, R_ENF, R_AUX, R_MED}),
    ("Cocina", "🍳", "Cocina", "Cocina", {R_ADMIN, R_COC, R_AUXC}),
    ("Aseo", "🧹", "Servicios generales", "Aseo", {R_ADMIN, R_ASEO}),
    ("Familias", "👨‍👩‍👧", "Familias", "Familias", {R_ADMIN, R_FAM}),
    ("Contratos", "📄", "Contratos", "Contratos", {R_ADMIN, R_FAM}),
    ("Archivos", "🗂", "Archivos", "Archivos", {R_ADMIN}),
    ("Monitor", "🖥", "Monitor de actividad", "Monitor", {R_ADMIN}),
    ("Admin", "⚙️", "Administración", None, {R_ADMIN}),
]


def modulos_cliente(cli):
    """Módulos que el plan del geriátrico incluye (Enfermería siempre)."""
    txt = str((cli or {}).get("Modulos", "")).strip()
    if not txt:
        plan = PLANES.get(str((cli or {}).get("Plan", "")), PLANES["Pro"])
        return set(plan["modulos"]) | {"Enfermeria"}
    return {m.strip() for m in txt.split(",") if m.strip()} | {"Enfermeria"}


def roles_cliente(cli):
    txt = str((cli or {}).get("Roles_Permitidos", "")).strip()
    if not txt:
        plan = PLANES.get(str((cli or {}).get("Plan", "")), PLANES["Pro"])
        return list(plan["roles"])
    r = [x.strip() for x in txt.split(",") if x.strip()]
    return r if R_ADMIN in r else [R_ADMIN] + r


def paginas_permitidas(rol, cli):
    mods = modulos_cliente(cli)
    return [(k, i, n) for k, i, n, m, roles in PAGINAS_GERIATRICO
            if (m is None or m in mods) and (roles is None or rol in roles)]


def puede_ver(rol, cli, pagina):
    return pagina in {k for k, _, _ in paginas_permitidas(rol, cli)}


def puede_admitir(cli):
    """(puede, motivo): respeta el límite de residentes del plan."""
    mx = int(_num((cli or {}).get("Max_Residentes", 0)))
    if not mx:
        return True, ""
    act = leer("residentes")
    n = int((act["Estado"] != "Egresado").sum())
    return (n < mx), f"Su plan permite {mx} residentes activos (hoy tiene {n})."


# ──────────────────────────────────────────────────────────────
# Seguridad: bloqueo por intentos fallidos (en el servidor, no se evade abriendo otra pestaña)
# ──────────────────────────────────────────────────────────────
_INTENTOS = {}   # clave -> {"fallos": n, "hasta": timestamp}


def _clave_intento(*partes):
    return hashlib.sha256("|".join(str(p).strip().lower() for p in partes).encode()).hexdigest()[:24]


def segundos_bloqueo(*partes):
    r = _INTENTOS.get(_clave_intento(*partes))
    return max(0, int(r["hasta"] - time.time())) if r else 0


def registrar_fallo(*partes, umbral=5):
    with _LOCK:
        r = _INTENTOS.setdefault(_clave_intento(*partes), {"fallos": 0, "hasta": 0.0})
        r["fallos"] += 1
        if r["fallos"] % umbral == 0:   # cada `umbral` fallos: 5, 10, 20, 40, 60 minutos
            r["hasta"] = time.time() + min(60, 5 * 2 ** (r["fallos"] // umbral - 1)) * 60
        return r["fallos"]


def limpiar_fallos(*partes):
    _INTENTOS.pop(_clave_intento(*partes), None)


# ──────────────────────────────────────────────────────────────
# Exportación segura y archivos
# ──────────────────────────────────────────────────────────────
def csv_seguro(df):
    """CSV en bytes; neutraliza celdas que Excel/Sheets interpretarían como fórmulas."""
    d = df.copy().astype(str)
    d = d.apply(lambda c: c.map(lambda v: "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") and not _es_numero(v) else v))
    return d.to_csv(index=False).encode("utf-8-sig")


def _es_numero(v):
    try:
        float(v.replace(",", "."))
        return True
    except ValueError:
        return False


def nombre_seguro(n, largo=80):
    n = re.sub(r"[^\w.\- ]", "_", str(n), flags=re.UNICODE).strip(" .") or "archivo"
    return n[:largo]


def _id_carpeta(url):
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", str(url or ""))
    return m.group(1) if m else None


_CARPETAS = {}   # (tid, ruta) -> id de carpeta en Drive


def _raiz_geriatrico(a, tid):
    s = _store(tid)
    rid = _id_carpeta(s.get("carpeta_url"))
    if rid:
        return rid
    sid = s["libro"].id
    r = _chk(a["drive"].get(f"{_DRIVE}/{sid}", params={"fields": "parents"})).json()
    if r.get("parents"):
        return r["parents"][0]
    raise ErrorNube("No se encontró la carpeta de este geriátrico en Drive.")


def _ruta_drive(a, tid, cedula, nombre_res, categoria):
    """Carpeta del geriátrico ▸ «cédula · nombre» ▸ categoría (se crean solas la primera vez)."""
    clave = (tid, str(cedula), categoria)
    if clave in _CARPETAS:
        return _CARPETAS[clave]
    padre = _raiz_geriatrico(a, tid)
    if cedula:
        padre = _asegurar_carpeta(a["drive"], f"{cedula} · {nombre_res}", padre)
    fid = _asegurar_carpeta(a["drive"], categoria, padre)
    _CARPETAS[clave] = fid
    return fid


def guardar_archivo(cfg, cedula, nombre_res, categoria, nombre_archivo, datos, mime, autor):
    """Guarda un archivo en la carpeta del residente (Drive) o en disco (demostración). Devuelve la fila de 'archivos'."""
    tid = tenant_actual()
    aid, nom = nueva_id("AR"), nombre_seguro(nombre_archivo)
    fila = {"ID": aid, "Cedula": cedula or "", "Categoria": categoria, "Nombre": nom, "Drive_ID": "", "Ruta_Local": "",
            "Fecha_Hora": fmt_fh(), "Autor": autor, "Tamano": len(datos)}
    if _libro(tid) is None:
        d = os.path.join(DATA_DIR, re.sub(r"[^A-Za-z0-9_-]", "_", tid), "archivos",
                         re.sub(r"[^A-Za-z0-9_-]", "_", str(cedula or "general")), nombre_seguro(categoria))
        os.makedirs(d, exist_ok=True)
        ruta = os.path.join(d, f"{aid}_{nom}")
        with open(ruta, "wb") as f:
            f.write(datos)
        fila["Ruta_Local"] = ruta
    else:
        try:
            a = _auth(cfg)
            carpeta = _ruta_drive(a, tid, cedula, nombre_res, categoria)
            b = _pysecrets.token_hex(12)
            meta = json.dumps({"name": f"{aid}_{nom}", "parents": [carpeta]})
            cuerpo = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n--{b}\r\n"
                      f"Content-Type: {mime}\r\n\r\n").encode() + datos + f"\r\n--{b}--".encode()
            r = _chk(a["drive"].post("https://www.googleapis.com/upload/drive/v3/files",
                                     params={"uploadType": "multipart", "fields": "id"}, data=cuerpo,
                                     headers={"Content-Type": f"multipart/related; boundary={b}"}))
            fila["Drive_ID"] = r.json()["id"]
        except ErrorNube:
            raise
        except Exception as e:
            raise ErrorNube(f"No se pudo subir el archivo a Drive: {e}") from e
    agregar("archivos", fila)
    return fila


def leer_archivo(cfg, fila):
    """Bytes de un archivo registrado en 'archivos' (o None si no está)."""
    if fila.get("Ruta_Local"):
        ruta = os.path.abspath(fila["Ruta_Local"])
        if not ruta.startswith(os.path.abspath(DATA_DIR)) or not os.path.exists(ruta):
            return None
        with open(ruta, "rb") as f:
            return f.read()
    if fila.get("Drive_ID"):
        a = _auth(cfg)
        return _chk(a["drive"].get(f"{_DRIVE}/{fila['Drive_ID']}", params={"alt": "media"})).content
    return None


def buscar_archivo(archivo_id):
    df = leer("archivos")
    f = df[df["ID"] == str(archivo_id)]
    return None if f.empty else f.iloc[0].to_dict()


# ──────────────────────────────────────────────────────────────
# Medicamentos: horarios, ronda del día, administración con hora exacta y stock
# ──────────────────────────────────────────────────────────────
TURNOS = ["Mañana (07:00 - 13:00)", "Tarde (13:00 - 19:00)", "Noche (19:00 - 07:00)"]
_VECES = {"Cada 4 h": 6, "Cada 6 h": 4, "Cada 8 h": 3, "Cada 12 h": 2, "Cada 24 h": 1}
TOLERANCIA_MIN = 30   # minutos de margen antes de marcar una dosis como atrasada


def turno_de(dt=None):
    hh = (dt or ahora()).hour
    return TURNOS[0] if 7 <= hh < 13 else TURNOS[1] if 13 <= hh < 19 else TURNOS[2]


def horarios_lista(txt):
    """'8:00, 20:00' -> ['08:00', '20:00']"""
    out = []
    for h_, m_ in re.findall(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", str(txt)):
        out.append(f"{int(h_):02d}:{m_}")
    return sorted(set(out))


def dosis_por_dia(med):
    n = len(horarios_lista(med.get("Horarios", ""))) or _VECES.get(str(med.get("Frecuencia", "")), 0)
    return n * (_num(med.get("Unidades_Dosis", 1), 1) or 1)


def _hora_a_dt(hhmm, dia=None):
    h_, m_ = hhmm.split(":")
    d = dia or hoy()
    return datetime(d.year, d.month, d.day, int(h_), int(m_))


def dosis_hoy(cedula=None):
    """Ronda del día: cada dosis programada con su estado (Dado / Rechazado / Pendiente / Próximo / Atrasado)."""
    meds = leer("kardex_meds")
    meds = meds[meds["Estado"] == "Activo"]
    res = leer("residentes")
    res = res[res["Estado"] != "Egresado"]
    if cedula:
        meds = meds[meds["Cedula"] == cedula]
    meds = meds[meds["Cedula"].isin(res["Cedula"])]
    nombres = res.set_index("Cedula")[["Nombre", "Habitacion"]].to_dict("index")
    ad = leer("admin_meds")
    ad = ad[ad["Fecha_Hora"].str.startswith(hoy().isoformat())]
    reg = {(r["ID_Med"], r["Hora_Programada"]): r for r in ad.to_dict("records") if r["Hora_Programada"]}
    ahora_ = ahora()
    out = []
    for m in meds.to_dict("records"):
        f_ini = parsear_fecha(m["F_Inicio"])
        if f_ini and f_ini > hoy():
            continue
        for hh in horarios_lista(m["Horarios"]):
            prog = _hora_a_dt(hh)
            r = reg.get((m["ID_Med"], hh))
            if r:
                est = "Dado" if r["Resultado"] == "Administrado" else "No dado"
            elif ahora_ > prog + timedelta(minutes=TOLERANCIA_MIN):
                est = "Atrasado"
            elif ahora_ >= prog - timedelta(minutes=60):
                est = "Ahora"
            else:
                est = "Pendiente"
            nr = nombres.get(m["Cedula"], {})
            out.append({"ID_Med": m["ID_Med"], "Cedula": m["Cedula"], "Residente": nr.get("Nombre", m["Cedula"]),
                        "Habitacion": nr.get("Habitacion", ""), "Medicamento": m["Medicamento"], "Dosis": m["Dosis"],
                        "Via": m["Via"], "Indicaciones": m["Indicaciones"], "Hora": hh, "Estado": est,
                        "Real": r["Fecha_Hora"][11:16] if r else "", "Quien": r["Autor"] if r else "",
                        "Turno": r["Turno"] if r else "", "Desvio": r["Minutos_Desvio"] if r else "",
                        "Observacion": r["Observacion"] if r else ""})
    return sorted(out, key=lambda x: (x["Hora"], x["Residente"]))


def registrar_dosis(cedula, id_med, hora_prog, resultado, obs, autor):
    """Registra la administración con la hora EXACTA del clic. Evita doble registro de la misma dosis."""
    meds = leer("kardex_meds")
    f = meds[meds["ID_Med"] == id_med]
    if f.empty:
        raise KeyError(id_med)
    med = f.iloc[0].to_dict()
    ahora_ = ahora()
    if hora_prog:
        ad = leer("admin_meds", fresco=True)
        ya = ad[(ad["ID_Med"] == id_med) & (ad["Hora_Programada"] == hora_prog) &
                (ad["Fecha_Hora"].str.startswith(hoy().isoformat()))]
        if not ya.empty:
            raise ValueError("Esa dosis ya fue registrada hoy.")
        desvio = int((ahora_ - _hora_a_dt(hora_prog)).total_seconds() // 60)
    else:
        desvio = ""
    agregar("admin_meds", {"ID": nueva_id("AD"), "ID_Med": id_med, "Cedula": cedula, "Fecha_Hora": fmt_fh(ahora_),
                           "Resultado": resultado, "Observacion": obs, "Autor": autor, "Hora_Programada": hora_prog or "",
                           "Turno": turno_de(ahora_), "Minutos_Desvio": desvio})
    if resultado == "Administrado":   # descuenta del stock de ese residente, si lo lleva
        st_ = stock_meds(cedula)
        if not st_.empty and (st_["Medicamento"].str.lower() == med["Medicamento"].strip().lower()).any():
            agregar("mov_meds", {"ID": nueva_id("MV"), "Cedula": cedula, "Medicamento": med["Medicamento"].strip(),
                                 "Tipo": "Consumo", "Cantidad": _num(med.get("Unidades_Dosis", 1), 1) or 1,
                                 "Fecha_Hora": fmt_fh(ahora_), "Autor": autor, "Nota": f"Dosis de las {hora_prog or 'PRN'}"})
    return desvio


_SIGNO = {"Ingreso": 1, "Devolución": 1, "Consumo": -1, "Salida": -1}


def stock_meds(cedula=None):
    """Existencias de medicamentos por residente y días que le alcanzan."""
    mv = leer("mov_meds")
    if cedula:
        mv = mv[mv["Cedula"] == cedula]
    if mv.empty:
        return pd.DataFrame(columns=["Cedula", "Medicamento", "Stock", "Dosis_Dia", "Dias", "Nivel"])
    mv = mv.assign(_k=mv["Medicamento"].str.strip().str.lower(),
                   _v=[_SIGNO.get(t, 1) * _num(c) if t != "Ajuste" else _num(c) for t, c in zip(mv["Tipo"], mv["Cantidad"])])
    g = mv.groupby(["Cedula", "_k"]).agg(Medicamento=("Medicamento", "last"), Stock=("_v", "sum")).reset_index()
    kar = leer("kardex_meds")
    kar = kar[kar["Estado"] == "Activo"]
    dpd = {(r["Cedula"], r["Medicamento"].strip().lower()): dosis_por_dia(r) for r in kar.to_dict("records")}
    g["Dosis_Dia"] = [dpd.get((c, k), 0) for c, k in zip(g["Cedula"], g["_k"])]
    g["Dias"] = [round(s_ / d, 1) if d else None for s_, d in zip(g["Stock"], g["Dosis_Dia"])]
    g["Nivel"] = ["crit" if s_ <= 0 or (d is not None and d <= 2) else "warn" if (d is not None and d <= 5) else "ok"
                  for s_, d in zip(g["Stock"], g["Dias"])]
    return g.drop(columns="_k")


# ──────────────────────────────────────────────────────────────
# Inventarios de Cocina y Servicios generales
# ──────────────────────────────────────────────────────────────
def stock_inventario(seccion):
    """Producto, existencias, mínimo y días estimados que alcanza, con nivel de alerta."""
    pr = leer("inv_productos")
    pr = pr[(pr["Seccion"] == seccion) & (pr["Activo"].str.upper() != "NO")]
    if pr.empty:
        return pd.DataFrame(columns=["Producto", "Unidad", "Stock", "Minimo", "Consumo_Diario", "Dias", "Nivel"])
    mv = leer("inv_mov")
    mv = mv[mv["Seccion"] == seccion]
    mv = mv.assign(_v=[(-1 if t == "Consumo" else 1) * _num(c) for t, c in zip(mv["Tipo"], mv["Cantidad"])])
    tot = mv.groupby("Producto")["_v"].sum().to_dict()
    filas = []
    for p in pr.to_dict("records"):
        stk, mini, cd = tot.get(p["Producto"], 0.0), _num(p["Minimo"]), _num(p["Consumo_Diario"])
        dias = round(stk / cd, 1) if cd else None
        crit = stk <= 0 or (mini and stk <= mini / 2)
        warn = (mini and stk <= mini) or (dias is not None and dias <= 3)
        filas.append({"Producto": p["Producto"], "Unidad": p["Unidad"], "Stock": round(stk, 2), "Minimo": mini,
                      "Consumo_Diario": cd, "Dias": dias, "Nivel": "crit" if crit else "warn" if warn else "ok"})
    return pd.DataFrame(filas)


def alertas_stock(seccion):
    d = stock_inventario(seccion)
    return d[d["Nivel"] != "ok"] if not d.empty else d


# ──────────────────────────────────────────────────────────────
# Familias: pagos del residente y alertas de vencimiento
# ──────────────────────────────────────────────────────────────
def alertas_pago(dias=5):
    """Residentes activos cuyo pago vence en <= `dias` días (o ya venció)."""
    res = leer("residentes")
    res = res[res["Estado"] != "Egresado"]
    out = []
    for r in res.to_dict("records"):
        v = parsear_fecha(r["Pagado_Hasta"])
        if v is None:
            continue
        d = (v - hoy()).days
        if d <= dias:
            out.append({**r, "Dias": d, "Vence": v.isoformat()})
    return sorted(out, key=lambda x: x["Dias"])


def registrar_pago_familia(cedula, monto, meses, metodo, autor):
    res = leer("residentes")
    f = res[res["Cedula"] == cedula]
    if f.empty:
        raise KeyError(cedula)
    ant = parsear_fecha(f.iloc[0]["Pagado_Hasta"])
    atraso = (hoy() - ant).days if ant else ""
    nueva = sumar_meses(max(ant or hoy(), hoy()), int(meses))
    agregar("pagos_familia", {"ID": nueva_id("PF"), "Cedula": cedula, "Fecha": hoy().isoformat(), "Monto": monto,
                              "Metodo": metodo, "Pagado_Hasta": nueva.isoformat(), "Dias_Atraso": atraso, "Autor": autor})
    actualizar("residentes", "Cedula", cedula, {"Pagado_Hasta": nueva.isoformat()})
    return nueva


# ──────────────────────────────────────────────────────────────
# Propietario: ranking de geriátricos cumplidos
# ──────────────────────────────────────────────────────────────
def ranking_puntualidad(minimo_pagos=2):
    """Ordena los geriátricos por cumplimiento de pagos. Paga el día de vencimiento o antes = puntual."""
    cl = leer("clientes")
    pg = leer("pagos")
    filas = []
    for c in cl.to_dict("records"):
        mios = pg[(pg["Codigo"] == c["Codigo"]) & (pg["Dias_Atraso"].str.strip() != "")]
        d = [_num(x) for x in mios["Dias_Atraso"]]
        ok, _, dias_v = estado_servicio(c)
        n = len(d)
        if n:
            a_tiempo = sum(1 for x in d if x <= 0) / n
            atraso_prom = sum(max(x, 0) for x in d) / n
            score = max(0.0, 100 * a_tiempo - min(2 * atraso_prom, 40)) + min(n, 12) * 0.5
            score = min(100.0, score)
        else:
            a_tiempo, atraso_prom, score = 0.0, 0.0, 0.0
        al_dia = ok and (dias_v is None or dias_v >= 0)
        filas.append({"Codigo": c["Codigo"], "Nombre": c["Nombre"], "Plan": c["Plan"], "Pagos": n,
                      "APuntual": round(100 * a_tiempo), "AtrasoProm": round(atraso_prom, 1),
                      "Puntaje": round(score, 1), "AlDia": al_dia,
                      "Elegible": n >= minimo_pagos and al_dia})
    filas.sort(key=lambda x: (x["Elegible"], x["Puntaje"], x["Pagos"]), reverse=True)
    pos = 0
    for f in filas:
        if f["Elegible"]:
            pos += 1
            f["Posicion"] = pos
        else:
            f["Posicion"] = None
    return filas


CATEGORIAS_CARPETA = ["Pertenencias", "Medicamentos", "Anexos", "Reportes", "Salidas", "Contratos"]


def crear_carpetas_residente(cfg, cedula, nombre):
    """Crea «cédula · nombre» con sus subcarpetas (Pertenencias, Medicamentos, Anexos…). True si quedaron listas."""
    tid = tenant_actual()
    if _libro(tid) is None:
        for c in CATEGORIAS_CARPETA:
            os.makedirs(os.path.join(DATA_DIR, re.sub(r"[^A-Za-z0-9_-]", "_", tid), "archivos",
                                     re.sub(r"[^A-Za-z0-9_-]", "_", str(cedula)), c), exist_ok=True)
        return True
    a = _auth(cfg)
    for c in CATEGORIAS_CARPETA:
        _ruta_drive(a, tid, cedula, nombre, c)
    return True
