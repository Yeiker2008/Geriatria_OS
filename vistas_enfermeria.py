# -*- coding: utf-8 -*-
"""vistas_enfermeria.py · Pantallas de ENFERMERÍA (residentes, medicamentos, signos, notas, kardex, pertenencias, salidas, escalas)."""
import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import documentos as D
import nucleo as N
import ui as U
from ui import KW, chip, h

SEC = "Enfermeria"
PUEDE_DAR = (N.R_ENF, N.R_AUX, N.R_ADMIN)
VE_DINERO = (N.R_ADMIN, N.R_FAM)


# ══════════════════════════════════════════════════════════════
# RESIDENTES
# ══════════════════════════════════════════════════════════════
def pagina_residentes():
    U.banner(SEC, "Residentes", "Aquí se ingresa y se consulta a cada adulto mayor.")
    t1, t2, t3 = st.tabs(["📋 Ver residentes", "➕ Nuevo ingreso", "📎 Documentos (anexos)"])
    ve_dinero = U.rol() in VE_DINERO

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
            cols = ["Cedula", "Nombre", "Edad", "Habitacion", "EPS", "Alergias", "Acudiente_Nombre", "Acudiente_Tel", "Estado"]
            tabla = d[cols + (["Mensualidad", "Pagado_Hasta"] if ve_dinero else [])]
            U.tabla(tabla)
        st.divider()
        ced = U.selector_residente("dir", solo_activos=False, etiqueta="Elija un residente para ver o corregir sus datos")
        if ced:
            r = U.ficha(ced)
            v = U.ver("edit")
            with st.form(f"form_edit_{v}"):
                st.markdown("##### ✏️ Corregir datos")
                a, b, c = st.columns(3)
                nom = a.text_input("Nombre completo", r["Nombre"], key=f"e_nom_{ced}_{v}")
                sexo = b.selectbox("Sexo", ["Femenino", "Masculino", "Otro"],
                                   index=["Femenino", "Masculino", "Otro"].index(r["Sexo"]) if r["Sexo"] in ("Femenino", "Masculino", "Otro") else 0,
                                   key=f"e_sex_{ced}_{v}")
                hab = c.text_input("Habitación / cama", r["Habitacion"], key=f"e_hab_{ced}_{v}")
                a, b = st.columns(2)
                eps = a.text_input("EPS / medicina prepagada", r["EPS"], key=f"e_eps_{ced}_{v}")
                with b:
                    fn = U.selector_fecha("Fecha de nacimiento", N.parsear_fecha(r["Fecha_Nacimiento"]) or date(1945, 1, 1), f"e_fn_{ced}_{v}")
                dx = st.text_area("Diagnósticos principales", r["Diagnosticos"], key=f"e_dx_{ced}_{v}", height=80)
                al = st.text_input("Alergias (escriba «Ninguna» si no tiene)", r["Alergias"], key=f"e_al_{ced}_{v}")
                a, b = st.columns(2)
                acn = a.text_input("Familiar / acudiente", r["Acudiente_Nombre"], key=f"e_acn_{ced}_{v}")
                act_ = b.text_input("Teléfono del acudiente (WhatsApp)", r["Acudiente_Tel"], key=f"e_act_{ced}_{v}")
                cambios_extra = {}
                if ve_dinero:
                    a, b = st.columns(2)
                    mens = a.number_input("Mensualidad (COP)", min_value=0.0, value=float(N._num(r["Mensualidad"])), step=10000.0, key=f"e_men_{ced}_{v}")
                    cambios_extra = {"Mensualidad": mens}
                if st.form_submit_button("💾 GUARDAR CAMBIOS", type="primary", **KW):
                    if not nom.strip():
                        st.error("El nombre es obligatorio.")
                    elif fn is None:
                        st.error("La fecha de nacimiento no es válida.")
                    else:
                        N.actualizar("residentes", "Cedula", ced, {
                            "Nombre": nom.strip(), "Sexo": sexo, "Habitacion": hab.strip(), "EPS": eps.strip(),
                            "Fecha_Nacimiento": fn.isoformat(), "Diagnosticos": dx.strip(), "Alergias": al.strip(),
                            "Acudiente_Nombre": acn.strip(), "Acudiente_Tel": act_.strip(), **cambios_extra})
                        N.log(st.session_state.usuario, "EDITA_RESIDENTE", ced)
                        U.flash("ok", "✅ Datos actualizados.")
                        U.nueva_version("edit")
                        st.rerun()

            with st.expander("🚪 Egreso o reingreso del residente"):
                if r["Estado"] == "Egresado":
                    st.write(f"Egresó el **{r['F_Egreso']}** · motivo: {r['Motivo_Egreso']}")
                    ok, motivo = N.puede_admitir(U.cli())
                    if st.button("↩️ Reactivar residente", key=f"react_{ced}", disabled=not ok):
                        N.actualizar("residentes", "Cedula", ced, {"Estado": "Activo", "F_Egreso": "", "Motivo_Egreso": ""})
                        N.log(st.session_state.usuario, "REACTIVA_RESIDENTE", ced)
                        U.flash("ok", "✅ Residente reactivado.")
                        st.rerun()
                    if not ok:
                        st.warning(motivo)
                else:
                    motivo = st.selectbox("Motivo de egreso", ["Traslado a hospital", "Retorno a domicilio", "Traslado a otra institución",
                                                               "Fallecimiento", "Otro"], key=f"mot_{ced}")
                    if st.button("Registrar egreso", key=f"egr_{ced}"):
                        N.actualizar("residentes", "Cedula", ced, {"Estado": "Egresado", "F_Egreso": N.hoy().isoformat(), "Motivo_Egreso": motivo})
                        N.log(st.session_state.usuario, "EGRESO_RESIDENTE", f"{ced} · {motivo}")
                        U.flash("ok", "✅ Egreso registrado.")
                        st.rerun()

    with t2:
        ok, motivo = N.puede_admitir(U.cli())
        if not ok:
            U.aviso(f"⛔ {motivo} Para ingresar más residentes pida ampliar su plan.", "crit")
        else:
            v = U.ver("adm")
            with st.form(f"form_adm_{v}"):
                st.markdown("##### 1️⃣ Datos del residente")
                a, b, c = st.columns(3)
                cc = a.text_input("Cédula", key=f"a_cc_{v}")
                nom = b.text_input("Nombre completo", key=f"a_nom_{v}")
                sexo = c.selectbox("Sexo", ["Femenino", "Masculino", "Otro"], key=f"a_sex_{v}")
                a, b, c = st.columns([1.6, 1, 1])
                with a:
                    fn = U.selector_fecha("Fecha de nacimiento", date(1945, 1, 1), f"a_fn_{v}")
                hab = b.text_input("Habitación / cama", key=f"a_hab_{v}")
                ing = c.date_input("Fecha de ingreso", value=N.hoy(), max_value=N.hoy(), key=f"a_ing_{v}")
                eps = st.text_input("EPS / medicina prepagada", key=f"a_eps_{v}")
                dx = st.text_area("Diagnósticos principales", key=f"a_dx_{v}", height=80)
                al = st.text_input("⚠ Alergias (escriba «Ninguna» si no tiene)", key=f"a_al_{v}")
                st.markdown("##### 2️⃣ Familia")
                a, b = st.columns(2)
                acn = a.text_input("Familiar / acudiente", key=f"a_acn_{v}")
                act_ = b.text_input("Teléfono / WhatsApp del acudiente", key=f"a_act_{v}")
                mens, paga = 0.0, None
                if ve_dinero:
                    st.markdown("##### 3️⃣ Pago mensual")
                    a, b = st.columns(2)
                    mens = a.number_input("Mensualidad (COP)", min_value=0.0, step=10000.0, key=f"a_men_{v}")
                    paga = b.date_input("Pagado hasta (fecha límite del próximo pago)", value=N.sumar_meses(N.hoy(), 1), key=f"a_pag_{v}")
                if st.form_submit_button("✅ REGISTRAR INGRESO", type="primary", **KW):
                    ccl = cc.strip().replace(".", "").replace(" ", "")
                    ya = N.leer("residentes")
                    if not ccl or not nom.strip():
                        st.error("La cédula y el nombre son obligatorios.")
                    elif fn is None:
                        st.error("La fecha de nacimiento no existe o está en el futuro. Revise día, mes y año.")
                    elif not al.strip():
                        st.error("Indique las alergias (o escriba «Ninguna»). Es un dato de seguridad del paciente.")
                    elif ccl in ya["Cedula"].values:
                        st.error("Ya existe un residente con esa cédula. Si egresó, reactívelo desde «Ver residentes».")
                    else:
                        N.agregar("residentes", {
                            "Cedula": ccl, "Nombre": nom.strip(), "Fecha_Nacimiento": fn.isoformat(), "Sexo": sexo,
                            "EPS": eps.strip(), "Habitacion": hab.strip(), "Diagnosticos": dx.strip(), "Alergias": al.strip(),
                            "Acudiente_Nombre": acn.strip(), "Acudiente_Tel": act_.strip(), "Estado": "Activo",
                            "F_Ingreso": ing.isoformat(), "Mensualidad": mens or "", "Pagado_Hasta": paga.isoformat() if paga else ""})
                        N.log(st.session_state.usuario, "ADMISION", f"{ccl} · {nom.strip()}")
                        try:
                            N.crear_carpetas_residente(U.cfg(), ccl, nom.strip())
                            extra = " Su carpeta con subcarpetas quedó creada en la nube."
                        except Exception:
                            extra = " (La carpeta en Drive se creará sola con el primer archivo que suba.)"
                        st.session_state["res_sel"] = ccl
                        U.flash("ok", f"✅ {nom.strip()} fue ingresado/a correctamente.{extra}")
                        U.nueva_version("adm")
                        st.rerun()

    with t3:
        ced = U.selector_residente("anx", solo_activos=False)
        if ced:
            r = U.ficha(ced)
            U.ayuda(["Toque «Elegir archivo» y escoja el documento (PDF o foto).", "Escriba un nombre claro, por ejemplo «Fórmula médica octubre».",
                     "Toque «Guardar». Queda en la carpeta del residente (subcarpeta Anexos)."])
            v = U.ver("anexo")
            with st.form(f"form_anexo_{v}"):
                nombre = st.text_input("Nombre del documento", key=f"ax_n_{v}")
                arch = st.file_uploader("Archivo (PDF, JPG o PNG · máx. 10 MB)", type=["pdf", "jpg", "jpeg", "png"], key=f"ax_f_{v}")
                if st.form_submit_button("📎 GUARDAR DOCUMENTO", type="primary", **KW):
                    if not nombre.strip() or arch is None:
                        st.error("Escriba un nombre y elija un archivo.")
                    else:
                        datos, mime = arch.getvalue(), arch.type or "application/octet-stream"
                        try:
                            if len(datos) > 10 * 1024 * 1024:
                                raise ValueError("El archivo pesa más de 10 MB.")
                            if arch.name.lower().endswith(".pdf"):
                                if not datos.startswith(b"%PDF"):
                                    raise ValueError("El archivo no es un PDF válido.")
                                nom_f = f"{nombre.strip()}.pdf"
                            else:
                                datos, mime, nom_f = D.procesar_imagen(datos), "image/jpeg", f"{nombre.strip()}.jpg"
                            N.guardar_archivo(U.cfg(), ced, r["Nombre"], "Anexos", nom_f, datos, mime, U.firma())
                            N.log(st.session_state.usuario, "SUBE_ANEXO", f"{ced} · {nom_f}")
                            U.flash("ok", "✅ Documento guardado en la carpeta del residente.")
                            U.nueva_version("anexo")
                            st.rerun()
                        except (ValueError, N.ErrorNube) as e:
                            st.error(str(e))
            ar = N.leer("archivos")
            ar = ar[(ar["Cedula"] == ced) & (ar["Categoria"] == "Anexos")].sort_values("Fecha_Hora", ascending=False)
            if ar.empty:
                st.caption("Este residente aún no tiene documentos.")
            else:
                U.tabla(ar[["Fecha_Hora", "Nombre", "Autor"]])
                ids = ar["ID"].tolist()
                sel = st.selectbox("Abrir un documento", ids, format_func=lambda i: ar[ar["ID"] == i].iloc[0]["Nombre"], key="anx_dl")
                datos, fila = U.bytes_de(sel)
                if datos:
                    st.download_button("⬇️ Descargar", datos, file_name=fila["Nombre"], key=f"dl_anx_{sel}")


