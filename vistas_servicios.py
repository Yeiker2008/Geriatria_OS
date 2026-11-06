# -*- coding: utf-8 -*-
"""vistas_servicios.py · COCINA, SERVICIOS GENERALES, FAMILIAS, CONTRATOS, ARCHIVOS, MONITOR y ADMINISTRACIÓN."""
import html
from datetime import timedelta

import pandas as pd
import streamlit as st

import documentos as D
import nucleo as N
import ui as U
from ui import KW, chip, h

NIVEL_ICONO = {"ok": "🟢", "warn": "🟡", "crit": "🔴"}
UNIDADES = ["kg", "libras", "gramos", "litros", "unidades", "paquetes", "bolsas", "cajas", "frascos"]


# ══════════════════════════════════════════════════════════════
# PIEZAS COMUNES DE COCINA Y SERVICIOS GENERALES
# ══════════════════════════════════════════════════════════════
def _alertas_stock(seccion, etiqueta):
    for x in N.alertas_stock(seccion).to_dict("records"):
        dias = f" · alcanza ~{x['Dias']:g} días" if x["Dias"] is not None else ""
        U.aviso(f"{'🔴 SE ACABÓ' if x['Nivel'] == 'crit' else '🟡 POCO'} {etiqueta}: {x['Producto']} — quedan {x['Stock']:g} {x['Unidad']}{dias}",
                x["Nivel"])


def _inventario(seccion, sec_color, puede_crear):
    stk = N.stock_inventario(seccion)
    if stk.empty:
        st.info("Todavía no hay productos. Cree el primero en la pestaña **➕ Producto nuevo**.")
    else:
        _alertas_stock(seccion, "—")
        U.tabla(pd.DataFrame({"": [NIVEL_ICONO[n] for n in stk["Nivel"]], "Producto": stk["Producto"], "Unidad": stk["Unidad"],
                              "Quedan": stk["Stock"], "Mínimo": stk["Minimo"], "Se gasta por día": stk["Consumo_Diario"],
                              "Alcanza (días)": stk["Dias"].fillna("—")}))
    t1, t2, t3 = st.tabs(["📥 Llegó producto", "📤 Se gastó", "➕ Producto nuevo"])
    prods = stk["Producto"].tolist() if not stk.empty else []
    with t1:
        U.ayuda(["Elija el producto que llegó.", "Escriba cuántas unidades llegaron.", "Si sabe, diga para cuántos días debe alcanzar.", "Toque **Guardar**."])
        v = U.ver(f"{seccion}_in")
        with st.form(f"form_in_{seccion}_{v}"):
            prod = st.selectbox("Producto", prods or ["—"], key=f"in_p_{seccion}_{v}")
            a, b = st.columns(2)
            cant = a.number_input("¿Cuánto llegó?", min_value=0.0, step=1.0, key=f"in_c_{seccion}_{v}")
            dias = b.number_input("¿Para cuántos días debe alcanzar? (0 = no sé)", min_value=0, step=1, key=f"in_d_{seccion}_{v}")
            nota = st.text_input("Nota (proveedor, factura…)", key=f"in_n_{seccion}_{v}")
            if st.form_submit_button("📥 GUARDAR LLEGADA", type="primary", **KW):
                if not prods or cant <= 0:
                    st.error("Elija el producto y escriba una cantidad mayor que cero.")
                else:
                    N.agregar("inv_mov", {"ID": N.nueva_id("IV"), "Seccion": seccion, "Producto": prod, "Tipo": "Ingreso", "Cantidad": cant,
                                          "Fecha_Hora": N.fmt_fh(), "Uso": nota.strip(), "Dias_Estimados": dias or "", "Autor": U.firma()})
                    N.log(st.session_state.usuario, f"LLEGADA_{seccion.upper()}", f"{prod} +{cant:g}")
                    U.flash("ok", f"✅ Llegaron {cant:g} de {prod}.")
                    U.nueva_version(f"{seccion}_in")
                    st.rerun()
    with t2:
        v = U.ver(f"{seccion}_out")
        with st.form(f"form_out_{seccion}_{v}"):
            prod = st.selectbox("Producto", prods or ["—"], key=f"out_p_{seccion}_{v}")
            cant = st.number_input("¿Cuánto se gastó?", min_value=0.0, step=1.0, key=f"out_c_{seccion}_{v}")
            uso = st.text_input("¿En qué se usó?", key=f"out_u_{seccion}_{v}",
                                placeholder="Ej: almuerzo de hoy" if seccion == "Cocina" else "Ej: aseo de habitaciones del piso 2")
            if st.form_submit_button("📤 GUARDAR GASTO", type="primary", **KW):
                if not prods or cant <= 0 or not uso.strip():
                    st.error("Elija el producto, la cantidad y diga en qué se usó.")
                else:
                    N.agregar("inv_mov", {"ID": N.nueva_id("IV"), "Seccion": seccion, "Producto": prod, "Tipo": "Consumo", "Cantidad": cant,
                                          "Fecha_Hora": N.fmt_fh(), "Uso": uso.strip(), "Dias_Estimados": "", "Autor": U.firma()})
                    N.log(st.session_state.usuario, f"GASTO_{seccion.upper()}", f"{prod} -{cant:g} · {uso.strip()}")
                    U.flash("ok", f"✅ Gasto guardado: {cant:g} de {prod}.")
                    U.nueva_version(f"{seccion}_out")
                    st.rerun()
    with t3:
        if not puede_crear:
            U.aviso("Solo el cocinero/a o el administrador pueden crear productos nuevos." if seccion == "Cocina" else "Solo administración puede crear productos nuevos.", "info")
        else:
            v = U.ver(f"{seccion}_new")
            with st.form(f"form_new_{seccion}_{v}"):
                a, b = st.columns(2)
                nom = a.text_input("Nombre del producto", key=f"pn_n_{seccion}_{v}", placeholder="Ej: Arroz" if seccion == "Cocina" else "Ej: Cloro")
                uni = b.selectbox("Unidad", UNIDADES, key=f"pn_u_{seccion}_{v}")
                a, b = st.columns(2)
                mini = a.number_input("Avisar cuando queden menos de…", min_value=0.0, step=1.0, key=f"pn_m_{seccion}_{v}")
                cd = b.number_input("Se gasta más o menos por día", min_value=0.0, step=0.5, key=f"pn_c_{seccion}_{v}")
                if st.form_submit_button("➕ CREAR PRODUCTO", type="primary", **KW):
                    ya = N.leer("inv_productos")
                    if not nom.strip():
                        st.error("Escriba el nombre.")
                    elif ((ya["Seccion"] == seccion) & (ya["Producto"].str.lower() == nom.strip().lower())).any():
                        st.error("Ese producto ya existe.")
                    else:
                        N.agregar("inv_productos", {"Seccion": seccion, "Producto": nom.strip(), "Unidad": uni, "Minimo": mini, "Consumo_Diario": cd, "Activo": "SI"})
                        N.log(st.session_state.usuario, f"CREA_PRODUCTO_{seccion.upper()}", nom.strip())
                        U.flash("ok", f"✅ Producto «{nom.strip()}» creado.")
                        U.nueva_version(f"{seccion}_new")
                        st.rerun()


