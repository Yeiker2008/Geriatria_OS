# -*- coding: utf-8 -*-
"""vistas_owner.py · Panel de los PROPIETARIOS (planes, clientes, pagos, ranking). Nunca muestra datos clínicos."""
import pandas as pd
import streamlit as st

import nucleo as N
import ui as U
from ui import KW, chip, h

PLANES = list(N.PLANES)
MOD_ETQ = N.MODULOS


def _planes_ficha():
    cols = st.columns(len(PLANES) - 1)
    for c, (nom, p) in zip(cols, [(k, v) for k, v in N.PLANES.items() if k != "Personalizado"]):
        c.markdown(U.bloque(f"<div class='kpi'><div class='n' style='font-size:1.4rem'>{h(nom)}</div>"
                            f"<div class='l'>👥 {p['max_usuarios']} usuarios · 👴 {p['max_residentes']} residentes</div>"
                            f"<div class='l' style='font-weight:500'>{'<br>'.join('• ' + h(b) for b in p['beneficios'])}</div></div>"), unsafe_allow_html=True)


def _campos_plan(plan, cod, v, cli=None):
    """Controles de límites, módulos y roles, que arrancan con los valores del plan elegido."""
    p = N.PLANES[plan]
    mu = int(N._num(cli["Max_Usuarios"], p["max_usuarios"])) if cli else p["max_usuarios"]
    mr = int(N._num(cli["Max_Residentes"], p["max_residentes"])) if cli and cli.get("Max_Residentes") else p["max_residentes"]
    mods = sorted(N.modulos_cliente(cli)) if cli else p["modulos"]
    roles = N.roles_cliente(cli) if cli else p["roles"]
    k = f"{cod}_{plan}_{v}"
    a, b = st.columns(2)
    mxu = a.number_input("Máximo de usuarios activos", min_value=1, max_value=2000, value=mu, key=f"pl_mu_{k}")
    mxr = b.number_input("Máximo de residentes activos", min_value=1, max_value=5000, value=mr, key=f"pl_mr_{k}")
    ms = st.multiselect("Módulos incluidos", list(MOD_ETQ), default=[m for m in mods if m in MOD_ETQ], format_func=lambda m: MOD_ETQ[m], key=f"pl_m_{k}")
    rs = st.multiselect("Roles que puede crear", N.ROLES_TODOS, default=[r for r in roles if r in N.ROLES_TODOS], key=f"pl_r_{k}")
    return mxu, mxr, ms, rs


def pagina_owner_hub():
    U.banner("Owner", "Panel de propietarios", "Suscripciones, clientes e ingresos. Aquí nunca se muestran datos clínicos.")
    regs = N.leer("clientes").to_dict("records")
    con = [r for r in regs if N.estado_servicio(r)[0]]
    sin = [r for r in regs if not N.estado_servicio(r)[0]]
    por_vencer = [r for r in con if N.estado_servicio(r)[2] is not None and N.estado_servicio(r)[2] <= 7]
    mrr = sum(N._num(r["Precio_Mensual"]) for r in con)
    pg = N.leer("pagos")
    cobrado = sum(N._num(x) for x in pg[pg["Fecha"].str.startswith(N.hoy().strftime("%Y-%m"))]["Monto"])
    c = st.columns(6)
    for col, (n, l, t) in zip(c, [(len(regs), "Geriátricos", ""), (len(con), "Con acceso", ""), (len(sin), "Sin acceso", "crit" if sin else ""),
                                  (len(por_vencer), "Vencen en 7 días", "warn" if por_vencer else ""), (N.cop(mrr), "Ingreso mensual esperado", ""),
                                  (N.cop(cobrado), "Cobrado este mes", "")]):
        col.markdown(U.kpi(n, l, t), unsafe_allow_html=True)
    if not regs:
        st.info("Aún no hay geriátricos. Cree el primero en **➕ Nuevo cliente**.")
        return
    st.markdown("##### 🏢 Todos los geriátricos")
    U.tabla(pd.DataFrame([{"Geriátrico": r["Nombre"], "Código": r["Codigo"], "Plan": r["Plan"], "Usuarios": r["Max_Usuarios"], "Residentes": r["Max_Residentes"],
                           "Mensualidad": N.cop(r["Precio_Mensual"]), "Estado": N.etiqueta_servicio(r)[0], "Vence": r["Vence"]} for r in regs]))
    cobrar = [r for r in regs if r in por_vencer or r in sin]
    if cobrar:
        st.markdown("##### 📞 Cobranza")
        for r in cobrar:
            t, n = N.etiqueta_servicio(r)
            w = U.wa_link(r["Telefono"], f"Hola {r['Contacto']}, le escribimos de Geriatría OS: la suscripción de {r['Nombre']} ({t.lower()}). ¿Nos confirma el pago? Gracias.")
            st.markdown(f"{chip(t, n)} **{h(r['Nombre'])}** · {N.cop(r['Precio_Mensual'])}" + (f" · [💬 WhatsApp]({w})" if w else ""), unsafe_allow_html=True)