# ══════════════════════════════════════════════════════════════
# DAR MEDICAMENTOS (ronda del día)
# ══════════════════════════════════════════════════════════════
def _desvio_txt(d):
    try:
        m = int(d)
    except (TypeError, ValueError):
        return ""
    if abs(m) <= 5:
        return "a tiempo"
    return f"{m} min tarde" if m > 0 else f"{-m} min antes"


def _fila_dosis(d, puede_dar, alergias):
    cls = d["Estado"].replace(" ", "-")
    al = alergias.get(d["Cedula"], "").strip()
    al_chip = chip(f"⚠ Alergia: {al}", "crit") if al and al.lower() not in ("ninguna", "no", "n/a", "ninguna conocida") else ""
    estado = {"Atrasado": chip("🔴 ATRASADA", "crit"), "Ahora": chip("🟡 Es la hora", "warn"), "Pendiente": chip("⏳ Más tarde", "info"),
              "Dado": chip(f"✅ Dada a las {d['Real']} · {d['Quien']} · {_desvio_txt(d['Desvio'])}", "ok"),
              "No dado": chip(f"❌ No se dio: {d['Observacion']}", "crit")}[d["Estado"]]
    ind = f"<div class='det'>📌 {h(d['Indicaciones'])}</div>" if d["Indicaciones"].strip() else ""
    izq, der = st.columns([5, 2.3])
    izq.markdown(U.bloque(f"""<div class='dosis {cls}'><div style='display:flex;gap:18px;align-items:center'>
        <div class='hora'>{d['Hora']}</div><div><div class='med'>💊 {h(d['Medicamento'])} · {h(d['Dosis'])} · {h(d['Via'])}</div>
        <div class='det'>👤 {h(d['Residente'])} · Hab. {h(d['Habitacion'] or '—')}</div>{ind}<div>{estado}{al_chip}</div></div></div></div>"""),
                 unsafe_allow_html=True)
    if d["Estado"] in ("Dado", "No dado") or not puede_dar:
        return
    k = f"{d['ID_Med']}_{d['Hora'].replace(':', '')}"
    with der:
        if st.button("✅ YA SE LA DI", key=f"dar_{k}", **KW):
            try:
                desv = N.registrar_dosis(d["Cedula"], d["ID_Med"], d["Hora"], "Administrado", "", U.firma())
                N.log(st.session_state.usuario, "ADMINISTRA_MED", f"{d['Cedula']} · {d['Medicamento']} {d['Dosis']} · prog {d['Hora']} · {_desvio_txt(desv)}")
                U.flash("ok", f"✅ Guardado: {d['Medicamento']} para {d['Residente']} a las {N.ahora().strftime('%H:%M')}.")
            except ValueError as e:
                U.flash("warn", str(e))
            st.rerun()
        cont = st.popover("❌ No se pudo dar", **KW) if hasattr(st, "popover") else st.expander("❌ No se pudo dar")
        with cont:
            mot = st.selectbox("¿Por qué?", ["El residente la rechazó", "Estaba dormido / no despertó", "Vomitó",
                                             "No hay medicamento (agotado)", "Otro motivo"], key=f"nd_m_{k}")
            obs = st.text_input("Explique en pocas palabras", key=f"nd_o_{k}")
            if st.button("Guardar", key=f"nd_g_{k}", type="primary"):
                if not obs.strip():
                    st.error("Escriba una explicación.")
                else:
                    resul = "Rechazado por el residente" if mot.startswith("El residente") else "No administrado (otra causa)"
                    try:
                        N.registrar_dosis(d["Cedula"], d["ID_Med"], d["Hora"], resul, f"{mot}: {obs.strip()}", U.firma())
                        N.log(st.session_state.usuario, "NO_ADMINISTRA_MED", f"{d['Cedula']} · {d['Medicamento']} · {mot}")
                        U.flash("warn", f"Quedó anotado: {d['Medicamento']} no se dio ({mot}).")
                    except ValueError as e:
                        U.flash("warn", str(e))
                    st.rerun()