def _tareas(seccion, areas, tipos, ejemplo):
    stk = N.stock_inventario(seccion)
    prods = stk["Producto"].tolist() if not stk.empty else []
    v = U.ver(f"{seccion}_tar")
    U.ayuda(["Elija **dónde** se hizo el trabajo.", "Elija **qué** se hizo.", "Cuente en pocas palabras **cómo** lo hizo.",
             "Si usó productos, anótelos en la tabla. Toque **Guardar**."])
    with st.form(f"form_tar_{seccion}_{v}"):
        a, b = st.columns(2)
        area = a.selectbox("📍 ¿Dónde?", areas, key=f"ta_a_{seccion}_{v}")
        tipo = b.selectbox("🧽 ¿Qué se hizo?", tipos, key=f"ta_t_{seccion}_{v}")
        desc = st.text_area("📝 ¿Cómo se hizo? (pasos, detalles)", key=f"ta_d_{seccion}_{v}", height=90, placeholder=ejemplo)
        usados = None
        if prods:
            st.markdown("**🧴 Productos que usó** (opcional)")
            usados = st.data_editor(pd.DataFrame({"Producto": [prods[0]], "Cantidad": [0.0]}), num_rows="dynamic", key=f"ta_u_{seccion}_{v}",
                                    column_config={"Producto": st.column_config.SelectboxColumn(options=prods, required=True),
                                                   "Cantidad": st.column_config.NumberColumn(min_value=0.0, step=0.5)}, **KW)
        if st.form_submit_button("✅ GUARDAR LO QUE HICE", type="primary", **KW):
            if len(desc.strip()) < 8:
                st.error("Cuente brevemente cómo lo hizo (mínimo una frase).")
            else:
                lista = [x for x in (usados.to_dict("records") if usados is not None else []) if x.get("Producto") and N._num(x.get("Cantidad")) > 0]
                txt = "; ".join(f"{x['Producto']} x{N._num(x['Cantidad']):g}" for x in lista)
                N.agregar("tareas_aseo", {"ID": N.nueva_id("TA"), "Fecha_Hora": N.fmt_fh(), "Seccion": seccion, "Area": area, "Tipo": tipo,
                                          "Descripcion": desc.strip(), "Productos": txt, "Autor": U.quien(), "Rol": U.rol()})
                for x in lista:
                    N.agregar("inv_mov", {"ID": N.nueva_id("IV"), "Seccion": seccion, "Producto": x["Producto"], "Tipo": "Consumo", "Cantidad": N._num(x["Cantidad"]),
                                          "Fecha_Hora": N.fmt_fh(), "Uso": f"{tipo} · {area}", "Dias_Estimados": "", "Autor": U.firma()})
                N.log(st.session_state.usuario, f"TAREA_{seccion.upper()}", f"{tipo} · {area}")
                U.flash("ok", f"✅ Guardado: {tipo} en {area}.")
                U.nueva_version(f"{seccion}_tar")
                st.rerun()
    tr = N.leer("tareas_aseo")
    tr = tr[tr["Seccion"] == seccion].sort_values("Fecha_Hora", ascending=False)
    st.markdown("##### 📋 Lo que se ha hecho")
    hoy = tr[tr["Fecha_Hora"].str.startswith(N.hoy().isoformat())]
    st.caption(f"Hoy se han registrado {len(hoy)} trabajos.")
    if tr.empty:
        st.caption("Aún no hay registros.")
    else:
        U.tabla(tr[["Fecha_Hora", "Area", "Tipo", "Descripcion", "Productos", "Autor"]].head(60))


def _indicaciones(seccion, ayudas):
    ind = N.leer("indicaciones")
    ind = ind[(ind["Seccion"] == seccion) & (ind["Activa"].str.upper() != "NO")].sort_values("Fecha_Hora", ascending=False)
    st.markdown("##### 📢 Indicaciones de la administración")
    if ind.empty:
        st.caption("No hay indicaciones nuevas.")
    for x in ind.to_dict("records"):
        U.aviso(f"{x['Titulo']}: {x['Texto']}  ({x['Fecha_Hora'][:10]} · {x['Autor']})", "info")
    st.markdown("##### 💡 Ayudas rápidas")
    for a in ayudas:
        st.markdown(f"- {a}")


# ══════════════════════════════════════════════════════════════
# COCINA
# ══════════════════════════════════════════════════════════════
def pagina_cocina():
    U.banner("Cocina", "Cocina", "Mercado que llega, lo que se gasta y la limpieza de la cocina.")
    t1, t2, t3 = st.tabs(["📦 Mercado e inventario", "🧽 Aseo y trabajo en la cocina", "📢 Indicaciones y ayudas"])
    with t1:
        _inventario("Cocina", "Cocina", puede_crear=U.rol() in (N.R_ADMIN, N.R_COC))
    with t2:
        _tareas("Cocina", ["Estufa y mesones", "Nevera / congelador", "Despensa", "Piso de la cocina", "Utensilios y ollas", "Comedor", "Canecas y basuras", "Toda la cocina"],
                ["Aseo formal (diario)", "Aseo general (profundo)", "Desinfección de superficies", "Lavado de utensilios", "Limpieza de nevera", "Preparación de alimentos", "Otro"],
                "Ej: Se lavó el mesón con jabón y se desinfectó con cloro diluido; se trapeó el piso.")
    with t3:
        _indicaciones("Cocina", ["Anote **todo** lo que llega del mercado el mismo día.", "Si un producto está en 🟡 o 🔴, avise a administración.",
                                 "Revise fechas de vencimiento al recibir el mercado.", "Lávese las manos antes de preparar alimentos."])


