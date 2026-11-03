# -*- coding: utf-8 -*-
"""
nucleo.py · Geriatría OS
------------------------
Capa de datos (Google Drive + Google Sheets, con respaldo local en CSV),
seguridad de contraseñas, escalas clínicas y utilidades.

No depende de Streamlit, así que se puede probar por separado.
"""
import hashlib
import hmac
import os
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


def nueva_id(prefijo):
    return f"{prefijo}-{uuid.uuid4().hex[:8].upper()}"


# ──────────────────────────────────────────────────────────────
# Esquema de la base de datos (una pestaña por tabla)
# ──────────────────────────────────────────────────────────────
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
    "usuarios": ["Usuario", "Password", "Rol", "Alias", "Reg_Profesional", "Activo"],
    "logs": ["Fecha_Hora", "Usuario", "Accion", "Detalle"],
}

NOMBRE_CARPETA = "Geriatria_OS"
NOMBRE_LIBRO = "DB_Geriatria_Master"
DATA_DIR = os.environ.get("GERIATRIA_DATA_DIR", "datos_locales")
TTL = 120  # segundos que se conserva una tabla en memoria

_DRIVE = "https://www.googleapis.com/drive/v3/files"
_E = {"tablas": {}, "hojas": {}, "enc": {}, "libro": None, "error": None,
      "carpeta_url": None, "libro_url": None, "t_intento": 0.0}
_LOCK = threading.RLock()


class ErrorNube(Exception):
    """Falla al leer o escribir en Google Sheets."""


# ──────────────────────────────────────────────────────────────
# Conexión a Google Drive / Sheets
# ──────────────────────────────────────────────────────────────
def _chk(r):
    if r.status_code >= 400:
        raise RuntimeError(f"Google Drive respondió {r.status_code}: {r.text[:400]}")
    return r


def _listar(drive, q):
    r = _chk(drive.get(_DRIVE, params={"q": q, "fields": "files(id,name,parents)",
                                       "spaces": "drive", "pageSize": 20}))
    return r.json().get("files", [])


def _asegurar_carpeta(drive):
    q = (f"name='{NOMBRE_CARPETA}' and mimeType='application/vnd.google-apps.folder' "
         "and trashed=false")
    f = _listar(drive, q)
    if f:
        return f[0]["id"]
    r = _chk(drive.post(_DRIVE, json={"name": NOMBRE_CARPETA,
                                      "mimeType": "application/vnd.google-apps.folder"}))
    return r.json()["id"]


def _asegurar_libro(drive, carpeta):
    base = f"name='{NOMBRE_LIBRO}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
    dentro = _listar(drive, base + f" and '{carpeta}' in parents")
    if dentro:
        return dentro[0]["id"]
    sueltos = _listar(drive, base)  # libro de intentos anteriores: se reutiliza y se mueve a la carpeta
    if sueltos:
        f = sueltos[0]
        try:
            _chk(drive.patch(f"{_DRIVE}/{f['id']}", params={
                "addParents": carpeta, "removeParents": ",".join(f.get("parents", [])), "fields": "id"}))
        except Exception:
            pass
        return f["id"]
    r = _chk(drive.post(_DRIVE, json={"name": NOMBRE_LIBRO, "parents": [carpeta],
                                      "mimeType": "application/vnd.google-apps.spreadsheet"}))
    return r.json()["id"]


def _asegurar_pestanas(libro):
    existentes = {w.title: w for w in libro.worksheets()}
    nombres = list(ESQUEMA)
    if not any(n in existentes for n in nombres):  # libro nuevo: la hoja inicial pasa a ser "residentes"
        libro.sheet1.update_title(nombres[0])
        existentes = {w.title: w for w in libro.worksheets()}
    enc = {}
    for nombre, cols in ESQUEMA.items():
        ws = existentes.get(nombre)
        if ws is None:
            ws = libro.add_worksheet(title=nombre, rows=500, cols=max(len(cols) + 2, 12))
        fila1 = [c.strip() for c in ws.row_values(1)]
        if not any(fila1):
            ws.append_row(list(cols), value_input_option="RAW")
            fila1 = list(cols)
        else:
            for c in cols:  # si se agregan columnas nuevas al esquema, se añaden al final
                if c not in fila1:
                    fila1.append(c)
                    ws.update_cell(1, len(fila1), c)
        enc[nombre] = fila1
        _E["hojas"][nombre] = ws
    _E["enc"] = enc