def pagina_medicamentos():
    U.banner(SEC, "Dar medicamentos", "Toque el botón verde cuando le dé la medicina. La hora exacta se guarda sola.")
    U.ayuda(["Busque la tarjeta de la hora que le toca.", "Dele la medicina al residente.",
             "Toque **✅ YA SE LA DI**. El sistema anota la hora real, quién la dio y el turno.",
             "Si no se pudo dar, toque **❌ No se pudo dar** y diga por qué."])
    puede_dar = U.rol() in PUEDE_DAR
    if not puede_dar:
        U.aviso("Usted puede ver la ronda, pero solo enfermería registra las dosis.", "info")
    modo = st.radio("¿A quién quiere ver?", ["👥 A todos", "👤 A uno solo"], horizontal=True, key="med_modo")
    ced = U.selector_residente("med") if modo.startswith("👤") else None
    dosis = N.dosis_hoy(ced)
    res = N.leer("residentes")
    alerg = dict(zip(res["Cedula"], res["Alergias"]))
    cuenta = {e: sum(1 for d in dosis if d["Estado"] == e) for e in ("Atrasado", "Ahora", "Pendiente", "Dado", "No dado")}
    c = st.columns(4)
    c[0].markdown(U.kpi(cuenta["Atrasado"], "🔴 Atrasadas", "crit" if cuenta["Atrasado"] else ""), unsafe_allow_html=True)
    c[1].markdown(U.kpi(cuenta["Ahora"], "🟡 Es la hora", "warn" if cuenta["Ahora"] else ""), unsafe_allow_html=True)
    c[2].markdown(U.kpi(cuenta["Pendiente"], "⏳ Más tarde"), unsafe_allow_html=True)
    c[3].markdown(U.kpi(cuenta["Dado"], "✅ Ya dadas"), unsafe_allow_html=True)
    filtro = st.radio("Mostrar", ["⏰ Las que faltan", "📋 Todas las de hoy", "✅ Las ya dadas"], horizontal=True, key="med_filtro")
    if filtro.startswith("⏰"):
        lista = [d for d in dosis if d["Estado"] in ("Atrasado", "Ahora", "Pendiente")]
        lista.sort(key=lambda d: ({"Atrasado": 0, "Ahora": 1, "Pendiente": 2}[d["Estado"]], d["Hora"]))
    elif filtro.startswith("✅"):
        lista = [d for d in dosis if d["Estado"] in ("Dado", "No dado")]
    else:
        lista = dosis
    if not dosis:
        st.info("No hay medicamentos con horario programado para hoy. Las horas se escriben en el **Kardex** (por ejemplo 08:00, 20:00).")
    elif not lista:
        U.aviso("🎉 ¡Todo al día! No hay medicinas pendientes en esta lista.", "ok")
    for d in lista[:80]:
        _fila_dosis(d, puede_dar, alerg)

    if puede_dar:
        with st.expander("➕ Dosis extra o «si es necesario»"):
            ced2 = U.selector_residente("prn")
            if ced2:
                kar = N.leer("kardex_meds")
                kar = kar[(kar["Cedula"] == ced2) & (kar["Estado"] == "Activo")]
                if kar.empty:
                    st.caption("Este residente no tiene medicinas activas.")
                else:
                    et = {r.ID_Med: f"{r.Medicamento} {r.Dosis} · {r.Via}" for r in kar.itertuples()}
                    v = U.ver("prn")
                    with st.form(f"form_prn_{v}"):
                        idm = st.selectbox("Medicina", list(et), format_func=lambda i: et[i], key=f"prn_m_{v}")
                        mot = st.text_input("¿Por qué se le da? (obligatorio)", key=f"prn_o_{v}")
                        if st.form_submit_button("✅ REGISTRAR DOSIS EXTRA", type="primary", **KW):
                            if not mot.strip():
                                st.error("Escriba el motivo.")
                            else:
                                N.registrar_dosis(ced2, idm, "", "Administrado", f"Dosis extra: {mot.strip()}", U.firma())
                                N.log(st.session_state.usuario, "DOSIS_EXTRA", f"{ced2} · {et[idm]} · {mot.strip()}")
                                U.flash("ok", f"✅ Dosis extra guardada: {et[idm]}.")
                                U.nueva_version("prn")
                                st.rerun()


# ══════════════════════════════════════════════════════════════
# SIGNOS VITALES
# ══════════════════════════════════════════════════════════════
def pagina_vitales():
    U.banner(SEC, "Signos vitales", "Anote la presión, el pulso, la temperatura… El sistema avisa si algo está mal.")
    ced = U.selector_residente("vit")
    if not ced:
        return
    U.ficha(ced)
    v = U.ver("vit")
    with st.form(f"form_vit_{v}"):
        st.markdown("##### Nuevo registro")
        c = st.columns(4)
        sis = c[0].number_input("TA sistólica (la alta)", min_value=40, max_value=260, value=120, step=1, key=f"v_s_{ced}_{v}")
        dia = c[1].number_input("TA diastólica (la baja)", min_value=20, max_value=160, value=80, step=1, key=f"v_d_{ced}_{v}")
        fc = c[2].number_input("Pulso (lpm)", min_value=20, max_value=220, value=76, step=1, key=f"v_fc_{ced}_{v}")
        fr = c[3].number_input("Respiraciones (rpm)", min_value=5, max_value=60, value=18, step=1, key=f"v_fr_{ced}_{v}")
        c = st.columns(4)
        temp = c[0].number_input("Temperatura (°C)", min_value=30.0, max_value=43.0, value=36.5, step=0.1, format="%.1f", key=f"v_t_{ced}_{v}")
        sat = c[1].number_input("Oxígeno SatO₂ (%)", min_value=50, max_value=100, value=95, step=1, key=f"v_o_{ced}_{v}")
        glu = c[2].number_input("Glucemia · 0 = no se midió", min_value=0, max_value=600, value=0, step=1, key=f"v_g_{ced}_{v}")
        dolor = c[3].number_input("Dolor (0 a 10)", min_value=0, max_value=10, value=0, step=1, key=f"v_p_{ced}_{v}")
        peso = st.number_input("Peso (kg) · 0 = no se midió", min_value=0.0, max_value=250.0, value=0.0, step=0.1, format="%.1f", key=f"v_w_{ced}_{v}")
        if st.form_submit_button("💾 GUARDAR SIGNOS VITALES", type="primary", **KW):
            if sis <= dia:
                st.error("La presión alta (sistólica) debe ser mayor que la baja (diastólica).")
            else:
                al = N.evaluar_signos(sis, dia, fc, fr, temp, sat, glu, dolor)
                texto = "; ".join(("🔴 " if n == "crit" else "🟡 ") + t for t, n in al)
                N.agregar("signos_vitales", {
                    "ID": N.nueva_id("SV"), "Cedula": ced, "Fecha_Hora": N.fmt_fh(), "TA_Sis": sis, "TA_Dia": dia, "FC": fc,
                    "FR": fr, "Temp": temp, "SatO2": sat, "Glucemia": glu or "", "Dolor": dolor, "Peso": peso or "",
                    "Alertas": texto, "Autor": U.firma()})
                N.log(st.session_state.usuario, "SIGNOS_VITALES", f"{ced} · {texto or 'sin alertas'}")
                U.flash("warn" if al else "ok", "⚠️ Guardado con alertas: " + texto if al else "✅ Signos vitales guardados. Todo normal.")
                U.nueva_version("vit")
                st.rerun()
    vit = N.leer("signos_vitales")
    hist = vit[vit["Cedula"] == ced].sort_values("Fecha_Hora", ascending=False)
    st.markdown("##### 📜 Historial")
    if hist.empty:
        st.caption("Este residente aún no tiene registros.")
        return
    U.tabla(hist[["Fecha_Hora", "TA_Sis", "TA_Dia", "FC", "FR", "Temp", "SatO2", "Glucemia", "Dolor", "Peso", "Alertas", "Autor"]].head(40))
    g = hist.head(30).sort_values("Fecha_Hora").set_index("Fecha_Hora")[["TA_Sis", "TA_Dia", "FC"]].apply(pd.to_numeric, errors="coerce")
    if len(g) >= 2:
        st.markdown("##### 📈 Tendencia (últimos 30 registros)")
        st.line_chart(g)


