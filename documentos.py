# -*- coding: utf-8 -*-
"""
documentos.py · Geriatría OS
----------------------------
Todo lo que produce o procesa archivos (sin depender de Streamlit, se puede probar solo):
  • procesar_imagen   → valida y reduce fotos (quita ubicación GPS/EXIF por privacidad)
  • pdf_semanal       → resumen semanal de salud para entregar a la familia o llevar al médico
  • campos_plantilla / generar_contrato → generador de contratos a partir de la plantilla .docx del geriátrico
"""
import io
import re
import zipfile
from datetime import timedelta

import pandas as pd

MAX_FOTO = 12 * 1024 * 1024       # 12 MB de entrada (el celular puede mandar fotos pesadas)
MAX_PLANTILLA = 6 * 1024 * 1024   # 6 MB

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


def fecha_larga(d):
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


# ══════════════════════════════════════════════════════════════
# FOTOS
# ══════════════════════════════════════════════════════════════
def procesar_imagen(datos, max_lado=1280, calidad=80):
    """Valida que sea una imagen real, la endereza, la reduce y la regraba como JPEG (sin EXIF/GPS)."""
    from PIL import Image, ImageOps
    if len(datos) > MAX_FOTO:
        raise ValueError("La foto pesa más de 12 MB. Tome una nueva con menos calidad.")
    try:
        Image.open(io.BytesIO(datos)).verify()
        im = Image.open(io.BytesIO(datos))
        im = ImageOps.exif_transpose(im)
    except Exception as e:
        raise ValueError("El archivo no es una imagen válida.") from e
    if im.mode not in ("RGB", "L"):
        fondo = Image.new("RGB", im.size, "white")
        fondo.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[-1])
        im = fondo
    im = im.convert("RGB")
    im.thumbnail((max_lado, max_lado))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=calidad, optimize=True)
    return out.getvalue()


# ══════════════════════════════════════════════════════════════
# CONTRATOS (.docx con marcadores (=CAMPO=))
# ══════════════════════════════════════════════════════════════
PATRON = re.compile(r"\(=\s*([A-Za-z0-9_ÁÉÍÓÚÑáéíóúñ ]+?)\s*=\)")

CAMPOS_CONTRATO = {
    "NOMBRE": "Nombre completo del residente",
    "CEDULA": "Cédula del residente",
    "FECHA_NACIMIENTO": "Fecha de nacimiento",
    "EDAD": "Edad en años",
    "SEXO": "Sexo",
    "EPS": "EPS / medicina prepagada",
    "HABITACION": "Habitación o cama",
    "DIAGNOSTICOS": "Diagnósticos principales",
    "ALERGIAS": "Alergias",
    "ACUDIENTE": "Nombre del familiar / acudiente",
    "TELEFONO_ACUDIENTE": "Teléfono del acudiente",
    "FECHA_INGRESO": "Fecha de ingreso",
    "MENSUALIDAD": "Valor de la mensualidad",
    "GERIATRICO": "Nombre del geriátrico",
    "NIT": "NIT del geriátrico",
    "FECHA_HOY": "Fecha de hoy (ej. 4 de noviembre de 2026)",
    "FECHA_HOY_CORTA": "Fecha de hoy (04/11/2026)",
}