# ══════════════════════════════════════════════════════════════
# SERVICIOS GENERALES (ASEO)
# ══════════════════════════════════════════════════════════════
def pagina_aseo():
    U.banner("Aseo", "Servicios generales", "Registre el aseo que se hizo, dónde, cómo y con qué productos.")
    t1, t2, t3 = st.tabs(["🧹 Lo que hice hoy", "🧴 Productos de aseo", "📢 Indicaciones y ayudas"])
    with t1:
        res = N.leer("residentes")
        habs = sorted({f"Habitación {x}" for x in res[res["Estado"] != "Egresado"]["Habitacion"] if x.strip()})
        _tareas("Aseo", habs + ["Pasillos", "Baños comunes", "Comedor", "Sala", "Lavandería", "Patio / jardín", "Entrada", "Todo el piso"],
                ["Aseo formal (diario)", "Aseo general (profundo)", "Desinfección", "Cambio de ropa de cama", "Lavado de ropa", "Recolección de basuras", "Otro"],
                "Ej: Se barrió, se trapeó con desinfectante y se cambió la ropa de cama.")
    with t2:
        _inventario("Aseo", "Aseo", puede_crear=U.rol() in (N.R_ADMIN, N.R_ASEO))
    with t3:
        _indicaciones("Aseo", ["Use guantes con el cloro y nunca lo mezcle con otros productos.", "Pise con cuidado: ponga el aviso de «piso mojado».",
                               "Anote cada habitación que limpie.", "Si un producto se está acabando, avise a administración."])


# ══════════════════════════════════════════════════════════════
# FAMILIAS
# ══════════════════════════════════════════════════════════════
PLANTILLAS = {
    "💰 Recordatorio de pago": "Hola {familiar} 👋, le saludamos de {geriatrico}. Le recordamos que el pago de la mensualidad de {residente} "
                              "vence el {fecha} ({dias}). Valor: {monto}. ¡Gracias por su puntualidad! 🙏",
    "✅ Pago recibido": "Hola {familiar}, confirmamos que recibimos el pago de la mensualidad de {residente}. Quedó pagado hasta el {fecha}. ¡Muchas gracias! 🙏 — {geriatrico}",
    "💊 Medicinas por agotarse": "Hola {familiar}, le escribimos de {geriatrico}. Las siguientes medicinas de {residente} se están acabando: {medicinas}. "
                                "Por favor tráigalas lo antes posible para no interrumpir su tratamiento. 🙏",
    "🧴 Faltan artículos de aseo": "Hola {familiar}, de {geriatrico}: a {residente} se le están acabando artículos de aseo personal ({aseo}). "
                                  "Por favor envíelos o avísenos para comprarlos. Gracias 🙏",
    "📄 Reporte semanal de salud": "Hola {familiar} 👋, le compartimos el resumen de salud de {residente} (del {desde} al {hasta}), con signos vitales y medicinas. "
                                  "Le adjunto el PDF. Si lo lleva al médico, le servirá para saber cómo ha estado. — {geriatrico}",
    "📢 Mensaje libre": "Hola {familiar}, le escribimos de {geriatrico} sobre {residente}: ",
}


def _vars(r, **extra):
    cli = U.cli()
    base = {"familiar": r["Acudiente_Nombre"] or "familiar", "residente": r["Nombre"], "geriatrico": cli["Nombre"],
            "fecha": r["Pagado_Hasta"] or "—", "dias": "", "monto": N.cop(r["Mensualidad"]) if r["Mensualidad"] else "—",
            "medicinas": "—", "aseo": "—", "desde": "", "hasta": ""}
    base.update(extra)
    return base


def _texto(plantilla, r, **extra):
    try:
        return PLANTILLAS[plantilla].format(**_vars(r, **extra))
    except Exception:
        return PLANTILLAS[plantilla]


def _meds_bajos(ced):
    s = N.stock_meds(ced)
    return "; ".join(f"{x['Medicamento']} (quedan {x['Stock']:g})" for x in s[s["Nivel"] != "ok"].to_dict("records")) if not s.empty else ""


def _aseo_bajo(ced):
    ma = N.leer("aseo_personal")
    ma = ma[ma["Cedula"] == ced]
    if ma.empty:
        return ""
    ma = ma.assign(_v=[(-1 if t == "Consumo" else 1) * N._num(c) for t, c in zip(ma["Tipo"], ma["Cantidad"])])
    g = ma.groupby("Articulo")["_v"].sum()
    return ", ".join(g[g <= 1].index)


def _enviar_wa(r, texto, tipo, clave):
    link = U.wa_link(r["Acudiente_Tel"], texto)
    if not link:
        st.warning("Este residente no tiene teléfono del acudiente. Agréguelo en **Residentes**.")
        return
    c1, c2 = st.columns(2)
    with c1:
        U.enlace("📲 ABRIR WHATSAPP CON EL MENSAJE", link)
    with c2:
        if st.button("✅ Ya lo envié (guardar en historial)", key=f"env_{clave}", **KW):
            N.agregar("comunicaciones", {"ID": N.nueva_id("CM"), "Cedula": r["Cedula"], "Fecha_Hora": N.fmt_fh(), "Tipo": tipo, "Canal": "WhatsApp",
                                         "Mensaje": texto[:500], "Autor": U.firma()})
            N.log(st.session_state.usuario, "ENVIA_WHATSAPP", f"{r['Cedula']} · {tipo}")
            U.flash("ok", "✅ Quedó registrado en el historial de comunicaciones.")
            st.rerun()