# ══════════════════════════════════════════════════════════════
# NOTAS SOAPIE (con hora de inicio y de fin, inalterables)
# ══════════════════════════════════════════════════════════════
def pagina_soapie():
    U.banner(SEC, "Notas de enfermería", "Se escribe una sola vez: queda firmada con hora de inicio y de fin. No se puede borrar ni cambiar.")
    ced = U.selector_residente("soap", solo_activos=False)
    if not ced:
        return
    r = U.ficha(ced)
    t1, t2 = st.tabs(["✍️ Hacer nota", "📚 Notas anteriores"])
    inicios = st.session_state.setdefault("nota_inicio", {})
    with t1:
        if r["Estado"] == "Egresado":
            st.warning("Este residente está egresado; no se pueden agregar notas nuevas.")
        elif ced not in inicios:
            U.ayuda(["Toque **📝 HACER NOTA**: el sistema anota la hora exacta en que empieza a escribir.",
                     "Llene los cuadros con datos claros: qué dijo, qué vio, qué hizo.",
                     "Marque la casilla de confirmación y toque **FIRMAR**. La hora de fin se guarda sola."])
            st.markdown("Para escribir una nota primero debe iniciarla. Así queda registrada la hora real en que empezó, como lo exige la norma.")
            if st.button("📝 HACER NOTA", type="primary", key=f"ini_nota_{ced}", **KW):
                inicios[ced] = N.fmt_fh()
                N.log(st.session_state.usuario, "INICIA_NOTA", f"{ced} · {inicios[ced]}")
                st.rerun()
        else:
            U.aviso(f"🕒 Nota iniciada el {inicios[ced][:10]} a las {inicios[ced][11:]}. Termínela y fírmela.", "info")
            v = U.ver("soap")
            with st.form(f"form_soap_{v}"):
                turno = st.selectbox("Turno", N.TURNOS, index=N.TURNOS.index(N.turno_de()), key=f"so_t_{ced}_{v}")
                s = st.text_area("S · Subjetivo — Lo que dice o siente el residente o su familia", key=f"so_s_{ced}_{v}", height=90,
                                 placeholder="Ej: «Refiere dolor en rodilla derecha desde anoche, 6 de 10; no durmió bien».")
                o = st.text_area("O · Objetivo — Lo que usted ve, mide y examina", key=f"so_o_{ced}_{v}", height=90,
                                 placeholder="Ej: Rodilla derecha inflamada, sin enrojecimiento. TA 130/80, pulso 78, temp 36.6 °C. Camina con bastón.")
                a = st.text_area("A · Análisis — Su conclusión como enfermero/a", key=f"so_a_{ced}_{v}", height=80,
                                 placeholder="Ej: Dolor osteoarticular que limita la marcha, riesgo de caída.")
                p = st.text_area("P · Plan — Qué se va a hacer", key=f"so_p_{ced}_{v}", height=80,
                                 placeholder="Ej: Vigilar la marcha, aplicar compresa tibia, avisar al médico si el dolor sube.")
                i = st.text_area("I · Intervención — Lo que YA se hizo", key=f"so_i_{ced}_{v}", height=90,
                                 placeholder="Ej: A las 08:10 se aplicó compresa tibia 15 min y se dio el analgésico formulado.")
                e = st.text_area("E · Evaluación — Cómo respondió", key=f"so_e_{ced}_{v}", height=80,
                                 placeholder="Ej: A las 09:00 refiere dolor 3 de 10, descansa tranquilo.")
                conf = st.checkbox("Confirmo que leí mi nota. Entiendo que al firmar NO se podrá cambiar ni borrar.", key=f"so_c_{ced}_{v}")
                b1, b2 = st.columns([3, 1])
                firmar = b1.form_submit_button("🔏 FIRMAR Y GUARDAR NOTA", type="primary", **KW)
                cancelar = b2.form_submit_button("Cancelar nota", **KW)
            if cancelar:
                N.log(st.session_state.usuario, "CANCELA_NOTA", f"{ced} · iniciada {inicios.get(ced)}")
                inicios.pop(ced, None)
                U.nueva_version("soap")
                st.rerun()
            if firmar:
                cortos = [n for n, t in (("Subjetivo", s), ("Objetivo", o), ("Intervención", i), ("Evaluación", e)) if len(t.strip()) < 15]
                if cortos:
                    st.error("Escriba con más detalle (mínimo una frase completa) en: " + ", ".join(cortos) + ".")
                elif not conf:
                    st.error("Marque la casilla de confirmación para poder firmar.")
                else:
                    fin = N.fmt_fh()
                    nota = {"ID_Nota": N.nueva_id("SOAPIE"), "Cedula": ced, "Fecha_Hora": fin, "Turno": turno, "Autor": U.firma(),
                            "Subjetivo": s.strip(), "Objetivo": o.strip(), "Analisis": a.strip(), "Plan": p.strip(),
                            "Intervencion": i.strip(), "Evaluacion": e.strip(), "Hora_Inicio": inicios[ced]}
                    nota["Sello"] = N.sello_nota(nota)
                    N.agregar("notas_soapie", nota)
                    N.log(st.session_state.usuario, "NOTA_SOAPIE", f"{ced} · {nota['ID_Nota']} · {inicios[ced]} → {fin}")
                    inicios.pop(ced, None)
                    U.flash("ok", f"✅ Nota {nota['ID_Nota']} firmada. Inicio {nota['Hora_Inicio'][11:]} · Fin {fin[11:]}.")
                    U.nueva_version("soap")
                    st.rerun()
    with t2:
        sop = N.leer("notas_soapie")
        sop = sop[sop["Cedula"] == ced].sort_values("Fecha_Hora", ascending=False)
        if sop.empty:
            st.caption("Este residente aún no tiene notas.")
            return
        st.download_button("⬇️ Descargar notas (CSV)", N.csv_seguro(sop.drop(columns=["Cedula"])), file_name=f"soapie_{ced}.csv",
                           mime="text/csv", key=f"dl_{ced}")
        for n in sop.head(30).to_dict("records"):
            integra = N.sello_nota(n) == n["Sello"]
            ini = n.get("Hora_Inicio", "")
            tiempo = f"{ini[11:]} → {n['Fecha_Hora'][11:]}" if ini else n["Fecha_Hora"][11:]
            with st.expander(f"📝 {n['Fecha_Hora'][:10]} · {tiempo} · {n['Turno'].split(' (')[0]} · {n['Autor']}"):
                st.markdown(chip("Sello íntegro ✓", "ok") if integra else chip("⚠ El contenido no coincide con el sello", "crit"), unsafe_allow_html=True)
                for etiqueta, campo in [("S · Subjetivo", "Subjetivo"), ("O · Objetivo", "Objetivo"), ("A · Análisis", "Analisis"),
                                        ("P · Plan", "Plan"), ("I · Intervención", "Intervencion"), ("E · Evaluación", "Evaluacion")]:
                    if n[campo].strip():
                        st.markdown(f"**{etiqueta}**")
                        st.text(n[campo])
                st.caption(f"ID {n['ID_Nota']} · Inicio {ini or '—'} · Fin {n['Fecha_Hora']} · Sello {n['Sello']}")