def pagina_ranking():
    U.banner("Owner", "Los mejores geriátricos", "Ranking de cumplimiento de pagos: los 5 primeros son los que ofrecemos como recomendados.")
    st.caption("Puntaje = % de pagos hechos a tiempo (el día del vencimiento o antes), menos una penalización por días de atraso, más un pequeño bono por antigüedad. "
               "Solo entran geriátricos con 2+ pagos, servicio vigente y sin deuda.")
    rk = N.ranking_puntualidad()
    if not rk:
        st.info("Aún no hay clientes.")
        return
    top = [r for r in rk if r["Elegible"]][:5]
    if not top:
        st.info("Todavía ninguno cumple los requisitos (2+ pagos registrados con puntualidad).")
    medallas = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for m, r in zip(medallas, top):
        st.markdown(U.bloque(f"<div class='ficha'><div class='avatar' style='font-size:1.6rem'>{m}</div><div><div class='nom'>{h(r['Nombre'])}</div>"
                             f"<div class='sub2'>Plan {h(r['Plan'])} · {r['Pagos']} pagos · {r['APuntual']}% a tiempo · atraso promedio {r['AtrasoProm']} días</div></div>"
                             f"<div class='der'><div class='n' style='font-family:Fraunces;font-size:2rem;font-weight:700'>{r['Puntaje']}</div></div></div>"), unsafe_allow_html=True)
    st.markdown("##### Tabla completa")
    df = pd.DataFrame([{"Puesto": r["Posicion"] or "—", "Geriátrico": r["Nombre"], "Plan": r["Plan"], "Pagos": r["Pagos"], "% a tiempo": r["APuntual"],
                        "Atraso prom. (días)": r["AtrasoProm"], "Puntaje": r["Puntaje"], "Al día": "Sí" if r["AlDia"] else "No",
                        "Recomendable": "⭐ Sí" if r["Posicion"] and r["Posicion"] <= 5 else "—"} for r in rk])
    U.tabla(df)
    st.download_button("⬇️ Descargar ranking (CSV)", N.csv_seguro(df), file_name="ranking_geriatricos.csv", mime="text/csv")