def conectar(cfg, forzar=False):
    """Conecta con Drive/Sheets. Devuelve el libro o None (el motivo queda en estado_nube())."""
    with _LOCK:
        if forzar:
            _E.update(libro=None, error=None, t_intento=0.0)
            _E["hojas"].clear()
            _E["tablas"].clear()
        if _E["libro"] is not None:
            return _E["libro"]
        if time.time() - _E["t_intento"] < 60:  # no insistir en cada recarga
            return None
        _E["t_intento"] = time.time()
        try:
            import gspread
            from google.auth.transport.requests import AuthorizedSession, Request
            from google.oauth2.credentials import Credentials

            faltan = [k for k in ("google_client_id", "google_client_secret", "google_refresh_token")
                      if not cfg.get(k)]
            if faltan:
                raise RuntimeError("Faltan estos valores en Secrets: " + ", ".join(faltan))
            creds = Credentials(token=None, refresh_token=cfg["google_refresh_token"],
                                token_uri="https://oauth2.googleapis.com/token",
                                client_id=cfg["google_client_id"],
                                client_secret=cfg["google_client_secret"])
            creds.refresh(Request())
            drive = AuthorizedSession(creds)
            carpeta = _asegurar_carpeta(drive)
            libro = gspread.authorize(creds).open_by_key(_asegurar_libro(drive, carpeta))
            _asegurar_pestanas(libro)
            _E.update(libro=libro, error=None, libro_url=libro.url,
                      carpeta_url=f"https://drive.google.com/drive/folders/{carpeta}")
            return libro
        except Exception as e:
            _E["libro"] = None
            _E["error"] = f"{type(e).__name__}: {e}"
            return None


def estado_nube():
    return {"conectado": _E["libro"] is not None, "error": _E["error"],
            "carpeta_url": _E["carpeta_url"], "libro_url": _E["libro_url"]}


# ──────────────────────────────────────────────────────────────
# Lectura / escritura de tablas
# ──────────────────────────────────────────────────────────────
def _normalizar(df, cols):
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    extras = [c for c in df.columns if c not in cols]
    return df[list(cols) + extras].fillna("").astype(str).reset_index(drop=True)


def _csv_path(nombre):
    return os.path.join(DATA_DIR, f"db_{nombre}.csv")


def _leer_csv(nombre):
    p = _csv_path(nombre)
    if os.path.exists(p):
        df = pd.read_csv(p, dtype=str, keep_default_na=False)
    else:
        df = pd.DataFrame(columns=ESQUEMA[nombre])
    return _normalizar(df, ESQUEMA[nombre])


def _guardar_csv(nombre, df):
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_csv(_csv_path(nombre), index=False)


def _hoja(nombre):
    if nombre not in _E["hojas"]:
        _E["hojas"][nombre] = _E["libro"].worksheet(nombre)
    return _E["hojas"][nombre]


def _leer_cloud(nombre):
    vals = _hoja(nombre).get_all_values()
    if vals:
        enc = [h.strip() for h in vals[0]]
        filas = [(list(f) + [""] * len(enc))[:len(enc)] for f in vals[1:] if any(str(x).strip() for x in f)]
        df = pd.DataFrame(filas, columns=enc)
    else:
        df = pd.DataFrame(columns=ESQUEMA[nombre])
    return _normalizar(df, ESQUEMA[nombre]), len(vals)