# ══════════════════════════════════════════════════════════════
# KARDEX Y STOCK DE MEDICINAS
# ══════════════════════════════════════════════════════════════
def pagina_kardex():
    U.banner(SEC, "Kardex y medicinas", "Qué medicinas toma cada residente y cuántas tiene guardadas.")
    ced = U.selector_residente("kar")
    if not ced:
        return
    r = U.ficha(ced)
    meds = N.leer("kardex_meds")
    mr = meds[meds["Cedula"] == ced]
    act = mr[mr["Estado"] == "Activo"]
    etq = {x.ID_Med: f"{x.Medicamento} {x.Dosis} · {x.Via} · {x.Frecuencia}" for x in act.itertuples()}
    puede_recetar = U.rol() in (N.R_ADMIN, N.R_ENF, N.R_MED)

    t1, t2, t3, t4 = st.tabs(["💊 Medicinas que toma", "📦 Llegada y stock", "➕ Agregar / suspender", "🗂 Historial"])
    with t1:
        if act.empty:
            st.info("Este residente no tiene medicinas activas. Agregue una en «Agregar / suspender».")
        else:
            U.tabla(act[["Medicamento", "Dosis", "Via", "Frecuencia", "Horarios", "Unidades_Dosis", "Indicaciones", "Prescrito_Por"]])
            st.caption("Para dar las medicinas use **💊 Dar medicamentos** en el menú.")
    with t2:
        stk = N.stock_meds(ced)
        st.markdown("##### 📦 Medicinas guardadas de este residente")
        if stk.empty:
            st.caption("Todavía no se ha registrado la llegada de medicinas.")
        else:
            ic = {"ok": "🟢", "warn": "🟡", "crit": "🔴"}
            U.tabla(pd.DataFrame({"": [ic[n] for n in stk["Nivel"]], "Medicina": stk["Medicamento"], "Quedan": stk["Stock"],
                                  "Se gastan por día": stk["Dosis_Dia"], "Alcanzan (días)": stk["Dias"].fillna("—")}))
            for x in stk[stk["Nivel"] != "ok"].to_dict("records"):
                U.aviso(f"{'🔴 SE ACABA' if x['Nivel'] == 'crit' else '🟡 POCAS'}: {x['Medicamento']} — quedan {x['Stock']:g} (alcanzan {x['Dias'] if x['Dias'] is not None else '?'} días). Avise a la familia.", x["Nivel"])
        if act.empty:
            st.info("Primero agregue la medicina en «Agregar / suspender» y luego registre aquí cuántas llegaron.")
        else:
            st.markdown("##### ➕ Registrar lo que llegó")
            U.ayuda(["En la tabla toque una fila y elija la medicina.", "Escriba cuántas unidades llegaron (pastillas, ampollas, frascos…).",
                     "Si llegaron varias medicinas a la vez, agregue una fila por cada una (toque el + de la tabla).", "Toque **Guardar llegada**."])
            v = U.ver("stk")
            nombres = sorted(set(act["Medicamento"].str.strip()))
            ed = st.data_editor(pd.DataFrame({"Medicina": [nombres[0]], "Cantidad": [0.0], "Nota": [""]}), num_rows="dynamic", key=f"ed_stk_{ced}_{v}",
                                column_config={"Medicina": st.column_config.SelectboxColumn(options=nombres, required=True),
                                               "Cantidad": st.column_config.NumberColumn(min_value=0.0, step=1.0, required=True),
                                               "Nota": st.column_config.TextColumn("Nota (ej. caja x30, la trajo la hija)")}, **KW)
            foto = None
            with st.expander("📷 Foto de la caja o de la fórmula (opcional)"):
                foto = U.capturar_foto(f"stk_{ced}_{v}", "Foto de la medicina")
            if st.button("💾 GUARDAR LLEGADA", type="primary", key=f"gs_{ced}_{v}", **KW):
                filas = [x for x in ed.to_dict("records") if x.get("Medicina") and N._num(x.get("Cantidad")) > 0]
                if not filas:
                    st.error("Escriba al menos una medicina con su cantidad.")
                else:
                    for x in filas:
                        N.agregar("mov_meds", {"ID": N.nueva_id("MV"), "Cedula": ced, "Medicamento": x["Medicina"], "Tipo": "Ingreso",
                                               "Cantidad": N._num(x["Cantidad"]), "Fecha_Hora": N.fmt_fh(), "Autor": U.firma(), "Nota": x.get("Nota") or ""})
                    resumen = "; ".join(f"{x['Medicina']} x{N._num(x['Cantidad']):g}" for x in filas)
                    N.log(st.session_state.usuario, "LLEGADA_MEDICINA", f"{ced} · {resumen}")
                    if foto:
                        try:
                            N.guardar_archivo(U.cfg(), ced, r["Nombre"], "Medicamentos", f"llegada_{N.hoy().isoformat()}.jpg",
                                              D.procesar_imagen(foto), "image/jpeg", U.firma())
                        except (ValueError, N.ErrorNube) as e:
                            st.warning(f"Las medicinas se guardaron, pero la foto no: {e}")
                    U.flash("ok", f"✅ Llegada registrada: {resumen}")
                    U.nueva_version("stk")
                    st.rerun()
            with st.expander("🔧 Corregir existencias (se perdió, venció, se devolvió a la familia…)"):
                with st.form(f"form_aj_{ced}"):
                    idn = st.selectbox("Medicina", nombres, key=f"aj_m_{ced}")
                    signo = st.radio("¿Qué pasó?", ["➖ Salió o se perdió", "➕ Se encontró / corrección a favor"], horizontal=True, key=f"aj_s_{ced}")
                    cant = st.number_input("Cantidad", min_value=0.0, step=1.0, key=f"aj_c_{ced}")
                    mot = st.text_input("Motivo (obligatorio)", key=f"aj_o_{ced}")
                    if st.form_submit_button("Guardar corrección", **KW):
                        if cant <= 0 or not mot.strip():
                            st.error("Escriba la cantidad y el motivo.")
                        else:
                            N.agregar("mov_meds", {"ID": N.nueva_id("MV"), "Cedula": ced, "Medicamento": idn, "Tipo": "Ajuste",
                                                   "Cantidad": cant if signo.startswith("➕") else -cant, "Fecha_Hora": N.fmt_fh(),
                                                   "Autor": U.firma(), "Nota": mot.strip()})
                            N.log(st.session_state.usuario, "AJUSTA_STOCK", f"{ced} · {idn} · {signo[:1]}{cant:g} · {mot.strip()}")
                            U.flash("ok", "✅ Corrección guardada.")
                            st.rerun()
    with t3:
        if not puede_recetar:
            U.aviso("Solo médico, enfermería y administración pueden agregar o suspender medicinas.", "info")
        else:
            v = U.ver("med")
            with st.form(f"form_med_{v}"):
                st.markdown("##### ➕ Nueva medicina")
                a, b, c = st.columns(3)
                med = a.text_input("Nombre de la medicina", key=f"m_n_{ced}_{v}")
                dosis = b.text_input("Dosis (ej: 500 mg)", key=f"m_d_{ced}_{v}")
                via = c.selectbox("Vía", ["Oral", "Sublingual", "Intramuscular", "Intravenosa", "Subcutánea", "Tópica", "Inhalada", "Oftálmica", "Rectal"], key=f"m_v_{ced}_{v}")
                a, b, c = st.columns(3)
                frec = a.selectbox("Frecuencia", ["Cada 4 h", "Cada 6 h", "Cada 8 h", "Cada 12 h", "Cada 24 h", "Dosis única", "Si es necesario (PRN)"], key=f"m_f_{ced}_{v}")
                hor = b.text_input("Horas (ej: 08:00, 20:00)", key=f"m_h_{ced}_{v}", help="Estas horas son las que aparecen en «Dar medicamentos».")
                uds = c.number_input("Unidades por dosis", min_value=0.25, value=1.0, step=0.25, key=f"m_u_{ced}_{v}",
                                     help="Cuántas pastillas / ampollas se dan cada vez. Sirve para descontar del stock.")
                ind = st.text_area("Indicaciones (con comida, en ayunas…)", key=f"m_i_{ced}_{v}", height=70)
                if st.form_submit_button("💾 GUARDAR MEDICINA", type="primary", **KW):
                    horas = N.horarios_lista(hor)
                    if not med.strip() or not dosis.strip():
                        st.error("Escriba el nombre y la dosis.")
                    elif frec not in ("Dosis única", "Si es necesario (PRN)") and not horas:
                        st.error("Escriba al menos una hora con este formato: 08:00  (si son varias, sepárelas con coma).")
                    else:
                        N.agregar("kardex_meds", {"ID_Med": N.nueva_id("MD"), "Cedula": ced, "Medicamento": med.strip(), "Dosis": dosis.strip(),
                                                  "Via": via, "Frecuencia": frec, "Horarios": ", ".join(horas), "Indicaciones": ind.strip(),
                                                  "Estado": "Activo", "Prescrito_Por": U.quien(), "F_Inicio": N.hoy().isoformat(),
                                                  "Unidades_Dosis": uds})
                        N.log(st.session_state.usuario, "PRESCRIBE", f"{ced} · {med.strip()} {dosis.strip()}")
                        U.flash("ok", f"✅ {med.strip()} agregada al kardex.")
                        U.nueva_version("med")
                        st.rerun()
            if not act.empty:
                v2 = U.ver("susp")
                with st.form(f"form_susp_{v2}"):
                    st.markdown("##### ⏹ Suspender una medicina")
                    idm = st.selectbox("¿Cuál se suspende?", list(etq), format_func=lambda i: etq[i], key=f"s_m_{ced}_{v2}")
                    if st.form_submit_button("Suspender", **KW):
                        N.actualizar("kardex_meds", "ID_Med", idm, {"Estado": "Suspendido", "F_Suspension": N.hoy().isoformat()})
                        N.log(st.session_state.usuario, "SUSPENDE_MED", f"{ced} · {etq[idm]}")
                        U.flash("ok", f"Suspendida: {etq[idm]}")
                        U.nueva_version("susp")
                        st.rerun()
    with t4:
        ad = N.leer("admin_meds")
        ad = ad[ad["Cedula"] == ced].sort_values("Fecha_Hora", ascending=False)
        if ad.empty:
            st.caption("Aún no hay medicinas dadas.")
        else:
            nombres_m = mr.set_index("ID_Med")["Medicamento"].to_dict()
            ad = ad.assign(Medicamento=ad["ID_Med"].map(nombres_m).fillna("—"))
            U.tabla(ad[["Fecha_Hora", "Hora_Programada", "Medicamento", "Resultado", "Turno", "Minutos_Desvio", "Observacion", "Autor"]].head(80))
        susp = mr[mr["Estado"] != "Activo"]
        if not susp.empty:
            st.markdown("##### Medicinas suspendidas")
            U.tabla(susp[["Medicamento", "Dosis", "Frecuencia", "F_Inicio", "F_Suspension"]])


