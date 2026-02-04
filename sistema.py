for part in msg.walk():
    fn = part.get_filename()
    payload = part.get_payload(decode=True)
    if not payload:
        continue

    fn = fn.lower() if fn else "sin_nombre"

    # --- ZIP ---
    if fn.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as z_in:
                for z_name in z_in.namelist():
                    z_payload = z_in.read(z_name)

                    # INTENTAR JSON
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

                    # INTENTAR PDF
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
        # --- INTENTAR JSON AUN SIN EXTENSIÓN ---
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

        # --- INTENTAR PDF ---
        try:
            u_tmp, _ = obtener_datos_dte(io.BytesIO(payload))
            if u_tmp:
                u_tmp = str(u_tmp).upper()
                zf_final.writestr(f"{u_tmp}.pdf", payload)
                encontrados += 1
        except:
            pass
