"""Panoul echipei SKILLIO: rapoarte și dispute, bani blocați, comision, controale pentru prezentare."""
import json

import streamlit as st

from views import comunitate

from core import config, db, logica, timp
from services import ai, autentificare, mesaje_externe, solana, stocare, voce
from ui import comp as c


def panou(u):
    c.h('<div class="sk-title">Mediere</div><div class="sk-cap">Echipa SKILLIO. Fiecare dispută o decide un om, '
        'pe baza pozelor, a chatului, a cronologiei și a înregistrărilor.</div>')
    s = logica.statistici_platforma()
    c.h('<div class="sk-stats">'
        f'<div class="sk-stat"><span class="v">{s["lucrari_active"]}</span><span class="l">Lucrări active</span></div>'
        f'<div class="sk-stat"><span class="v">{s["finalizate"]}</span><span class="l">Lucrări finalizate</span></div>'
        f'<div class="sk-stat"><span class="v" style="color:var(--sk-escrow)">{c.lei(s["blocat"])}</span>'
        f'<span class="l">Bani blocați acum</span></div>'
        f'<div class="sk-stat"><span class="v">{c.lei(s["comision"])}</span><span class="l">Comision încasat '
        f'({config.COMISION:.0%})</span></div>'
        f'<div class="sk-stat"><span class="v">{s["mesteri"]}</span><span class="l">Meșteri</span></div>'
        f'<div class="sk-stat"><span class="v">{s["utilizatori"]}</span><span class="l">Clienți</span></div></div>')

    _sos_dispute()
    deschise = logica.rapoarte("deschis")
    c.h(f'<div class="sk-label">Dispute și rapoarte ({len(deschise)})</div>')
    if not deschise:
        c.gol("Niciun raport deschis.", "check")
    for r in deschise:
        disp = '<span class="sk-badge danger">Dispută, bani blocați</span>' if r["disputa"] else ""
        with st.container(key=f"card_r{r['id']}"):
            c.h(f'<div class="sk-between"><div class="sk-h">{c.esc(r["motiv"])}</div>{disp}</div>'
                f'<div class="sk-cap">{c.esc(r["autor"])} → {c.esc(r["vizat"])} · {timp.de_cand(r["creat_la"])}'
                f'{" · " + c.esc(r["titlu"]) if r["titlu"] else ""}</div><div class="sk-b">{c.esc(r["detalii"])}</div>')
            if r["lucrare_id"]:
                l = logica.lucrare(r["lucrare_id"])
                rc = logica.reconfirmare(l)
                bani = logica.bani_lucrare(l["id"])
                c.h(c.kv([("Blocat", c.lei(bani["blocat"])), ("Preț reconfirmat", c.lei(rc["pret"]) if rc else "—"),
                          ("Părere AI (doar informativ)", c.esc(rc.get("ai", {}).get("verdict", "—")) if rc else "—")]))
                ultimele = logica.mesaje(l["id"])[-4:]
                if ultimele:
                    c.h('<div class="sk-cap">' + "<br>".join(c.esc(m["text"][:110]) for m in ultimele) + "</div>")
            rez = st.text_input("Decizia mediatorului (o văd ambele părți)", key=f"rez_{r['id']}")
            with st.container(horizontal=True):
                et_ok = "Dă dreptate clientului" if r["disputa"] else "Confirmă raportul"
                et_no = "Dă dreptate meșterului" if r["disputa"] else "Respinge"
                if st.button(et_no, key=f"r_no{r['id']}", width="stretch"):
                    logica.rezolva_raport(r["id"], False, rez)
                    st.rerun()
                if st.button(et_ok, type="primary", key=f"r_ok{r['id']}", width="stretch"):
                    logica.rezolva_raport(r["id"], True, rez)
                    st.rerun()
            if r["lucrare_id"] and st.button("Vezi lucrarea", key=f"link_rl{r['id']}", type="tertiary"):
                c.go("lucrare", r["lucrare_id"])

    acte = db.q("SELECT * FROM utilizatori WHERE act_status = 'in_asteptare'")
    if acte:
        c.h(f'<div class="sk-label">Documente de verificat ({len(acte)})</div>')
        for m in acte:
            with st.container(key=f"card_act{m['id']}"):
                c.h(f'<div class="sk-row">{c.avatar(m)}<b class="sk-b">{c.esc(m["nume"])}</b></div>')
                date = stocare.citeste(m["act_poza"]) if m["act_poza"] and not m["act_poza"].endswith(".pdf") else None
                if date:
                    st.image(date)
                if st.button("Marchează verificat", key=f"act_ok{m['id']}", type="primary", width="stretch"):
                    logica.actualizeaza_profil(m["id"], act_status="verificat")
                    st.rerun()

    _integrari()
    with st.expander("Living Labs: ce spun oamenii"):
        comunitate.rezultate()

    if not (config.MOD_PREZENTARE or config.DEMO_LOGIN):
        _toate_lucrarile()
        return
    with st.expander("Controale pentru prezentare", expanded=True):
        st.markdown(f"Ceasul aplicației: **{timp.data_ora(timp.acum())}** (decalaj {timp.decalaj_zile()} zile)")
        st.caption("Dă timpul înainte ca să apară întrebările „după o zi / o săptămână / o lună”.")
        with st.container(horizontal=True):
            for zile, et in ((1, "+1 zi"), (6, "+6 zile"), (23, "+23 zile")):
                if st.button(et, key=f"t_{zile}", width="stretch"):
                    db.pune_setare("decalaj_zile", timp.decalaj_zile() + zile)
                    st.rerun()
            if st.button("Ceas real", key="t_0", width="stretch"):
                db.pune_setare("decalaj_zile", 0)
                st.rerun()
        if st.button("Resetează datele demo", key="danger_reset"):
            st.session_state["_confirm_reset"] = True
        if st.session_state.get("_confirm_reset"):
            st.warning("Se șterg toate lucrările și conturile noi, apoi se pun la loc datele demo.")
            with st.container(horizontal=True):
                if st.button("Renunță", key="reset_no", width="stretch"):
                    st.session_state.pop("_confirm_reset")
                    st.rerun()
                if st.button("Da, resetează", type="primary", key="reset_yes", width="stretch"):
                    st.session_state.pop("_confirm_reset")
                    db.reseteaza()
                    st.query_params.clear()
                    st.rerun()

    _toate_lucrarile()