# ══════════════════════════════════════════════════════════════
# PERTENENCIAS Y ASEO PERSONAL
# ══════════════════════════════════════════════════════════════
TIPOS_PERT = ["👕 Ropa / prenda", "⌚ Objeto de valor (reloj, joyas)", "👓 Gafas / audífonos / prótesis", "📄 Documento", "📱 Aparato electrónico", "🧸 Otro"]
ESTADOS_PERT = ["En custodia", "Salió con el residente", "Entregada a la familia", "Dañada o perdida", "Faltante al regreso"]
ARTICULOS_ASEO = ["Shampoo", "Jabón de baño", "Cepillo de dientes", "Crema dental", "Desodorante", "Crema corporal", "Peine / cepillo",
                  "Pañales", "Toallas húmedas", "Papel higiénico", "Afeitadora", "Colonia", "Otro"]
CHIP_PERT = {"En custodia": "ok", "Salió con el residente": "info", "Entregada a la familia": "warn", "Dañada o perdida": "crit", "Faltante al regreso": "crit"}


def pagina_pertenencias():
    U.banner(SEC, "Pertenencias y aseo personal", "Qué trae cada residente: ropa, objetos de valor y artículos de aseo.")
    ced = U.selector_residente("per", solo_activos=False)
    if not ced:
        return
    r = U.ficha(ced)
    t1, t2 = st.tabs(["🎒 Ropa y objetos", "🧴 Aseo personal"])
    with t1:
        U.ayuda(["Toque **📷 Tomar foto** y fotografíe la prenda u objeto (o elija una foto de la galería).", "Escriba qué es y cuántos hay.",
                 "Toque **Guardar**. La foto queda en la carpeta del residente."])
        v = U.ver("pert")
        with st.form(f"form_pert_{v}"):
            a, b, c = st.columns([2, 1, 3])
            tipo = a.selectbox("¿Qué es?", TIPOS_PERT, key=f"pt_t_{ced}_{v}")
            cant = b.number_input("Cantidad", min_value=1, value=1, step=1, key=f"pt_c_{ced}_{v}")
            desc = c.text_input("Descripción (color, marca, estado)", key=f"pt_d_{ced}_{v}", placeholder="Ej: Reloj Casio negro con correa de cuero, rayado")
            foto = U.capturar_foto(f"pert_{ced}_{v}", "Foto de la pertenencia")
            if st.form_submit_button("💾 GUARDAR PERTENENCIA", type="primary", **KW):
                if len(desc.strip()) < 4:
                    st.error("Escriba una descripción.")
                else:
                    aid = ""
                    try:
                        if foto:
                            aid = N.guardar_archivo(U.cfg(), ced, r["Nombre"], "Pertenencias", f"{tipo[2:12]}_{N.hoy().isoformat()}.jpg",
                                                    D.procesar_imagen(foto), "image/jpeg", U.firma())["ID"]
                        N.agregar("pertenencias", {"ID": N.nueva_id("PT"), "Cedula": ced, "Fecha_Hora": N.fmt_fh(), "Tipo": tipo, "Descripcion": desc.strip(),
                                                   "Cantidad": cant, "Estado": "En custodia", "Archivo_ID": aid, "Autor": U.firma()})
                        N.log(st.session_state.usuario, "INGRESA_PERTENENCIA", f"{ced} · {tipo} · {desc.strip()}")
                        U.flash("ok", "✅ Pertenencia registrada.")
                        U.nueva_version("pert")
                        st.rerun()
                    except (ValueError, N.ErrorNube) as e:
                        st.error(str(e))
        pt = N.leer("pertenencias")
        pt = pt[pt["Cedula"] == ced].sort_values("Fecha_Hora", ascending=False)
        st.markdown("##### 🗃 Lo que tiene este residente")
        if pt.empty:
            st.caption("Aún no hay pertenencias registradas.")
        else:
            fe = st.radio("Mostrar", ["Todas", *ESTADOS_PERT], horizontal=True, key=f"pt_f_{ced}")
            if fe != "Todas":
                pt = pt[pt["Estado"] == fe]
            lim = st.session_state.get("pt_lim", 12)
            for i, x in enumerate(pt.head(lim).to_dict("records")):
                c1, c2 = st.columns([1, 3])
                with c1:
                    datos, _ = U.bytes_de(x["Archivo_ID"]) if x["Archivo_ID"] else (None, None)
                    if datos:
                        st.image(datos, width=150)
                    else:
                        st.markdown(f"<div style='font-size:3rem;text-align:center'>{x['Tipo'][:2]}</div>", unsafe_allow_html=True)
                with c2:
                    st.markdown(U.bloque(f"<div style='font-weight:800;font-size:1.05rem'>{h(x['Tipo'])} · x{h(x['Cantidad'])}</div>"
                                         f"<div>{h(x['Descripcion'])}</div><div style='color:#55657C;font-size:.85rem'>Registró {h(x['Autor'])} · {h(x['Fecha_Hora'][:16])}</div>"
                                         f"{chip(x['Estado'], CHIP_PERT.get(x['Estado'], 'ok'))}"), unsafe_allow_html=True)
                    with st.expander("Cambiar estado"):
                        nuevo = st.selectbox("Nuevo estado", ESTADOS_PERT, index=ESTADOS_PERT.index(x["Estado"]) if x["Estado"] in ESTADOS_PERT else 0, key=f"pt_e_{x['ID']}")
                        mot = st.text_input("Motivo (obligatorio)", key=f"pt_m_{x['ID']}")
                        if st.button("Guardar estado", key=f"pt_g_{x['ID']}"):
                            if not mot.strip() or nuevo == x["Estado"]:
                                st.error("Elija un estado distinto y escriba el motivo.")
                            else:
                                N.actualizar("pertenencias", "ID", x["ID"], {"Estado": nuevo})
                                N.log(st.session_state.usuario, "CAMBIA_ESTADO_PERTENENCIA",
                                      f"{ced} · {x['ID']} · {x['Descripcion']} · {x['Estado']} → {nuevo} · {mot.strip()}")
                                U.flash("ok", "✅ Estado actualizado (queda en la auditoría).")
                                st.rerun()
                st.divider()
            if len(pt) > lim and st.button("Ver más", key="pt_mas"):
                st.session_state["pt_lim"] = lim + 12
                st.rerun()
    with t2:
        U.ayuda(["En **Ingreso** anote lo que trae el residente (shampoo, jabón…) o lo que compró/trajo la familia.",
                 "En **Se usó** anote cuando se gasta o se termina algo.", "La tabla le dice cuánto le queda."])
        ma = N.leer("aseo_personal")
        ma = ma[ma["Cedula"] == ced]
        if not ma.empty:
            ma = ma.assign(_v=[(-1 if t == "Consumo" else 1) * N._num(c) for t, c in zip(ma["Tipo"], ma["Cantidad"])])
            g = ma.groupby("Articulo").agg(Quedan=("_v", "sum"), Ultimo=("Fecha_Hora", "max")).reset_index()
            g.insert(0, "", ["🔴" if q <= 0 else "🟡" if q <= 1 else "🟢" for q in g["Quedan"]])
            U.tabla(g.rename(columns={"Articulo": "Artículo", "Ultimo": "Último movimiento"}))
            for x in g[g["Quedan"] <= 1].to_dict("records"):
                U.aviso(f"{'🔴 SE ACABÓ' if x['Quedan'] <= 0 else '🟡 POCO'}: {x['Articulo']} de {r['Nombre']}. Avise a la familia o compre.", "crit" if x["Quedan"] <= 0 else "warn")
        else:
            st.caption("Aún no hay artículos de aseo registrados.")
        a, b = st.columns(2)
        with a:
            v = U.ver("aseo_i")
            with st.form(f"form_aseo_i_{v}"):
                st.markdown("##### ➕ Ingreso")
                art = st.selectbox("Artículo", ARTICULOS_ASEO, key=f"as_a_{ced}_{v}")
                otro = st.text_input("Si eligió «Otro», ¿cuál?", key=f"as_o_{ced}_{v}")
                cant = st.number_input("Cantidad", min_value=1, value=1, step=1, key=f"as_c_{ced}_{v}")
                orig = st.radio("¿De dónde salió?", ["Ingreso inicial", "Compra del geriátrico", "Lo trajo la familia"], key=f"as_r_{ced}_{v}")
                nota = st.text_input("Nota (opcional)", key=f"as_n_{ced}_{v}")
                if st.form_submit_button("💾 GUARDAR INGRESO", type="primary", **KW):
                    nombre = otro.strip() if art == "Otro" else art
                    if not nombre:
                        st.error("Escriba qué artículo es.")
                    else:
                        N.agregar("aseo_personal", {"ID": N.nueva_id("AP"), "Cedula": ced, "Fecha_Hora": N.fmt_fh(), "Articulo": nombre, "Tipo": "Ingreso",
                                                    "Cantidad": cant, "Origen": orig, "Autor": U.firma(), "Nota": nota.strip()})
                        N.log(st.session_state.usuario, "INGRESA_ASEO_PERSONAL", f"{ced} · {nombre} x{cant} · {orig}")
                        U.flash("ok", f"✅ {nombre} registrado.")
                        U.nueva_version("aseo_i")
                        st.rerun()
        with b:
            arts = sorted(set(ma["Articulo"])) if not ma.empty else []
            v = U.ver("aseo_c")
            with st.form(f"form_aseo_c_{v}"):
                st.markdown("##### ➖ Se usó o se terminó")
                if not arts:
                    st.caption("Primero registre un ingreso.")
                art = st.selectbox("Artículo", arts or ["—"], key=f"asc_a_{ced}_{v}")
                cant = st.number_input("¿Cuánto se gastó?", min_value=1, value=1, step=1, key=f"asc_c_{ced}_{v}")
                if st.form_submit_button("Guardar consumo", **KW) and arts:
                    N.agregar("aseo_personal", {"ID": N.nueva_id("AP"), "Cedula": ced, "Fecha_Hora": N.fmt_fh(), "Articulo": art, "Tipo": "Consumo",
                                                "Cantidad": cant, "Origen": "", "Autor": U.firma(), "Nota": ""})
                    N.log(st.session_state.usuario, "CONSUMO_ASEO_PERSONAL", f"{ced} · {art} x{cant}")
                    U.flash("ok", f"✅ Consumo de {art} guardado.")
                    U.nueva_version("aseo_c")
                    st.rerun()