def pagina_clientes():
    U.banner("Owner", "Clientes", "Estado, pagos, plan y accesos de cada geriátrico.")
    cl = N.leer("clientes")
    if cl.empty:
        st.info("Aún no hay geriátricos. Cree el primero en **➕ Nuevo cliente**.")
        return
    etq = {r.Codigo: f"{r.Nombre} · {r.Codigo}" for r in cl.itertuples()}
    cod = st.selectbox("Geriátrico", list(etq), format_func=lambda c: etq[c], key="cli_sel")
    cli = N.buscar_cliente(cod)
    txt, niv = N.etiqueta_servicio(cli)
    st.markdown(U.bloque(f"""<div class="ficha"><div class="avatar">🏢</div><div>
        <div class="nom">{h(cli['Nombre'])} {chip(txt, niv)}</div>
        <div class="sub2">Código <b>{h(cli['Codigo'])}</b> · Plan {h(cli['Plan'] or '—')} · {h(cli['Max_Usuarios'] or '—')} usuarios · {h(cli['Max_Residentes'] or '—')} residentes ·
        {N.cop(cli['Precio_Mensual'])}/mes · Vence {h(cli['Vence'] or '—')}</div>
        <div class="sub2">{h(cli['Contacto'])} {h(cli['Telefono'])} {h(cli['Email'])}</div></div>
        <div class="der">{chip(cli['Modo_Boveda'] or 'Central', 'ok')}</div></div>"""), unsafe_allow_html=True)
    actor = st.session_state.usuario
    t1, t2, t3, t4 = st.tabs(["💳 Estado y pagos", "📝 Plan y datos", "👥 Accesos", "🗄 Bóveda"])

    with t1:
        v = U.ver("cli_pago")
        with st.form(f"form_pago_{cod}_{v}"):
            st.markdown("##### Registrar pago (extiende la vigencia y reactiva el acceso)")
            a, b, c = st.columns(3)
            monto = a.number_input("Monto (COP)", min_value=0.0, value=float(N._num(cli["Precio_Mensual"])), step=1000.0, key=f"p_m_{cod}_{v}")
            meses = b.number_input("Meses que cubre", min_value=1, max_value=24, value=1, step=1, key=f"p_n_{cod}_{v}")
            metodo = c.selectbox("Método", ["Transferencia", "Nequi", "Daviplata", "Efectivo", "Otro"], key=f"p_t_{cod}_{v}")
            nota = st.text_input("Nota (opcional)", key=f"p_o_{cod}_{v}")
            if st.form_submit_button("REGISTRAR PAGO", type="primary", **KW):
                nueva = N.registrar_pago(cod, monto, meses, metodo, nota, actor)
                U.flash("ok", f"✅ Pago registrado. {cli['Nombre']} tiene acceso hasta el {nueva.strftime('%d/%m/%Y')}.")
                U.nueva_version("cli_pago")
                st.rerun()
        v2 = U.ver("cli_estado")
        with st.form(f"form_estado_{cod}_{v2}"):
            if cli["Estado"] == "Activo":
                st.markdown("##### ⛔ Suspender acceso (inmediato, incluso para quienes ya están dentro)")
                motivo = st.text_input("Motivo (ej: falta de pago)", key=f"s_m_{cod}_{v2}")
                if st.form_submit_button("Suspender ahora", **KW):
                    N.actualizar("clientes", "Codigo", cod, {"Estado": "Suspendido", "Notas": (cli["Notas"] + " | " if cli["Notas"] else "") + f"{N.hoy()} suspendido: {motivo}"})
                    N.log_control(actor, "SUSPENDE", f"{cod} · {motivo}")
                    U.flash("warn", f"⛔ {cli['Nombre']} fue suspendido.")
                    U.nueva_version("cli_estado")
                    st.rerun()
            else:
                st.markdown("##### ✅ Reactivar acceso")
                if st.form_submit_button("Reactivar", type="primary", **KW):
                    N.actualizar("clientes", "Codigo", cod, {"Estado": "Activo"})
                    N.log_control(actor, "REACTIVA", cod)
                    U.flash("ok", f"✅ {cli['Nombre']} fue reactivado.")
                    U.nueva_version("cli_estado")
                    st.rerun()
        pg = N.leer("pagos")
        pg = pg[pg["Codigo"] == cod].sort_values("Fecha", ascending=False)
        st.markdown("##### Historial de pagos")
        if pg.empty:
            st.caption("Sin pagos registrados.")
        else:
            U.tabla(pg[["Fecha", "Monto", "Metodo", "Periodo", "Dias_Atraso", "Nota"]])

    with t2:
        _planes_ficha()
        plan = st.selectbox("Plan", PLANES, index=PLANES.index(cli["Plan"]) if cli["Plan"] in PLANES else 0, key=f"c_pl_{cod}")
        st.caption("Al cambiar de plan, los límites, módulos y roles de abajo se llenan con los del plan. Puede ajustarlos antes de guardar.")
        v = U.ver("cli_ed")
        mxu, mxr, ms, rs = _campos_plan(plan, cod, v, cli if plan == cli["Plan"] else None)
        with st.form(f"form_cli_ed_{cod}_{v}"):
            a, b = st.columns(2)
            nom = a.text_input("Nombre del geriátrico", cli["Nombre"], key=f"c_n_{cod}_{v}")
            nit = b.text_input("NIT", cli["NIT"], key=f"c_nit_{cod}_{v}")
            a, b, c = st.columns(3)
            con_ = a.text_input("Contacto", cli["Contacto"], key=f"c_c_{cod}_{v}")
            tel = b.text_input("Teléfono / WhatsApp", cli["Telefono"], key=f"c_t_{cod}_{v}")
            mail = c.text_input("Email", cli["Email"], key=f"c_e_{cod}_{v}")
            a, b, c = st.columns(3)
            precio = a.number_input("Mensualidad (COP)", min_value=0.0, value=float(N._num(cli["Precio_Mensual"])), step=1000.0, key=f"c_pr_{cod}_{v}")
            gr = b.number_input("Días de gracia", min_value=0, max_value=60, value=int(N._num(cli["Dias_Gracia"])), step=1, key=f"c_g_{cod}_{v}")
            sin_v = c.checkbox("Sin fecha de vencimiento", value=not cli["Vence"], key=f"c_sv_{cod}_{v}")
            vence = st.date_input("Vigente hasta", value=N.parsear_fecha(cli["Vence"]) or N.hoy(), key=f"c_v_{cod}_{v}")
            if st.form_submit_button("💾 GUARDAR CAMBIOS", type="primary", **KW):
                if not nom.strip():
                    st.error("El nombre es obligatorio.")
                else:
                    N.actualizar("clientes", "Codigo", cod, {"Nombre": nom.strip(), "NIT": nit.strip(), "Plan": plan, "Contacto": con_.strip(), "Telefono": tel.strip(),
                                                             "Email": mail.strip(), "Max_Usuarios": mxu, "Max_Residentes": mxr, "Modulos": ",".join(ms),
                                                             "Roles_Permitidos": ",".join(rs), "Precio_Mensual": precio, "Dias_Gracia": gr,
                                                             "Vence": "" if sin_v else vence.isoformat()})
                    N.log_control(actor, "EDITA_CLIENTE", f"{cod} · plan {plan}")
                    U.flash("ok", "✅ Datos del cliente actualizados.")
                    U.nueva_version("cli_ed")
                    st.rerun()

    with t3:
        st.caption("Como propietario usted ve solo los usuarios del geriátrico. Los datos clínicos no se muestran en este panel.")
        if not N.abrir_tenant(U.cfg(), cli):
            st.error("No se pudo abrir la bóveda de este cliente.")
            st.code(N.estado_nube(cod)["error"] or "")
        else:
            usr = N.leer("usuarios", tid=cod)
            U.tabla(usr.drop(columns=["Password"]))
            v = U.ver("cli_pw")
            with st.form(f"form_cli_pw_{cod}_{v}"):
                st.markdown("##### 🔑 Restablecer clave de un usuario del cliente")
                sel = st.selectbox("Usuario", usr["Usuario"].tolist(), key=f"r_u_{cod}_{v}")
                pw = st.text_input("Clave temporal", value=N.clave_temporal(), key=f"r_p_{cod}_{v}")
                st.caption("Se le pedirá cambiarla al ingresar. Entréguesela al cliente por un canal seguro.")
                if st.form_submit_button("Restablecer", **KW):
                    if len(pw) < 8:
                        st.error("Mínimo 8 caracteres.")
                    else:
                        N.actualizar("usuarios", "Usuario", sel, {"Password": N.hash_pw(pw), "Cambiar_Clave": "SI", "Activo": "SI"}, tid=cod)
                        N.log_control(actor, "RESET_CLAVE_CLIENTE", f"{cod} · {sel}")
                        U.flash("ok", f"✅ Clave de {sel} restablecida. Clave temporal: {pw}")
                        U.nueva_version("cli_pw")
                        st.rerun()

    with t4:
        st.markdown(f"**Modo:** {h(cli['Modo_Boveda'] or 'Central')}")
        if cli["Carpeta_URL"]:
            st.markdown(f"[📁 Abrir carpeta del cliente en Drive]({cli['Carpeta_URL']})")
        if cli["Sheet_ID"]:
            st.markdown(f"[📄 Abrir base de datos](https://docs.google.com/spreadsheets/d/{cli['Sheet_ID']})")
            st.caption("Abrir la hoja es solo para soporte técnico: contiene datos clínicos del cliente.")
        if st.button("🔌 Probar conexión con la bóveda", key=f"probar_{cod}"):
            if N.abrir_tenant(U.cfg(), cli, forzar=True):
                st.success("✅ La bóveda responde correctamente.")
            else:
                st.error("No se pudo conectar:")
                st.code(N.estado_nube(cod)["error"] or "")
        v = U.ver("cli_vault")
        with st.form(f"form_vault_{cod}_{v}"):
            nuevo = st.text_input("Cambiar ID de la hoja (bóveda propia del cliente)", cli["Sheet_ID"], key=f"v_s_{cod}_{v}")
            if st.form_submit_button("Guardar ID", **KW):
                N.actualizar("clientes", "Codigo", cod, {"Sheet_ID": nuevo.strip(), "Modo_Boveda": "Propia del cliente" if nuevo.strip() != cli["Sheet_ID"] else cli["Modo_Boveda"]})
                N.log_control(actor, "CAMBIA_BOVEDA", cod)
                U.flash("ok", "✅ Bóveda actualizada.")
                U.nueva_version("cli_vault")
                st.rerun()