def _toate_lucrarile():
    with st.expander("Toate lucrările"):
        for l in db.q("SELECT l.*, a.nume AS cn, b.nume AS mn FROM lucrari l JOIN utilizatori a ON a.id = l.client_id "
                      "LEFT JOIN utilizatori b ON b.id = l.mester_id WHERE l.status != 'finalizata' OR "
                      "l.confirmat_la >= ? ORDER BY l.id DESC LIMIT 40",
                      (timp.iso(timp.acum().replace(hour=0)),)):
            st.markdown(f"**#{l['id']} {l['titlu']}** · {logica.STATUS[l['status']][0]} · {l['cn']}"
                        f"{' → ' + l['mn'] if l['mn'] else ''}")


def _integrari():
    stari = [("Login Auth0", autentificare.activ(), "securizat" , "doar intrare demo"),
             ("Bază de date", db.PG, "PostgreSQL", "SQLite local"),
             ("Poze", stocare.activ(), "cloud (S3)", "local"),
             ("Email", mesaje_externe.email_activ(), "SMTP", "oprit"),
             ("SMS", mesaje_externe.sms_activ(), "Twilio", "oprit"),
             ("Gemini", ai.activ(), "conectat", "reguli offline"),
             ("Solana", solana.activ(), config.SOLANA_CLUSTER, "plată simulată"),
             ("Voce", voce.activ(), "ElevenLabs", "vocea browserului"),
]
    with st.expander("Integrări și producție"):
        c.h('<div class="sk-badges">' + "".join(
            f'<span class="sk-badge {"ok" if on else ""}">{n}: {da if on else nu}</span>' for n, on, da, nu in stari)
            + '</div>')
        st.caption("Cheile se pun în .env, iar Auth0 în .streamlit/secrets.toml (vezi PRODUCTIE.md).")
        if mesaje_externe.email_activ() or mesaje_externe.sms_activ():
            catre = st.text_input("Trimite un mesaj de test către (email sau telefon)", key="adm_test_catre")
            if st.button("Trimite test", key="adm_test_btn", disabled=not catre.strip()):
                t = catre.strip()
                ok = (mesaje_externe.trimite_email(t, "Test SKILLIO", "Notificările prin email funcționează.")
                      if "@" in t else mesaje_externe.trimite_sms(t, "Notificările prin SMS funcționează."))
                (st.success if ok else st.error)("Trimis." if ok else "Nu s-a putut trimite. Vezi jurnalul.")
            for j in mesaje_externe.ULTIMELE[:8]:
                st.caption(f'{"✅" if j["ok"] else "❌"} {j["canal"]} → {j["catre"]} {j["detaliu"]}')
        if solana.activ():
            adr = solana.adresa_platforma()
            c.h(f'<div class="sk-cap">Portofel platformă: <a href="{solana.link_adresa(adr)}" target="_blank">'
                f'{adr} ↗</a></div>')
            if st.button("Verifică soldul Solana", key="adm_sol"):
                try:
                    st.info(f"Platformă: {solana.sold(adr):.4f} SOL · seif: {solana.sold(str(solana.seif().pubkey())):.4f} SOL")
                except Exception as e:
                    st.error(f"Rețeaua Solana nu răspunde: {e}")
            for j in solana.ULTIMELE[:6]:
                st.caption(f'{"✅" if j["ok"] else "❌"} {j["la"]} {j["tip"]}: {j["detaliu"][:60]}')
        if st.button("Pregătește un backup (JSON)", key="adm_backup"):
            date = {t: db.q(f"SELECT * FROM {t}") for t in db.TABELE}
            st.session_state["_backup"] = json.dumps(date, ensure_ascii=False, default=str)
        if st.session_state.get("_backup"):
            st.download_button("Descarcă backup-ul", st.session_state["_backup"], file_name="skillio-backup.json",
                               mime="application/json", key="adm_backup_dl")