# ══════════════════════════════════════════════════════════════
# SALIDAS Y REGRESOS
# ══════════════════════════════════════════════════════════════
def _items_texto(js):
    try:
        d = json.loads(js) if js else {}
    except ValueError:
        d = {}
    out = list(d.get("labels", []))
    if d.get("extra"):
        out.append(f"Puesto/llevado: {d['extra']}")
    return out, d


def pagina_salidas():
    U.banner(SEC, "Salidas y regresos", "Anote con qué sale cada residente y con qué regresa. Así nadie reclama lo que no llevó.")
    ced = U.selector_residente("sal")
    if not ced:
        return
    r = U.ficha(ced)
    sal = N.leer("salidas")
    sal_r = sal[sal["Cedula"] == ced].sort_values("F_Salida", ascending=False)
    abierta = sal_r[sal_r["Estado"] == "En salida"]
    t1, t2, t3 = st.tabs(["🚪 Va a salir", "↩️ Ya regresó", "📚 Historial y acta"])

    with t1:
        if not abierta.empty:
            U.aviso(f"Este residente ya está FUERA desde {abierta.iloc[0]['F_Salida'][:16]}. Registre su regreso en la otra pestaña.", "warn")
        else:
            pt = N.leer("pertenencias")
            pt = pt[(pt["Cedula"] == ced) & (pt["Estado"] == "En custodia")]
            op = {x.ID: f"{x.Tipo} · {x.Descripcion} (x{x.Cantidad})" for x in pt.itertuples()}
            v = U.ver("sal")
            with st.form(f"form_sal_{v}"):
                a, b = st.columns(2)
                motivo = a.selectbox("¿Por qué sale?", ["Visita familiar", "Cita médica", "Paseo", "Hospital / urgencias", "Trámite", "Otro"], key=f"sa_m_{ced}_{v}")
                destino = b.text_input("¿A dónde va?", key=f"sa_d_{ced}_{v}")
                acomp = st.text_input("¿Con quién sale? (nombre y parentesco)", key=f"sa_a_{ced}_{v}", placeholder="Ej: Marta Pérez, hija")
                lleva = st.multiselect("Objetos guardados que SE LLEVA", list(op), format_func=lambda i: op[i], key=f"sa_l_{ced}_{v}")
                extra = st.text_input("Lo que lleva puesto o consigo (reloj, anillo, gafas, bastón, dinero…)", key=f"sa_e_{ced}_{v}")
                foto = U.capturar_foto(f"sal_{ced}_{v}", "Foto al salir (opcional)")
                if st.form_submit_button("🚪 REGISTRAR SALIDA", type="primary", **KW):
                    if not destino.strip() or not acomp.strip():
                        st.error("Escriba a dónde va y con quién sale.")
                    else:
                        try:
                            aid = ""
                            if foto:
                                aid = N.guardar_archivo(U.cfg(), ced, r["Nombre"], "Salidas", f"salida_{N.hoy().isoformat()}.jpg",
                                                        D.procesar_imagen(foto), "image/jpeg", U.firma())["ID"]
                            items = {"ids": lleva, "labels": [op[i] for i in lleva], "extra": extra.strip(), "foto": aid}
                            N.agregar("salidas", {"ID": N.nueva_id("SL"), "Cedula": ced, "F_Salida": N.fmt_fh(), "Motivo": motivo, "Destino": destino.strip(),
                                                  "Acompanante": acomp.strip(), "Items_Salida": json.dumps(items, ensure_ascii=False),
                                                  "Autor_Salida": U.firma(), "Estado": "En salida"})
                            for i in lleva:
                                N.actualizar("pertenencias", "ID", i, {"Estado": "Salió con el residente"})
                            N.log(st.session_state.usuario, "SALIDA_RESIDENTE", f"{ced} · {motivo} · {destino.strip()} · lleva: {len(lleva)} objetos + «{extra.strip()}»")
                            U.flash("ok", f"✅ Salida registrada a las {N.ahora().strftime('%H:%M')}.")
                            U.nueva_version("sal")
                            st.rerun()
                        except (ValueError, N.ErrorNube) as e:
                            st.error(str(e))

    with t2:
        if abierta.empty:
            st.info("Este residente no está en salida.")
        else:
            s0 = abierta.iloc[0].to_dict()
            labels, d0 = _items_texto(s0["Items_Salida"])
            st.markdown(f"**Salió:** {s0['F_Salida'][:16]} · **Motivo:** {s0['Motivo']} · **Destino:** {s0['Destino']} · **Con:** {s0['Acompanante']}")
            v = U.ver("reg")
            with st.form(f"form_reg_{v}"):
                st.markdown("##### ✅ Marque lo que SÍ regresó con el residente")
                vueltos = {}
                for i, lab in zip(d0.get("ids", []), d0.get("labels", [])):
                    vueltos[i] = st.checkbox(lab, key=f"rg_{s0['ID']}_{i}_{v}")
                extra_s = d0.get("extra", "")
                ok_extra = True
                if extra_s:
                    ok_extra = st.checkbox(f"Lo que llevaba puesto: {extra_s}", key=f"rg_ex_{s0['ID']}_{v}")
                regresa_con = st.text_area("¿Con qué regresó además? (objetos nuevos, bolsas, medicinas…)", key=f"rg_c_{s0['ID']}_{v}", height=70)
                obs = st.text_area("Observaciones (estado del residente, novedades)", key=f"rg_o_{s0['ID']}_{v}", height=70)
                foto = U.capturar_foto(f"reg_{s0['ID']}_{v}", "Foto al regresar (opcional)")
                if st.form_submit_button("↩️ REGISTRAR REGRESO", type="primary", **KW):
                    faltan = [lab for i, lab in zip(d0.get("ids", []), d0.get("labels", [])) if not vueltos.get(i)]
                    if extra_s and not ok_extra:
                        faltan.append(f"Puesto/llevado: {extra_s}")
                    try:
                        aid = ""
                        if foto:
                            aid = N.guardar_archivo(U.cfg(), ced, r["Nombre"], "Salidas", f"regreso_{N.hoy().isoformat()}.jpg",
                                                    D.procesar_imagen(foto), "image/jpeg", U.firma())["ID"]
                        ret = {"vueltos": [i for i, ok in vueltos.items() if ok], "con": regresa_con.strip(), "foto": aid}
                        N.actualizar("salidas", "ID", s0["ID"], {"Estado": "Regresó", "F_Retorno": N.fmt_fh(), "Items_Retorno": json.dumps(ret, ensure_ascii=False),
                                                                 "Observacion_Retorno": obs.strip(), "Autor_Retorno": U.firma(), "Faltantes": "; ".join(faltan)})
                        for i in d0.get("ids", []):
                            N.actualizar("pertenencias", "ID", i, {"Estado": "En custodia" if vueltos.get(i) else "Faltante al regreso"})
                        N.log(st.session_state.usuario, "REGRESO_RESIDENTE", f"{ced} · faltantes: {'; '.join(faltan) or 'ninguno'}")
                        U.flash("warn" if faltan else "ok", ("⚠ Regreso registrado. NO regresó: " + "; ".join(faltan)) if faltan else "✅ Regreso registrado. Todo regresó completo.")
                        U.nueva_version("reg")
                        st.rerun()
                    except (ValueError, N.ErrorNube) as e:
                        st.error(str(e))

    with t3:
        if sal_r.empty:
            st.caption("Este residente no tiene salidas registradas.")
        else:
            U.tabla(sal_r[["F_Salida", "Motivo", "Destino", "Acompanante", "Estado", "F_Retorno", "Faltantes", "Autor_Salida", "Autor_Retorno"]])
            ids = sal_r["ID"].tolist()
            sel = st.selectbox("Acta de una salida", ids, format_func=lambda i: f"{sal_r[sal_r['ID'] == i].iloc[0]['F_Salida'][:16]} · {sal_r[sal_r['ID'] == i].iloc[0]['Destino']}", key="sal_acta")
            s1 = sal_r[sal_r["ID"] == sel].iloc[0].to_dict()
            it_s, ds = _items_texto(s1["Items_Salida"])
            ret = json.loads(s1["Items_Retorno"]) if s1["Items_Retorno"] else {}
            it_r = [lab for i, lab in zip(ds.get("ids", []), ds.get("labels", [])) if i in ret.get("vueltos", [])]
            if ret.get("con"):
                it_r.append(f"Además: {ret['con']}")
            pdf = D.pdf_acta_salida(U.cli()["Nombre"], r, s1, it_s, it_r, U.quien())
            st.download_button("🧾 Descargar acta (PDF)", pdf, file_name=f"acta_salida_{ced}_{s1['F_Salida'][:10]}.pdf", mime="application/pdf", key=f"acta_{sel}")