def _normalizar_campo(c):
    return (c.strip().upper().replace(" ", "_")
            .replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U").replace("Ñ", "N"))


def validar_docx(datos):
    if len(datos) > MAX_PLANTILLA:
        raise ValueError("La plantilla pesa más de 6 MB.")
    if not zipfile.is_zipfile(io.BytesIO(datos)):
        raise ValueError("El archivo no es un Word (.docx) válido.")
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        nombres = z.namelist()
        if "word/document.xml" not in nombres:
            raise ValueError("El archivo no es un documento de Word (.docx).")
        if any(n.lower().endswith("vbaproject.bin") for n in nombres):
            raise ValueError("Por seguridad no se aceptan documentos con macros.")


def _parrafos(doc):
    """Todos los párrafos: cuerpo, tablas (anidadas), encabezados y pies de página."""
    def en_contenedor(c):
        for p in c.paragraphs:
            yield p
        for t in getattr(c, "tables", []):
            for fila in t.rows:
                for celda in fila.cells:
                    yield from en_contenedor(celda)
    yield from en_contenedor(doc)
    for sec in doc.sections:
        for parte in (sec.header, sec.footer, sec.first_page_header, sec.first_page_footer):
            if parte is not None:
                yield from en_contenedor(parte)


def campos_plantilla(datos):
    """Marcadores que la plantilla ya tiene → (reconocidos, desconocidos)."""
    from docx import Document
    validar_docx(datos)
    doc = Document(io.BytesIO(datos))
    vistos = []
    for p in _parrafos(doc):
        for m in PATRON.finditer("".join(r.text for r in p.runs)):
            c = _normalizar_campo(m.group(1))
            if c not in vistos:
                vistos.append(c)
    return [c for c in vistos if c in CAMPOS_CONTRATO], [c for c in vistos if c not in CAMPOS_CONTRATO]


def _reemplazar_en_parrafo(p, valores):
    runs = p.runs
    textos = [r.text for r in runs]
    completo = "".join(textos)
    if "(=" not in completo:
        return 0
    cambios = 0
    for m in reversed(list(PATRON.finditer(completo))):
        clave = _normalizar_campo(m.group(1))
        if clave not in valores:
            continue
        s, e = m.span()
        val = str(valores[clave])
        pos, primero = 0, True
        for i, t in enumerate(textos):
            ini, fin = pos, pos + len(t)
            pos = fin
            if not t or fin <= s or ini >= e:
                continue
            a, b = max(s, ini) - ini, min(e, fin) - ini
            textos[i] = (t[:a] + val + t[b:]) if primero else (t[:a] + t[b:])
            primero = False
        cambios += 1
        completo = "".join(textos)
    for r, t0, t1 in zip(runs, [r.text for r in runs], textos):
        if t0 != t1:               # solo se tocan los trozos que cambian: firmas e imágenes quedan intactas
            r.text = t1
    return cambios


def generar_contrato(plantilla, valores):
    """Rellena la plantilla conservando formato, tablas, logos e imágenes de firma. Devuelve (docx_bytes, campos_sin_dato)."""
    from docx import Document
    validar_docx(plantilla)
    doc = Document(io.BytesIO(plantilla))
    v = {_normalizar_campo(k): ("" if x is None else x) for k, x in valores.items()}
    for p in _parrafos(doc):
        _reemplazar_en_parrafo(p, v)
    restantes = []
    for p in _parrafos(doc):
        for m in PATRON.finditer("".join(r.text for r in p.runs)):
            c = _normalizar_campo(m.group(1))
            if c not in restantes:
                restantes.append(c)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue(), restantes


def plantilla_ejemplo(nombre_geriatrico="NOMBRE DEL GERIÁTRICO"):
    """.docx de ejemplo con los marcadores, para que el geriátrico lo adapte a su propio contrato."""
    from docx import Document
    d = Document()
    d.add_heading("CONTRATO DE PRESTACIÓN DE SERVICIOS DE CUIDADO GERONTOLÓGICO", 1)
    d.add_paragraph("Fecha: (=FECHA_HOY=)")
    d.add_paragraph("Entre (=GERIATRICO=), NIT (=NIT=), y el señor(a) (=ACUDIENTE=), teléfono (=TELEFONO_ACUDIENTE=), "
                    "en calidad de acudiente de (=NOMBRE=), identificado(a) con cédula (=CEDULA=), "
                    "nacido(a) el (=FECHA_NACIMIENTO=) (=EDAD=) años, afiliado(a) a (=EPS=), se acuerda:")
    d.add_paragraph("PRIMERA. Ingreso: (=FECHA_INGRESO=) · Habitación: (=HABITACION=).")
    d.add_paragraph("SEGUNDA. Diagnósticos: (=DIAGNOSTICOS=). Alergias: (=ALERGIAS=).")
    d.add_paragraph("TERCERA. Mensualidad: (=MENSUALIDAD=), pagadera dentro de los primeros días de cada mes.")
    d.add_paragraph("\n\n______________________________          ______________________________")
    d.add_paragraph("(=GERIATRICO=)                                          (=ACUDIENTE=)")
    out = io.BytesIO()
    d.save(out)
    return out.getvalue()


# ══════════════════════════════════════════════════════════════
# PDF SEMANAL PARA LA FAMILIA / EL MÉDICO
# ══════════════════════════════════════════════════════════════
def _t(x):
    """Texto seguro para la fuente base del PDF (sin emojis)."""
    x = str(x).replace("🔴", "[ALERTA]").replace("🟡", "[Atención]").replace("→", "->")
    return re.sub(r"[^\x00-\xff]", "", x).strip()


def _num(x):
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return None


def _resumen_vitales(v):
    filas = []
    for col, nombre, unidad in [("TA_Sis", "Presión sistólica", "mmHg"), ("TA_Dia", "Presión diastólica", "mmHg"),
                                ("FC", "Frecuencia cardíaca", "lpm"), ("FR", "Frecuencia respiratoria", "rpm"),
                                ("Temp", "Temperatura", "°C"), ("SatO2", "Saturación de oxígeno", "%"),
                                ("Glucemia", "Glucemia", "mg/dL"), ("Peso", "Peso", "kg")]:
        n = [x for x in (_num(a) for a in v[col]) if x]
        if n:
            filas.append([nombre, f"{min(n):g}", f"{sum(n) / len(n):.1f}", f"{max(n):g}", unidad])
    return filas


def adherencia(kardex, admin, desde, hasta):
    """Por cada medicamento activo: dosis programadas vs administradas en el periodo."""
    from nucleo import horarios_lista, parsear_fecha
    filas = []
    for m in kardex.to_dict("records"):
        f_ini = parsear_fecha(m["F_Inicio"]) or desde
        susp = parsear_fecha(m["F_Suspension"])
        d0, d1 = max(desde, f_ini), min(hasta, susp) if susp else hasta
        if d1 < d0:
            continue
        dias = (d1 - d0).days + 1
        por_dia = len(horarios_lista(m["Horarios"]))
        a = admin[admin["ID_Med"] == m["ID_Med"]]
        dadas = int((a["Resultado"] == "Administrado").sum())
        rech = int((a["Resultado"] != "Administrado").sum())
        prog = dias * por_dia
        filas.append([m["Medicamento"], f"{m['Dosis']} · {m['Via']}", m["Horarios"] or m["Frecuencia"],
                      str(prog) if por_dia else "según necesidad", str(dadas), str(rech)])
    return filas


def pdf_semanal(geriatrico, res, vitales, kardex, admin, escalas, salidas, notas, desde, hasta, quien, edad=None):
    """Genera el PDF (bytes). `vitales`, `admin`, `escalas`, `salidas` y `notas` ya vienen filtrados al residente y periodo."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

    verde, azul, gris = colors.HexColor("#0F9D7A"), colors.HexColor("#0B1F3A"), colors.HexColor("#5F6F85")
    ss = getSampleStyleSheet()
    est = {"t": ParagraphStyle("t", parent=ss["Title"], fontSize=19, textColor=azul, spaceAfter=2, alignment=0),
           "s": ParagraphStyle("s", parent=ss["Normal"], fontSize=9.5, textColor=gris, spaceAfter=8),
           "h": ParagraphStyle("h", parent=ss["Heading2"], fontSize=12.5, textColor=verde, spaceBefore=10, spaceAfter=4),
           "n": ParagraphStyle("n", parent=ss["Normal"], fontSize=9.5, leading=12.5),
           "c": ParagraphStyle("c", parent=ss["Normal"], fontSize=8, leading=10),
           "p": ParagraphStyle("p", parent=ss["Normal"], fontSize=7.5, textColor=gris, leading=9.5)}

    def tabla(datos, anchos, enc=True, alertas_col=None):
        filas = [[Paragraph(_t(c), est["c"]) for c in f] for f in datos]
        t = Table(filas, colWidths=anchos, repeatRows=1 if enc else 0)
        sty = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8D2E0")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        if enc:
            sty += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E3F6EF")), ("TEXTCOLOR", (0, 0), (-1, 0), azul)]
        if alertas_col is not None:
            for i, f in enumerate(datos[1:], start=1):
                if "ALERTA" in f[alertas_col]:
                    sty.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FDECEC")))
                elif "Atención" in f[alertas_col]:
                    sty.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FFF3D6")))
        t.setStyle(TableStyle(sty))
        return t

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.4 * cm,
                            bottomMargin=1.5 * cm, title=f"Resumen semanal - {_t(res['Nombre'])}",
                            author=_t(geriatrico))
    W = A4[0] - 3.2 * cm
    el = [Paragraph("Resumen semanal de salud", est["t"]),
          Paragraph(f"{_t(geriatrico)} · Periodo: {desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}", est["s"])]

    alerg = _t(res["Alergias"]) or "No reportadas"
    datos_res = [["Residente", _t(res["Nombre"]), "Cédula", _t(res["Cedula"])],
                 ["Edad", f"{edad} años" if edad is not None else "—", "EPS", _t(res["EPS"]) or "—"],
                 ["Diagnósticos", _t(res["Diagnosticos"]) or "—", "Alergias", alerg]]
    t = Table([[Paragraph(f"<b>{a}</b>", est["c"]), Paragraph(b, est["c"]), Paragraph(f"<b>{c}</b>", est["c"]),
                Paragraph(d, est["c"])] for a, b, c, d in datos_res], colWidths=[2.4 * cm, W / 2 - 2.4 * cm, 2.2 * cm, W / 2 - 2.2 * cm])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, verde), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F6FA")),
                           ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F3F6FA")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    el += [t]

    # ── Signos vitales
    el.append(Paragraph("Signos vitales de la semana", est["h"]))
    if vitales.empty:
        el.append(Paragraph("No se registraron signos vitales en este periodo.", est["n"]))
    else:
        v = vitales.sort_values("Fecha_Hora")
        n_crit = int(v["Alertas"].str.contains("🔴", regex=False).sum())
        n_warn = int(v["Alertas"].str.contains("🟡", regex=False).sum()) - n_crit
        el.append(Paragraph(f"{len(v)} registros · <b>{n_crit}</b> con alerta crítica · <b>{max(n_warn, 0)}</b> con alerta leve.", est["n"]))
        el.append(Spacer(1, 4))
        el.append(tabla([["Medida", "Mínimo", "Promedio", "Máximo", "Unidad"]] + _resumen_vitales(v),
                        [5.2 * cm, 2.4 * cm, 2.4 * cm, 2.4 * cm, W - 12.4 * cm]))
        el.append(Spacer(1, 6))
        filas = [["Fecha y hora", "TA", "FC", "FR", "T °C", "SatO₂", "Gluc.", "Dolor", "Alertas"]]
        for r in v.to_dict("records"):
            filas.append([r["Fecha_Hora"][:16], f"{r['TA_Sis']}/{r['TA_Dia']}", r["FC"], r["FR"], r["Temp"], r["SatO2"],
                          r["Glucemia"] or "—", r["Dolor"], _t(r["Alertas"]) or "—"])
        el.append(tabla(filas, [3.0 * cm, 1.8 * cm, 1.1 * cm, 1.1 * cm, 1.3 * cm, 1.4 * cm, 1.3 * cm, 1.2 * cm, W - 12.2 * cm], alertas_col=8))
        try:  # tendencia
            from reportlab.graphics.charts.lineplots import LinePlot
            from reportlab.graphics.shapes import Drawing
            d = Drawing(W, 140)
            lp = LinePlot()
            lp.x, lp.y, lp.width, lp.height = 30, 20, W - 50, 105
            sis = [(i, _num(x)) for i, x in enumerate(v["TA_Sis"]) if _num(x)]
            fc = [(i, _num(x)) for i, x in enumerate(v["FC"]) if _num(x)]
            lp.data = [sis or [(0, 0)], fc or [(0, 0)]]
            lp.lines[0].strokeColor, lp.lines[1].strokeColor = colors.HexColor("#D64545"), verde
            lp.lines[0].strokeWidth = lp.lines[1].strokeWidth = 1.6
            lp.xValueAxis.visible = False
            lp.yValueAxis.labels.fontSize = 7
            d.add(lp)
            el += [Spacer(1, 6), Paragraph("Tendencia: <font color='#D64545'>presión sistólica</font> y "
                                           "<font color='#0F9D7A'>frecuencia cardíaca</font> (en orden de registro)", est["c"]), d]
        except Exception:
            pass

    # ── Medicamentos
    el.append(Paragraph("Medicamentos y cumplimiento", est["h"]))
    ad = adherencia(kardex, admin, desde, hasta)
    if ad:
        el.append(tabla([["Medicamento", "Dosis y vía", "Horario", "Programadas", "Dadas", "No dadas"]] + ad,
                        [4.3 * cm, 3.7 * cm, 3.4 * cm, 2.4 * cm, 1.6 * cm, W - 15.4 * cm]))
        no_dadas = admin[admin["Resultado"] != "Administrado"]
        if not no_dadas.empty:
            el.append(Spacer(1, 4))
            el.append(Paragraph("<b>Dosis no administradas y motivo:</b>", est["n"]))
            for r in no_dadas.to_dict("records"):
                el.append(Paragraph(f"• {r['Fecha_Hora'][:16]} — {_t(r['Resultado'])}: {_t(r['Observacion'])}", est["n"]))
    else:
        el.append(Paragraph("Sin medicamentos activos registrados.", est["n"]))

    # ── Escalas
    if not escalas.empty:
        el.append(Paragraph("Valoraciones geriátricas recientes", est["h"]))
        ult = escalas.sort_values("Fecha_Hora").groupby("Escala").tail(1)
        el.append(tabla([["Escala", "Fecha", "Puntaje", "Resultado"]] +
                        [[r["Escala"], r["Fecha_Hora"][:10], r["Puntaje"], _t(r["Interpretacion"])] for r in ult.to_dict("records")],
                        [3.2 * cm, 2.6 * cm, 2.0 * cm, W - 7.8 * cm]))

    # ── Salidas
    if not salidas.empty:
        el.append(Paragraph("Salidas de la semana", est["h"]))
        el.append(tabla([["Salida", "Destino / motivo", "Regreso", "Novedad"]] +
                        [[r["F_Salida"][:16], f"{_t(r['Destino'])} · {_t(r['Motivo'])}", r["F_Retorno"][:16] or "Aún fuera",
                          _t(r["Faltantes"]) or _t(r["Observacion_Retorno"]) or "Sin novedad"] for r in salidas.to_dict("records")],
                        [3.0 * cm, 6.0 * cm, 3.0 * cm, W - 12.0 * cm]))

    # ── Notas de enfermería (opcional)
    if notas is not None and not notas.empty:
        el.append(Paragraph("Observaciones de enfermería", est["h"]))
        for r in notas.sort_values("Fecha_Hora").to_dict("records"):
            txt = _t(r["Evaluacion"]) or _t(r["Objetivo"])
            el.append(KeepTogether([Paragraph(f"<b>{r['Fecha_Hora'][:16]}</b> · {_t(r['Turno']).split(' (')[0]}: {txt[:380]}", est["n"]),
                                    Spacer(1, 3)]))

    el += [Spacer(1, 14),
           Paragraph(f"Documento informativo generado el {hasta.strftime('%d/%m/%Y')} por {_t(quien)}. "
                     "No reemplaza la historia clínica ni la valoración de un profesional de la salud. "
                     "Si observa algún cambio en el estado del residente, consulte a su médico.", est["p"])]
    doc.build(el)
    return out.getvalue()


# ══════════════════════════════════════════════════════════════
# ACTA DE SALIDA / REGRESO (evita reclamos: queda escrito con qué salió y con qué regresó)
# ══════════════════════════════════════════════════════════════
def pdf_acta_salida(geriatrico, res, salida, items_salida, items_regreso, quien):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    ss = getSampleStyleSheet()
    n = ParagraphStyle("n", parent=ss["Normal"], fontSize=10, leading=14)
    h = ParagraphStyle("h", parent=ss["Heading2"], fontSize=13, textColor=colors.HexColor("#0B1F3A"))
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    el = [Paragraph("Acta de salida y regreso del residente", ss["Title"]), Paragraph(_t(geriatrico), n), Spacer(1, 10),
          Paragraph(f"<b>Residente:</b> {_t(res['Nombre'])} · CC {_t(res['Cedula'])}", n),
          Paragraph(f"<b>Salida:</b> {_t(salida['F_Salida'])} · <b>Motivo:</b> {_t(salida['Motivo'])} · <b>Destino:</b> {_t(salida['Destino'])}", n),
          Paragraph(f"<b>Acompañante / responsable:</b> {_t(salida['Acompanante']) or '—'}", n),
          Paragraph(f"<b>Registró la salida:</b> {_t(salida['Autor_Salida'])}", n), Paragraph("Con qué salió", h)]
    el += [Paragraph(f"• {_t(i)}", n) for i in items_salida] or [Paragraph("Sin objetos registrados.", n)]
    el.append(Paragraph("Con qué regresó", h))
    if salida["Estado"] == "Regresó":
        el.append(Paragraph(f"<b>Regreso:</b> {_t(salida['F_Retorno'])} · <b>Recibió:</b> {_t(salida['Autor_Retorno'])}", n))
        el += [Paragraph(f"• {_t(i)}", n) for i in items_regreso] or [Paragraph("Sin objetos registrados.", n)]
        fal = _t(salida["Faltantes"])
        el.append(Paragraph(f"<b>Objetos que no regresaron:</b> {fal or 'Ninguno'}", n))
        if _t(salida["Observacion_Retorno"]):
            el.append(Paragraph(f"<b>Observaciones:</b> {_t(salida['Observacion_Retorno'])}", n))
    else:
        el.append(Paragraph("El residente aún no ha regresado.", n))
    firmas = Table([["\n\n______________________", "\n\n______________________"], ["Quien entrega / recibe (familia)", f"Funcionario(a): {_t(quien)}"]],
                   colWidths=[8.5 * cm, 8.5 * cm])
    firmas.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9)]))
    el += [Spacer(1, 30), firmas]
    doc.build(el)
    return out.getvalue()