def _sos_dispute():
    rows = db.q("SELECT * FROM sos WHERE status = 'disputa' ORDER BY id DESC")
    if not rows:
        return
    c.h(f'<div class="sk-label">Dispute SOS ({len(rows)})</div>')
    for s_ in rows:
        cl, me = logica.user(s_["client_id"]), logica.user(s_["mester_id"])
        with st.container(key=f"card_sosd{s_['id']}"):
            c.h(f'<div class="sk-between"><b class="sk-h">{c.esc(s_["problema"])}</b><span class="sk-badge danger">'
                f'{c.lei(s_["suma"])} blocați</span></div><div class="sk-cap">{c.esc(cl["nume"])} ↔ '
                f'{c.esc(me["nume"] if me else "—")} · apel înregistrat: {c.esc(s_["camera"])}.webm · se șterge '
                f'automat după 30 de zile</div><div class="sk-b">{c.esc((s_["rezolutie"] or "").replace("__deschisa_de:", ""))}: '
                f'{c.esc(s_["motiv_disputa"])}</div>')
            rez = st.text_input("Decizia mediatorului", key=f"sosrez_{s_['id']}")
            with st.container(horizontal=True):
                if st.button("Plătește meșterul", key=f"sos_no{s_['id']}", width="stretch"):
                    logica.rezolva_sos(s_["id"], False, rez)
                    st.rerun()
                if st.button("Returnează clientului", type="primary", key=f"sos_ok{s_['id']}", width="stretch"):
                    logica.rezolva_sos(s_["id"], True, rez)
                    st.rerun()