# ══════════════════════════════════════════════════════════════
# ESCALAS GERIÁTRICAS
# ══════════════════════════════════════════════════════════════
def pagina_escalas():
    U.banner(SEC, "Escalas geriátricas", "Barthel, Braden, Downton y Pfeiffer con resultado automático.")
    ced = U.selector_residente("esc")
    if not ced:
        return
    r = U.ficha(ced)
    edad = N.calcular_edad(r["Fecha_Nacimiento"]) or 0
    nombre = st.selectbox("¿Qué escala va a aplicar?", list(N.ESCALAS), format_func=lambda k: N.ESCALAS[k]["titulo"], key="esc_sel")
    esc = N.ESCALAS[nombre]
    v = U.ver("esc")
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
            edu = st.selectbox("Nivel educativo (ajusta el resultado)", list(N.EDUCACION), index=1, format_func=lambda k: N.EDUCACION[k], key=f"es_edu_{ced}_{v}")
    puntaje = sum(resp.values())
    texto, nivel = N.interpretar(nombre, puntaje, edu)
    st.markdown(U.bloque(f"""<div class="puntaje"><div><div style="color:#55657C;font-weight:700">PUNTAJE</div>
        <div class="n">{puntaje}</div></div><div>{chip(texto, nivel)}</div></div>"""), unsafe_allow_html=True)
    if st.button("💾 GUARDAR VALORACIÓN", type="primary", key=f"es_save_{nombre}", **KW):
        detalle = "; ".join(f"{k}={p}" for k, p in resp.items()) + (f"; educacion={edu}" if edu else "")
        N.agregar("escalas", {"ID": N.nueva_id("ES"), "Cedula": ced, "Fecha_Hora": N.fmt_fh(), "Escala": nombre, "Puntaje": puntaje,
                              "Interpretacion": texto, "Detalle": detalle, "Autor": U.quien()})
        N.log(st.session_state.usuario, "ESCALA", f"{ced} · {nombre} = {puntaje}")
        U.flash("ok", f"✅ {nombre}: {puntaje} pts · {texto}")
        U.nueva_version("esc")
        st.rerun()
    hist = N.leer("escalas")
    hist = hist[(hist["Cedula"] == ced) & (hist["Escala"] == nombre)].sort_values("Fecha_Hora", ascending=False)
    st.markdown(f"##### Historial de {nombre}")
    if hist.empty:
        st.caption("Sin valoraciones previas de esta escala.")
    else:
        U.tabla(hist[["Fecha_Hora", "Puntaje", "Interpretacion", "Autor"]].head(20))
        g = hist.sort_values("Fecha_Hora").set_index("Fecha_Hora")[["Puntaje"]].apply(pd.to_numeric, errors="coerce")
        if len(g) >= 2:
            st.line_chart(g)
