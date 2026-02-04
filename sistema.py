if submit_button:
    st.session_state.email_pref, st.session_state.pass_pref = email_user, email_pass
    if recordar:
        guardar_local(email_user, email_pass)

    try:
        imap_date = fecha_desde.strftime("%d-%b-%Y")
        mail = imaplib.IMAP4_SSL(server_choice)
        mail.login(email_user, email_pass)
        mail.select("inbox")

        status, search_data = mail.search(
            None,
            f'(OR SUBJECT "{buscar_texto}" TEXT "{buscar_texto}" SINCE {imap_date})'
        )

        mail_ids = search_data[0].split()

        if mail_ids:
            zip_buffer = io.BytesIO()
            encontrados = 0
            progreso_mail = st.progress(0)

            with zipfile.ZipFile(zip_buffer, "w") as zf_final:
                for idx, m_id in enumerate(mail_ids):
                    res, data = mail.fetch(m_id, "(RFC822)")
                    msg = email.message_from_bytes(data[0][1])

                    for part in msg.walk():
                        fn = part.get_filename()
                        payload = part.get_payload(decode=True)
                        if not payload:
                            continue

                        fn = fn.lower() if fn else "sin_nombre"

                        # ================= ZIP =================
                        if fn.endswith(".zip"):
                            try:
                                with zipfile.ZipFile(io.BytesIO(payload)) as z_in:
                                    for z_name in z_in.namelist():
                                        z_payload = z_in.read(z_name)

                                        # ---- INTENTAR JSON ----
                                        try:
                                            raw = json.loads(z_payload)
                                            u_tmp = raw.get("identificacion", {}).get("codigoGeneracion")
                                            if u_tmp:
                                                u_tmp = str(u_tmp).upper()
                                                zf_final.writestr(f"{u_tmp}.json", z_payload)
                                                encontrados += 1
                                                continue
                                        except:
                                            pass

                                        # ---- INTENTAR PDF ----
                                        try:
                                            u_tmp, _ = obtener_datos_dte(io.BytesIO(z_payload))
                                            if u_tmp:
                                                u_tmp = str(u_tmp).upper()
                                                zf_final.writestr(f"{u_tmp}.pdf", z_payload)
                                                encontrados += 1
                                        except:
                                            pass
                            except:
                                pass

                        else:
                            # ============ INTENTAR JSON ============
                            try:
                                raw = json.loads(payload)
                                u_tmp = raw.get("identificacion", {}).get("codigoGeneracion")
                                if u_tmp:
                                    u_tmp = str(u_tmp).upper()
                                    zf_final.writestr(f"{u_tmp}.json", payload)
                                    encontrados += 1
                                    continue
                            except:
                                pass

                            # ============ INTENTAR PDF ============
                            try:
                                u_tmp, _ = obtener_datos_dte(io.BytesIO(payload))
                                if u_tmp:
                                    u_tmp = str(u_tmp).upper()
                                    zf_final.writestr(f"{u_tmp}.pdf", payload)
                                    encontrados += 1
                            except:
                                pass

                    progreso_mail.progress((idx + 1) / len(mail_ids))

            if encontrados > 0:
                st.success(f"✅ {encontrados} archivos DTE procesados.")
                st.download_button(
                    "📥 DESCARGAR ZIP",
                    zip_buffer.getvalue(),
                    "DTE_Busqueda.zip"
                )
            else:
                st.warning("No se encontraron archivos válidos con ese criterio.")

        mail.logout()

    except Exception as e:
        st.error(f"Error de conexión o búsqueda: {e}")