def pagina_familias():
    U.banner("Familias", "Familias", "Cobros, mensajes por WhatsApp y reportes de salud para la familia.")
    t1, t2, t3, t4 = st.tabs(["💰 Pagos", "📨 Mensajes", "📄 Reporte semanal (PDF)", "🧾 Historial"])
    res = N.leer("residentes")
    act = res[res["Estado"] != "Egresado"]

    with t1:
        al = N.alertas_pago(5)
        if not al:
            U.aviso("🎉 Ningún pago vence en los próximos 5 días.", "ok")
        for x in al:
            d = x["Dias"]
            nivel = "crit" if d < 0 else "warn"
            txt = f"VENCIDO hace {-d} días" if d < 0 else "vence HOY" if d == 0 else f"vence en {d} días"
            U.aviso(f"{'🔴' if d < 0 else '🟡'} {x['Nombre']}: {txt} ({x['Vence']}) · {N.cop(x['Mensualidad']) if x['Mensualidad'] else 'sin valor'}", nivel)
            plantilla = "💰 Recordatorio de pago"
            _enviar_wa(x, _texto(plantilla, x, dias=txt, fecha=x["Vence"]), "Alerta de pago", f"pago_{x['Cedula']}")
            st.divider()
        st.markdown("##### ✅ Registrar un pago de la familia")
        ced = U.selector_residente("pagf")
        if ced:
            r = act[act["Cedula"] == ced].iloc[0]
            v = U.ver("pagf")
            with st.form(f"form_pagf_{v}"):
                a, b, c = st.columns(3)
                monto = a.number_input("Monto (COP)", min_value=0.0, value=float(N._num(r["Mensualidad"])), step=10000.0, key=f"pf_m_{ced}_{v}")
                meses = b.number_input("Meses que cubre", min_value=1, max_value=12, value=1, key=f"pf_n_{ced}_{v}")
                met = c.selectbox("Método", ["Transferencia", "Nequi", "Daviplata", "Efectivo", "Otro"], key=f"pf_t_{ced}_{v}")
                if st.form_submit_button("💾 REGISTRAR PAGO", type="primary", **KW):
                    nueva = N.registrar_pago_familia(ced, monto, meses, met, U.firma())
                    N.log(st.session_state.usuario, "PAGO_FAMILIA", f"{ced} · {monto:g} · hasta {nueva}")
                    U.flash("ok", f"✅ Pago guardado. {r['Nombre']} queda pagado hasta el {nueva.strftime('%d/%m/%Y')}.")
                    U.nueva_version("pagf")
                    st.rerun()
        if not act.empty:
            st.markdown("##### 📅 Próximos vencimientos")
            tab = act[act["Pagado_Hasta"] != ""][["Nombre", "Habitacion", "Mensualidad", "Pagado_Hasta", "Acudiente_Nombre", "Acudiente_Tel"]].sort_values("Pagado_Hasta")
            if tab.empty:
                st.caption("Ningún residente tiene fecha de pago. Agréguela en **Residentes ▸ Corregir datos** (o al hacer el ingreso).")
            else:
                U.tabla(tab)

    with t2:
        ced = U.selector_residente("msg")
        if ced:
            r = act[act["Cedula"] == ced].iloc[0]
            pl = st.selectbox("¿Qué quiere enviar?", list(PLANTILLAS), key="msg_pl")
            hoy = N.hoy()
            extra = {"medicinas": _meds_bajos(ced) or "—", "aseo": _aseo_bajo(ced) or "—",
                     "desde": (hoy - timedelta(days=6)).strftime("%d/%m"), "hasta": hoy.strftime("%d/%m")}
            if r["Pagado_Hasta"]:
                dd = (N.parsear_fecha(r["Pagado_Hasta"]) - hoy).days
                extra["dias"] = f"en {dd} días" if dd > 0 else "hoy" if dd == 0 else f"hace {-dd} días"
            if pl.startswith("💊") and extra["medicinas"] == "—":
                st.info("Este residente no tiene medicinas por agotarse. Puede editar el mensaje igual.")
            msg = st.text_area("Mensaje (puede cambiarlo antes de enviar)", _texto(pl, r, **extra), height=150, key=f"msg_t_{ced}_{pl}")
            _enviar_wa(r, msg, pl.split(" ", 1)[1], f"msg_{ced}")

    with t3:
        U.ayuda(["Elija al residente y la fecha final de la semana.", "Toque **Crear PDF**.",
                 "Descárguelo y toque **ABRIR WHATSAPP**; en el chat adjunte el PDF descargado.",
                 "El PDF también queda guardado en la carpeta del residente (Reportes)."])
        ced = U.selector_residente("rep")
        if ced:
            r = act[act["Cedula"] == ced].iloc[0]
            hasta = st.date_input("Semana que termina el…", value=N.hoy(), max_value=N.hoy(), key=f"rep_h_{ced}")
            con_notas = st.checkbox("Incluir un resumen de las observaciones de enfermería", value=False, key=f"rep_n_{ced}")
            if st.button("📄 CREAR PDF", type="primary", key=f"rep_go_{ced}", **KW):
                desde = hasta - timedelta(days=6)
                rango = lambda s_, col: s_[(s_[col].str[:10] >= desde.isoformat()) & (s_[col].str[:10] <= hasta.isoformat())]
                vit = rango(N.leer("signos_vitales"), "Fecha_Hora")
                vit = vit[vit["Cedula"] == ced]
                kar = N.leer("kardex_meds")
                kar = kar[(kar["Cedula"] == ced) & (kar["Estado"] == "Activo")]
                ad = rango(N.leer("admin_meds"), "Fecha_Hora")
                ad = ad[ad["Cedula"] == ced]
                es = N.leer("escalas")
                es = es[es["Cedula"] == ced]
                sa = rango(N.leer("salidas"), "F_Salida")
                sa = sa[sa["Cedula"] == ced]
                no = None
                if con_notas:
                    no = rango(N.leer("notas_soapie"), "Fecha_Hora")
                    no = no[no["Cedula"] == ced]
                pdf = D.pdf_semanal(U.cli()["Nombre"], r.to_dict(), vit, kar, ad, es, sa, no, desde, hasta, U.quien(), N.calcular_edad(r["Fecha_Nacimiento"]))
                st.session_state[f"pdf_{ced}"] = (pdf, desde, hasta)
                try:
                    N.guardar_archivo(U.cfg(), ced, r["Nombre"], "Reportes", f"reporte_{desde.isoformat()}_{hasta.isoformat()}.pdf", pdf, "application/pdf", U.firma())
                except (ValueError, N.ErrorNube) as e:
                    st.warning(f"El PDF se creó, pero no se pudo guardar en la carpeta: {e}")
                N.log(st.session_state.usuario, "GENERA_REPORTE_SEMANAL", f"{ced} · {desde} → {hasta}")
            gen = st.session_state.get(f"pdf_{ced}")
            if gen:
                pdf, desde, hasta = gen
                st.success("✅ PDF listo.")
                st.download_button("⬇️ DESCARGAR PDF", pdf, file_name=f"resumen_{r['Cedula']}_{hasta.isoformat()}.pdf", mime="application/pdf", key=f"dl_rep_{ced}", **KW)
                txt = _texto("📄 Reporte semanal de salud", r, desde=desde.strftime("%d/%m"), hasta=hasta.strftime("%d/%m"))
                _enviar_wa(r, txt, "Reporte semanal", f"rep_{ced}")

    with t4:
        cm = N.leer("comunicaciones").sort_values("Fecha_Hora", ascending=False)
        nombres = res.set_index("Cedula")["Nombre"].to_dict()
        st.markdown("##### 📨 Mensajes enviados")
        if cm.empty:
            st.caption("Aún no hay mensajes registrados.")
        else:
            U.tabla(cm.assign(Residente=cm["Cedula"].map(nombres))[["Fecha_Hora", "Residente", "Tipo", "Canal", "Autor"]].head(100))
        pf = N.leer("pagos_familia").sort_values("Fecha", ascending=False)
        st.markdown("##### 💵 Pagos de familias")
        if pf.empty:
            st.caption("Aún no hay pagos registrados.")
        else:
            U.tabla(pf.assign(Residente=pf["Cedula"].map(nombres))[["Fecha", "Residente", "Monto", "Metodo", "Pagado_Hasta", "Dias_Atraso", "Autor"]].head(100))