def leer(nombre, fresco=False):
    c = _E["tablas"].get(nombre)
    if c and not fresco and time.time() - c[0] < TTL:
        return c[1].copy()
    if _E["libro"] is None:
        return _leer_csv(nombre)
    try:
        df, _ = _leer_cloud(nombre)
    except Exception as e:
        _E["hojas"].pop(nombre, None)
        if c and not fresco:
            return c[1].copy()  # datos en memoria mientras Google responde
        raise ErrorNube(f"No se pudo leer '{nombre}' en Google Sheets: {e}") from e
    _E["tablas"][nombre] = (time.time(), df)
    return df.copy()


def agregar(nombre, fila):
    """Agrega UNA fila al final (no reescribe la tabla)."""
    with _LOCK:
        if _E["libro"] is None:
            df = _leer_csv(nombre)
            df = pd.concat([df, pd.DataFrame([{k: str(v) for k, v in fila.items()}])], ignore_index=True)
            _guardar_csv(nombre, _normalizar(df, ESQUEMA[nombre]))
        else:
            enc = _E["enc"].get(nombre) or ESQUEMA[nombre]
            try:
                _hoja(nombre).append_row([str(fila.get(c, "")) for c in enc], value_input_option="RAW")
            except Exception as e:
                _E["hojas"].pop(nombre, None)
                raise ErrorNube(f"No se pudo guardar en Google Sheets ('{nombre}'): {e}") from e
        _E["tablas"].pop(nombre, None)


def actualizar(nombre, col_clave, valor, cambios):
    """Modifica campos de la fila cuya col_clave == valor."""
    with _LOCK:
        n_total = 0
        if _E["libro"] is None:
            df = _leer_csv(nombre)
        else:
            try:
                df, n_total = _leer_cloud(nombre)
            except Exception as e:
                raise ErrorNube(f"No se pudo leer '{nombre}' en Google Sheets: {e}") from e
        mask = df[col_clave].astype(str) == str(valor)
        if not mask.any():
            raise KeyError(f"No existe {col_clave}={valor} en {nombre}")
        for c, v in cambios.items():
            if c not in df.columns:
                df[c] = ""
            df.loc[mask, c] = str(v)
        if _E["libro"] is None:
            _guardar_csv(nombre, df)
        else:
            enc = _E["enc"].get(nombre) or ESQUEMA[nombre]
            datos = [list(enc)] + df.reindex(columns=enc).fillna("").astype(str).values.tolist()
            while len(datos) < n_total:  # conserva el largo para no dejar filas viejas sueltas
                datos.append([""] * len(enc))
            try:
                _hoja(nombre).update(range_name="A1", values=datos)
            except Exception as e:
                _E["hojas"].pop(nombre, None)
                raise ErrorNube(f"No se pudo actualizar '{nombre}' en Google Sheets: {e}") from e
        _E["tablas"].pop(nombre, None)


def resumen_tablas():
    return {t: len(leer(t)) for t in ESQUEMA}


def log(usuario, accion, detalle=""):
    """Auditoría. Nunca debe romper la app."""
    try:
        agregar("logs", {"Fecha_Hora": fmt_fh(), "Usuario": usuario, "Accion": accion,
                         "Detalle": str(detalle)[:300]})
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────
# Usuarios y contraseñas
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
    return hmac.compare_digest(pw.encode("utf-8"), guardado.encode("utf-8"))  # clave antigua en texto plano


def asegurar_admin(cfg):
    """Si no hay usuarios, crea 'admin'."""
    if leer("usuarios").empty:
        pw = str(cfg.get("admin_password") or "admin123")
        agregar("usuarios", {"Usuario": "admin", "Password": hash_pw(pw), "Rol": "Administrador",
                             "Alias": "Administrador", "Reg_Profesional": "", "Activo": "SI"})


def admin_con_clave_default():
    df = leer("usuarios")
    f = df[df["Usuario"] == "admin"]
    return (not f.empty) and verificar_pw("admin123", f.iloc[0]["Password"])


def autenticar(usuario, password):
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