def pagina_nuevo_cliente():
    U.banner("Owner", "Nuevo cliente", "Cree un geriátrico: se genera su código, su bóveda propia y su primer administrador.")
    ent = st.session_state.get("nuevo_cliente")
    if ent:
        st.success(f"✅ {ent['nombre']} fue creado. **Esta es la única vez que verá la contraseña temporal.**")
        st.code(f"🏥 Geriatría OS — Acceso de {ent['nombre']}\nCódigo del geriátrico: {ent['codigo']}\nUsuario: {ent['usuario']}\n"
                f"Contraseña temporal: {ent['clave']}\n(Deberá cambiarla en su primer ingreso)", language="text")
        if st.button("Entendido, crear otro", key="ent_ok"):
            st.session_state.pop("nuevo_cliente")
            st.rerun()
        return
    _planes_ficha()
    plan = st.selectbox("Plan", PLANES, index=1, key="n_plan")
    v = U.ver("cli_new")
    mxu, mxr, ms, rs = _campos_plan(plan, "nuevo", v)
    with st.form(f"form_nuevo_{v}"):
        st.markdown("##### Datos del geriátrico")
        a, b = st.columns(2)
        nom = a.text_input("Nombre del geriátrico", key=f"n_n_{v}")
        nit = b.text_input("NIT", key=f"n_nit_{v}")
        a, b, c = st.columns(3)
        con_ = a.text_input("Persona de contacto", key=f"n_c_{v}")
        tel = b.text_input("Teléfono / WhatsApp", key=f"n_t_{v}")
        mail = c.text_input("Email", key=f"n_e_{v}")
        st.markdown("##### Suscripción")
        a, b, c = st.columns(3)
        precio = a.number_input("Mensualidad (COP)", min_value=0.0, value=0.0, step=1000.0, key=f"n_pr_{v}")
        vence = b.date_input("Vigente hasta", value=N.sumar_meses(N.hoy(), 1), key=f"n_v_{v}")
        gr = c.number_input("Días de gracia", min_value=0, max_value=60, value=3, step=1, key=f"n_g_{v}")
        st.markdown("##### Bóveda de datos")
        modo = st.radio("¿Dónde se guardan sus datos?", ["Central", "Propia del cliente"], horizontal=True, key=f"n_m_{v}")
        sid = st.text_input("ID de la hoja del cliente (solo modo «Propia del cliente»)", key=f"n_s_{v}")
        st.markdown("##### Primer administrador del geriátrico")
        a, b = st.columns(2)
        au = a.text_input("Usuario", value="admin", key=f"n_au_{v}")
        ap = b.text_input("Contraseña temporal", value=N.clave_temporal(), key=f"n_ap_{v}")
        enviado = st.form_submit_button("CREAR GERIÁTRICO", type="primary", **KW)
    if enviado:
        au_l = au.strip().lower()
        if not nom.strip() or not au_l or " " in au_l or len(ap) < 8:
            st.error("Complete el nombre, un usuario sin espacios y una contraseña temporal de 8+ caracteres.")
            return
        datos = {"Nombre": nom.strip(), "NIT": nit.strip(), "Contacto": con_.strip(), "Telefono": tel.strip(), "Email": mail.strip(), "Plan": plan,
                 "Max_Usuarios": mxu, "Max_Residentes": mxr, "Modulos": ",".join(ms), "Roles_Permitidos": ",".join(rs), "Precio_Mensual": precio,
                 "Vence": vence.isoformat(), "Dias_Gracia": gr, "Modo_Boveda": modo, "Sheet_ID": sid.strip()}
        try:
            codigo = N.crear_cliente(U.cfg(), datos, au_l, ap, st.session_state.usuario)
        except Exception as e:
            st.error(f"No se pudo completar la creación: {e}")
            return
        st.session_state["nuevo_cliente"] = {"nombre": nom.strip(), "codigo": codigo, "usuario": au_l, "clave": ap}
        U.nueva_version("cli_new")
        st.rerun()