# ══════════════════════════════════════════════════════════════
# CONTRATOS
# ══════════════════════════════════════════════════════════════
def pagina_contratos():
    U.banner("Familias", "Contratos", "Suba el contrato de su geriátrico una vez y el sistema lo llena solo para cada residente.")
    t1, t2, t3 = st.tabs(["📤 Subir mi contrato", "🖨 Hacer un contrato", "📚 Contratos hechos"])
    pl = N.leer("plantillas_contrato").sort_values("Fecha_Hora", ascending=False)
    with t1:
        U.ayuda(["Abra su contrato en Word y, donde va un dato del residente, escriba el **marcador** entre paréntesis e igual. Ejemplo: donde va el nombre escriba `(=NOMBRE=)`.",
                 "Guarde el Word (.docx) y súbalo aquí.", "El sistema le dice qué marcadores encontró.",
                 "Si ya tiene el contrato con firma o sellos como imagen, se conservan. Si la firma es digital criptográfica, el contrato generado debe firmarse de nuevo."])
        st.markdown("##### 🏷 Marcadores disponibles")
        U.tabla(pd.DataFrame({"Escriba esto en su contrato": [f"(={k}=)" for k in D.CAMPOS_CONTRATO], "Se reemplaza por": list(D.CAMPOS_CONTRATO.values())}))
        st.download_button("⬇️ Bajar un contrato de ejemplo (Word)", D.plantilla_ejemplo(), file_name="contrato_ejemplo.docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="dl_ejemplo")
        v = U.ver("plant")
        with st.form(f"form_plant_{v}"):
            nom = st.text_input("Nombre de esta plantilla", key=f"pl_n_{v}", placeholder="Ej: Contrato de ingreso 2026")
            arch = st.file_uploader("Archivo Word (.docx) · máx. 6 MB", type=["docx"], key=f"pl_f_{v}")
            if st.form_submit_button("📤 GUARDAR PLANTILLA", type="primary", **KW):
                if not nom.strip() or arch is None:
                    st.error("Escriba un nombre y elija el archivo.")
                else:
                    try:
                        datos = arch.getvalue()
                        ok, desc = D.campos_plantilla(datos)
                        if not ok:
                            raise ValueError("No encontré ningún marcador como (=NOMBRE=) en el documento. Revise el paso 1.")
                        fila = N.guardar_archivo(U.cfg(), "", "", "Plantillas", f"{nom.strip()}.docx", datos,
                                                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document", U.firma())
                        N.agregar("plantillas_contrato", {"ID": N.nueva_id("PL"), "Nombre": nom.strip(), "Archivo_ID": fila["ID"], "Fecha_Hora": N.fmt_fh(), "Autor": U.firma()})
                        N.log(st.session_state.usuario, "SUBE_PLANTILLA_CONTRATO", nom.strip())
                        msg = f"✅ Plantilla guardada. Marcadores reconocidos: {', '.join(ok)}."
                        if desc:
                            msg += f" ⚠ No reconocidos (quedarán sin cambiar): {', '.join(desc)}."
                        U.flash("warn" if desc else "ok", msg)
                        U.nueva_version("plant")
                        st.rerun()
                    except (ValueError, N.ErrorNube) as e:
                        st.error(str(e))
    with t2:
        if pl.empty:
            st.info("Primero suba una plantilla en la pestaña **📤 Subir mi contrato**.")
        else:
            ced = U.selector_residente("con", solo_activos=False)
            if ced:
                r = U.ficha(ced)
                pid = st.selectbox("Plantilla", pl["ID"].tolist(), format_func=lambda i: pl[pl["ID"] == i].iloc[0]["Nombre"], key="con_pl")
                if st.button("🖨 GENERAR CONTRATO", type="primary", key=f"con_go_{ced}", **KW):
                    datos, _ = U.bytes_de(pl[pl["ID"] == pid].iloc[0]["Archivo_ID"])
                    if not datos:
                        st.error("No se pudo abrir la plantilla desde la carpeta.")
                    else:
                        cli = U.cli()
                        hoy = N.hoy()
                        vals = {"NOMBRE": r["Nombre"], "CEDULA": r["Cedula"], "FECHA_NACIMIENTO": D.fecha_larga(N.parsear_fecha(r["Fecha_Nacimiento"])) if N.parsear_fecha(r["Fecha_Nacimiento"]) else "",
                                "EDAD": N.calcular_edad(r["Fecha_Nacimiento"]) or "", "SEXO": r["Sexo"], "EPS": r["EPS"], "HABITACION": r["Habitacion"],
                                "DIAGNOSTICOS": r["Diagnosticos"], "ALERGIAS": r["Alergias"], "ACUDIENTE": r["Acudiente_Nombre"], "TELEFONO_ACUDIENTE": r["Acudiente_Tel"],
                                "FECHA_INGRESO": D.fecha_larga(N.parsear_fecha(r["F_Ingreso"])) if N.parsear_fecha(r["F_Ingreso"]) else "",
                                "MENSUALIDAD": N.cop(r["Mensualidad"]) if r["Mensualidad"] else "", "GERIATRICO": cli["Nombre"], "NIT": cli["NIT"],
                                "FECHA_HOY": D.fecha_larga(hoy), "FECHA_HOY_CORTA": hoy.strftime("%d/%m/%Y")}
                        try:
                            docx_b, faltan = D.generar_contrato(datos, vals)
                            fila = N.guardar_archivo(U.cfg(), ced, r["Nombre"], "Contratos", f"contrato_{r['Cedula']}_{hoy.isoformat()}.docx", docx_b,
                                                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document", U.firma())
                            N.agregar("contratos", {"ID": N.nueva_id("CT"), "Cedula": ced, "Plantilla": pl[pl["ID"] == pid].iloc[0]["Nombre"],
                                                    "Fecha_Hora": N.fmt_fh(), "Archivo_ID": fila["ID"], "Autor": U.firma()})
                            N.log(st.session_state.usuario, "GENERA_CONTRATO", f"{ced} · {pid}")
                            st.session_state[f"contrato_{ced}"] = (docx_b, faltan)
                        except (ValueError, N.ErrorNube) as e:
                            st.error(str(e))
                gen = st.session_state.get(f"contrato_{ced}")
                if gen:
                    docx_b, faltan = gen
                    st.success("✅ Contrato listo y guardado en la carpeta del residente (Contratos).")
                    if faltan:
                        st.warning("Estos marcadores no se reconocieron y quedaron sin cambiar: " + ", ".join(f"(={f}=)" for f in faltan))
                    st.download_button("⬇️ DESCARGAR CONTRATO (Word)", docx_b, file_name=f"contrato_{r['Cedula']}.docx",
                                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_con_{ced}", **KW)
    with t3:
        ct = N.leer("contratos").sort_values("Fecha_Hora", ascending=False)
        nombres = N.leer("residentes").set_index("Cedula")["Nombre"].to_dict()
        if ct.empty:
            st.caption("Aún no se ha generado ningún contrato.")
        else:
            U.tabla(ct.assign(Residente=ct["Cedula"].map(nombres))[["Fecha_Hora", "Residente", "Plantilla", "Autor"]])


# ══════════════════════════════════════════════════════════════
# ARCHIVOS (solo administración, solo lectura)
# ══════════════════════════════════════════════════════════════
def pagina_archivos():
    U.banner("Admin", "Archivos", "Todo lo que se ha guardado en la carpeta de su geriátrico. Aquí solo se mira y se descarga: nada se borra.")
    ar = N.leer("archivos").sort_values("Fecha_Hora", ascending=False)
    if ar.empty:
        st.info("Todavía no hay archivos. Aparecen aquí cuando el equipo sube fotos, anexos, reportes o contratos.")
        return
    res = N.leer("residentes").set_index("Cedula")["Nombre"].to_dict()
    ar = ar.assign(Residente=ar["Cedula"].map(res).fillna("(General)"))
    c1, c2, c3 = st.columns(3)
    quien_ = c1.selectbox("👤 Residente", ["Todos"] + sorted(ar["Residente"].unique()), key="ar_r")
    cat = c2.selectbox("📁 Carpeta", ["Todas"] + sorted(ar["Categoria"].unique()), key="ar_c")
    q = c3.text_input("🔍 Buscar por nombre", key="ar_q")
    if quien_ != "Todos":
        ar = ar[ar["Residente"] == quien_]
    if cat != "Todas":
        ar = ar[ar["Categoria"] == cat]
    if q.strip():
        ar = ar[ar["Nombre"].str.contains(q.strip(), case=False, regex=False)]
    st.caption(f"{len(ar)} archivos")
    imgs = ar[ar["Nombre"].str.lower().str.endswith((".jpg", ".jpeg", ".png"))]
    otros = ar.drop(imgs.index)
    if not imgs.empty:
        st.markdown("##### 🖼 Fotos")
        lim = st.session_state.get("ar_lim", 12)
        cols = st.columns(4)
        for i, x in enumerate(imgs.head(lim).to_dict("records")):
            datos, _ = U.bytes_de(x["ID"])
            with cols[i % 4]:
                if datos:
                    st.image(datos, width=220)
                st.caption(f"{x['Residente']} · {x['Categoria']}\n{x['Fecha_Hora'][:16]}")
        if len(imgs) > lim and st.button("Ver más fotos", key="ar_mas"):
            st.session_state["ar_lim"] = lim + 12
            st.rerun()
    if not otros.empty:
        st.markdown("##### 📄 Documentos")
        U.tabla(otros[["Fecha_Hora", "Residente", "Categoria", "Nombre", "Autor"]])
        sel = st.selectbox("Abrir un documento", otros["ID"].tolist(), format_func=lambda i: otros[otros["ID"] == i].iloc[0]["Nombre"], key="ar_sel")
        datos, fila = U.bytes_de(sel)
        if datos:
            st.download_button("⬇️ Descargar", datos, file_name=fila["Nombre"], key=f"ar_dl_{sel}")


# ══════════════════════════════════════════════════════════════
# MONITOR DE ACTIVIDAD (solo administración)
# ══════════════════════════════════════════════════════════════
def _terminal(df):
    lineas = []
    for r in df.sort_values("Fecha_Hora", ascending=False).head(400).to_dict("records"):
        tipo = r.get("Tipo") or "DATO"
        cls = {"CLIC": "c", "SEGURIDAD": "s", "PANTALLA": "v", "DATO": "d"}.get(tipo, "d")
        det = f": {r['Detalle']}" if r["Detalle"] else ""
        pag = f" {r['Pagina']} ›" if r.get("Pagina") else ""
        lineas.append(f"<span class='t'>{h(r['Fecha_Hora'][5:])}</span> <span class='u'>{h(r['Usuario'])}</span> "
                      f"<span class='{cls}'>[{h(tipo)}]</span>{h(pag)} {h(r['Accion'])}{h(det)}")
    st.markdown("<div class='term'>" + ("<br>".join(lineas) or "Sin actividad para estos filtros.") + "</div>", unsafe_allow_html=True)


def _cuerpo_monitor():
    lg = N.leer("logs", fresco=True)
    if lg.empty:
        st.info("Aún no hay actividad.")
        return
    c1, c2, c3 = st.columns([1, 2, 2])
    dia = c1.date_input("📅 Día", value=N.hoy(), max_value=N.hoy(), key="mon_dia")
    usuarios = sorted(lg["Usuario"].unique())
    sel_u = c2.multiselect("👤 Personas", usuarios, key="mon_u")
    tipos = c3.multiselect("🏷 Tipo", ["CLIC", "DATO", "PANTALLA", "SEGURIDAD"], key="mon_t")
    d = lg[lg["Fecha_Hora"].str[:10] == dia.isoformat()]
    if sel_u:
        d = d[d["Usuario"].isin(sel_u)]
    if tipos:
        d = d[d["Tipo"].replace("", "DATO").isin(tipos)]
    if d.empty:
        st.info("No hay actividad con estos filtros.")
        return
    resumen = d.groupby("Usuario").agg(Rol=("Rol", "last"), Acciones=("Accion", "count"), Primer=("Fecha_Hora", "min"), Ultimo=("Fecha_Hora", "max")).reset_index()
    resumen["Primer"], resumen["Ultimo"] = resumen["Primer"].str[11:], resumen["Ultimo"].str[11:]
    st.markdown("##### 👥 Quién hizo qué hoy")
    U.tabla(resumen.rename(columns={"Primer": "Primer movimiento", "Ultimo": "Último movimiento"}))
    t1, t2, t3 = st.tabs(["🖥 Todo junto", "👤 Por persona", "🔐 Seguridad"])
    with t1:
        _terminal(d)
    with t2:
        for u in resumen["Usuario"]:
            sub = d[d["Usuario"] == u]
            with st.expander(f"👤 {u} · {len(sub)} movimientos"):
                _terminal(sub)
    with t3:
        sg = lg[lg["Accion"].isin(["LOGIN_FALLIDO", "BLOQUEO_TEMPORAL", "SESION_EXPIRADA", "ACCESO_DENEGADO"]) | (lg["Tipo"] == "SEGURIDAD")]
        if sg.empty:
            U.aviso("Sin eventos de seguridad.", "ok")
        else:
            U.tabla(sg.sort_values("Fecha_Hora", ascending=False)[["Fecha_Hora", "Usuario", "Accion", "Detalle"]].head(100))


def pagina_monitor():
    U.banner("Admin", "Monitor de actividad", "Qué hizo cada persona, a qué hora y hasta qué botón tocó.")
    auto = st.toggle("🔄 Actualizar solo cada 10 segundos", key="mon_auto") if hasattr(st, "toggle") else False
    if not auto:
        st.button("🔄 Actualizar ahora", key="mon_ref")
    if auto and hasattr(st, "fragment"):
        st.fragment(run_every=10)(_cuerpo_monitor)()
    else:
        _cuerpo_monitor()


# ══════════════════════════════════════════════════════════════
# ADMINISTRACIÓN
# ══════════════════════════════════════════════════════════════
def pagina_admin():
    U.banner("Admin", "Administración", "Usuarios, indicaciones para el equipo, auditoría y copia de seguridad.")
    cli = U.cli()
    t1, t2, t3, t4, t5 = st.tabs(["👥 Usuarios", "📢 Indicaciones", "🧾 Auditoría", "📦 Mi plan", "💾 Respaldo"])
    mx = int(N._num(cli["Max_Usuarios"])) if cli else 0
    roles_ok = N.roles_cliente(cli)

    with t1:
        usr = N.leer("usuarios")
        activos = int((usr["Activo"].str.upper() != "NO").sum())
        lleno = bool(mx) and activos >= mx
        st.markdown(chip(f"Usuarios activos: {activos}" + (f" de {mx} permitidos por su plan" if mx else ""), "warn" if lleno else "ok"), unsafe_allow_html=True)
        U.tabla(usr.drop(columns=["Password"]))
        v = U.ver("usr")
        a, b = st.columns(2)
        with a:
            with st.form(f"form_usr_{v}"):
                st.markdown("##### ➕ Crear usuario")
                u = st.text_input("Usuario (sin espacios)", key=f"u_u_{v}")
                al = st.text_input("Nombre que se mostrará", key=f"u_a_{v}")
                rol = st.selectbox("¿Qué hace en el geriátrico?", roles_ok, key=f"u_r_{v}")
                reg = st.text_input("Registro profesional (si aplica)", key=f"u_g_{v}")
                pw = st.text_input("Contraseña temporal (8+ con letras y números)", type="password", key=f"u_p_{v}")
                st.caption("La persona deberá cambiarla en su primer ingreso.")
                if st.form_submit_button("➕ CREAR USUARIO", type="primary", **KW):
                    ul = u.strip().lower()
                    problema = N.validar_clave(pw)
                    if lleno:
                        st.error(f"Su plan permite {mx} usuarios activos. Desactive uno o pida ampliar su plan.")
                    elif not ul or " " in ul or not al.strip():
                        st.error("Escriba un usuario sin espacios y el nombre que se mostrará.")
                    elif problema:
                        st.error(problema)
                    elif ul in usr["Usuario"].str.lower().values:
                        st.error("Ese usuario ya existe.")
                    else:
                        N.agregar("usuarios", {"Usuario": ul, "Password": N.hash_pw(pw), "Rol": rol, "Alias": al.strip(),
                                               "Reg_Profesional": reg.strip(), "Activo": "SI", "Cambiar_Clave": "SI"})
                        N.log(st.session_state.usuario, "CREA_USUARIO", f"{ul} · {rol}")
                        U.flash("ok", f"✅ Usuario {ul} creado.")
                        U.nueva_version("usr")
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
                    elif nuevo_pw and N.validar_clave(nuevo_pw):
                        st.error(N.validar_clave(nuevo_pw))
                    else:
                        cambios = {"Activo": "SI" if estado == "Activo" else "NO"}
                        if nuevo_pw:
                            cambios.update(Password=N.hash_pw(nuevo_pw), Cambiar_Clave="SI")
                        N.actualizar("usuarios", "Usuario", sel, cambios)
                        N.log(st.session_state.usuario, "MODIFICA_USUARIO", f"{sel} · {estado}")
                        U.flash("ok", f"✅ Usuario {sel} actualizado.")
                        U.nueva_version("usr")
                        st.rerun()

    with t2:
        mods = N.modulos_cliente(cli)
        secs = ["Enfermería"] + (["Cocina"] if "Cocina" in mods else []) + (["Aseo"] if "Aseo" in mods else [])
        v = U.ver("ind")
        with st.form(f"form_ind_{v}"):
            st.markdown("##### 📢 Nueva indicación para el equipo")
            sec = st.selectbox("¿Para quién?", secs, key=f"in_s_{v}")
            tit = st.text_input("Título corto", key=f"in_t_{v}", placeholder="Ej: Dieta blanda para la habitación 3")
            txt = st.text_area("Indicación", key=f"in_x_{v}", height=90)
            if st.form_submit_button("📢 PUBLICAR", type="primary", **KW):
                if not tit.strip() or not txt.strip():
                    st.error("Escriba el título y la indicación.")
                else:
                    N.agregar("indicaciones", {"ID": N.nueva_id("IN"), "Seccion": "Enfermeria" if sec == "Enfermería" else sec, "Fecha_Hora": N.fmt_fh(),
                                               "Titulo": tit.strip(), "Texto": txt.strip(), "Autor": U.quien(), "Activa": "SI"})
                    N.log(st.session_state.usuario, "PUBLICA_INDICACION", f"{sec} · {tit.strip()}")
                    U.flash("ok", "✅ Indicación publicada.")
                    U.nueva_version("ind")
                    st.rerun()
        ind = N.leer("indicaciones").sort_values("Fecha_Hora", ascending=False)
        for x in ind.head(30).to_dict("records"):
            activa = x["Activa"].upper() != "NO"
            c1, c2 = st.columns([5, 1.4])
            c1.markdown(f"{'🟢' if activa else '⚪'} **{h(x['Seccion'])}** · {h(x['Titulo'])} — {h(x['Texto'])}", unsafe_allow_html=True)
            if c2.button("Quitar" if activa else "Volver a poner", key=f"ind_{x['ID']}"):
                N.actualizar("indicaciones", "ID", x["ID"], {"Activa": "NO" if activa else "SI"})
                st.rerun()

    with t3:
        lg = N.leer("logs").sort_values("Fecha_Hora", ascending=False)
        q = st.text_input("Filtrar por usuario o acción", key="q_log")
        if q.strip():
            lg = lg[lg["Usuario"].str.contains(q.strip(), case=False, regex=False) | lg["Accion"].str.contains(q.strip(), case=False, regex=False)]
        U.tabla(lg.head(300))
        st.download_button("⬇️ Descargar auditoría (CSV)", N.csv_seguro(lg), file_name="auditoria.csv", mime="text/csv")

    with t4:
        plan = N.PLANES.get(cli["Plan"], {})
        res = N.leer("residentes")
        n_res = int((res["Estado"] != "Egresado").sum())
        mxr = int(N._num(cli.get("Max_Residentes", 0)))
        st.markdown(f"### Plan **{h(cli['Plan'] or '—')}**")
        c = st.columns(3)
        c[0].markdown(U.kpi(f"{n_res}" + (f" / {mxr}" if mxr else ""), "Residentes activos"), unsafe_allow_html=True)
        c[1].markdown(U.kpi(f"{int((N.leer('usuarios')['Activo'].str.upper() != 'NO').sum())}" + (f" / {mx}" if mx else ""), "Usuarios activos"), unsafe_allow_html=True)
        c[2].markdown(U.kpi(cli["Vence"] or "—", "Vigente hasta"), unsafe_allow_html=True)
        mods = N.modulos_cliente(cli)
        st.markdown("**Módulos:** " + " · ".join(f"{'✅' if k in mods else '🔒'} {v}" for k, v in N.MODULOS.items()))
        st.markdown("**Roles que puede crear:** " + ", ".join(roles_ok))
        if plan.get("beneficios"):
            st.markdown("**Beneficios:**\n" + "\n".join(f"- {b}" for b in plan["beneficios"]))
        st.caption("¿Necesita más usuarios, residentes o módulos? Escriba a su proveedor para ampliar el plan.")

    with t5:
        if N.estado_nube()["conectado"]:
            st.success("✅ Su información se guarda en una bóveda exclusiva de su geriátrico. Ningún otro geriátrico puede verla.")
        else:
            st.info("Modo de demostración local.")
        st.markdown("##### 💾 Copia de seguridad (CSV)")
        st.caption("Descargue sus datos cuando quiera: son suyos.")
        cols = st.columns(3)
        for i, t in enumerate([t for t in N.ESQUEMA if t != "usuarios"]):
            cols[i % 3].download_button(f"⬇️ {t}", N.csv_seguro(N.leer(t)), file_name=f"{t}.csv", mime="text/csv", key=f"bk_{t}")