def pagina_pagos():
    U.banner("Owner", "Pagos", "Historial de cobros de todos los geriátricos.")
    pg = N.leer("pagos").sort_values("Fecha", ascending=False)
    if pg.empty:
        st.info("Aún no hay pagos registrados. Se registran desde **Clientes ▸ Estado y pagos**.")
        return
    nombres = N.leer("clientes").set_index("Codigo")["Nombre"].to_dict()
    pg = pg.assign(Geriatrico=pg["Codigo"].map(nombres).fillna("—"), Valor=pg["Monto"].map(N._num))
    st.markdown(U.kpi(N.cop(pg["Valor"].sum()), "Total cobrado (histórico)"), unsafe_allow_html=True)
    st.markdown("##### Cobrado por mes (COP)")
    st.bar_chart(pg.assign(Mes=pg["Fecha"].str[:7]).groupby("Mes")["Valor"].sum().sort_index())
    U.tabla(pg[["Fecha", "Geriatrico", "Codigo", "Monto", "Metodo", "Periodo", "Dias_Atraso", "Nota", "Registrado_Por"]])
    st.download_button("⬇️ Descargar pagos (CSV)", N.csv_seguro(pg.drop(columns=["Valor"])), file_name="pagos.csv", mime="text/csv")


def pagina_owner_sistema():
    U.banner("Owner", "Sistema", "Conexión con Google, configuración y auditoría del panel.")
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
        if st.button("🔄 Reintentar conexión", key="reconectar"):
            N.conectar(U.cfg(), forzar=True)
            st.rerun()
        with st.expander("Ejemplo de Secrets (Streamlit Cloud ▸ Settings ▸ Secrets)"):
            st.code('owner_code = "UN-CODIGO-SECRETO-LARGO"      # se escribe en el campo «Código» del login\n'
                    'google_folder_id = "ID de tu carpeta de Drive"\n'
                    '# control_sheet_id = "ID de la hoja OS_Control (opcional)"\n\n'
                    '# Un propietario por socio (genere cada hash abajo):\n'
                    '[owners.yeiker]\npassword_hash = "pbkdf2$310000$..."\n\n[owners.socio2]\npassword_hash = "pbkdf2$310000$..."\n\n'
                    '[gcp_service_account]\ntype = "service_account"\nproject_id = "geriatria-os"\n'
                    'private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"\n'
                    'client_email = "geriatria@geriatria-os.iam.gserviceaccount.com"\ntoken_uri = "https://oauth2.googleapis.com/token"', language="toml")
        with st.expander("Generar hash de contraseña (para cada propietario)"):
            pw = st.text_input("Contraseña a convertir (12+ caracteres)", type="password", key="gen_hash")
            if pw:
                st.code(f'password_hash = "{N.hash_pw(pw)}"', language="toml")
    with t2:
        U.tabla(N.leer("logs_control").sort_values("Fecha_Hora", ascending=False).head(300))
