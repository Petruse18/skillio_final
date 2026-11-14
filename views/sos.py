"""SOS: pentru 45 de lei, un meșter real te ghidează prin apel video, doar prin aplicație.
Meșterul dă doar informații de urgență (ce închizi, ce nu atingi), nu reparația de la cap la coadă.
Apelul se înregistrează (cu acordul ambilor), banii stau blocați 24 de ore, iar o dispută o decide un mediator."""
from datetime import timedelta

import streamlit as st

from core import config, logica, timp
from core.logica import Eroare
from ui import comp as c

JITSI = "https://meet.jit.si/"
STARI = {"asteapta": "Căutăm un meșter", "in_apel": "În apel", "incheiat": "Apel încheiat",
         "disputa": "La mediator", "eliberat": "Plătit", "returnat": "Bani returnați"}


def _act(fn, *a, ok=None):
    try:
        r = fn(*a)
        if ok:
            c.toast(ok)
        st.rerun()
        return r
    except Eroare as e:
        st.error(str(e))


def card_acasa(u):
    """Cardul SOS de pe ecranul clientului."""
    with st.container(key="card_sos"):
        c.h(f'<div class="sk-row"><span class="sk-sos-dot"></span><div class="sk-grow"><div class="sk-h">SOS · '
            f'{c.lei(config.SOS_PRET)}</div><div class="sk-cap">Țeavă spartă, miros de gaz, fără curent? Un meșter '
            f'te ghidează prin video în câteva minute.</div></div></div>')
        if st.button("Cere ajutor acum", key="sos_start", type="primary", width="stretch", icon=":material/videocam:"):
            c.go("sos")


def ecran(u, sid=None):
    c.bara_sus("SOS", "acasa")
    if sid:
        _apel(u, logica.sos(sid))
        return
    if u["rol"] == "mester":
        _lista_mester(u)
        return
    deschis = next((s for s in logica.sos_client(u["id"]) if s["status"] in ("asteapta", "in_apel", "incheiat")), None)
    if deschis:
        _apel(u, deschis)
        return
    c.h('<div class="sk-title">Ajutor de urgență</div><div class="sk-b" style="color:var(--sk-muted)">'
        'Un meșter verificat îți spune prin video ce să închizi și ce să nu atingi, până ajunge cineva.</div>')
    mes = st.selectbox("Ce fel de problemă?", list(config.MESERII), format_func=c.meserie_nume, key="sos_mes")
    prob = st.text_input("Ce s-a întâmplat?", placeholder="Ex: s-a spart țeava sub chiuvetă", key="sos_prob")
    c.h(c.kv([("Apel video cu un meșter", c.lei(config.SOS_PRET)),
              ("Din care primește meșterul", c.lei(config.SOS_MESTER)),
              ("Banii stau blocați", f"{config.FEREASTRA_DISPUTA_ORE} h după apel")]))
    acord = st.checkbox("Sunt de acord ca apelul să fie înregistrat. Înregistrarea e stocată în UE, o vede doar "
                        "mediatorul în caz de dispută și se șterge automat după 30 de zile.", key="sos_acord")
    c.alerta("Meșterul îți dă doar instrucțiuni de siguranță (ex. „închide robinetul general”). Pentru gaz: "
             "ieși din casă și sună la 112.", "escrow", "alert")
    if st.button(f"Plătesc {c.lei(config.SOS_PRET)} și sun", type="primary", width="stretch", key="sos_go",
                 icon=":material/call:"):
        sid = _act_val(logica.cere_sos, u["id"], mes, prob, acord)
        if sid:
            c.go("sos", sid)


def _act_val(fn, *a):
    try:
        return fn(*a)
    except Eroare as e:
        st.error(str(e))


def _lista_mester(u):
    rows = logica.sos_deschise(u["id"])
    c.h('<div class="sk-title">Apeluri SOS</div><div class="sk-b" style="color:var(--sk-muted)">'
        f'Răspunzi primul, primești {c.lei(config.SOS_MESTER)}. Doar instrucțiuni de siguranță, prin video.</div>')
    if not rows:
        c.gol("Niciun apel SOS acum.", "check")
    for s in rows:
        cl = logica.user(s["client_id"])
        with st.container(key=f"cardsel_sos{s['id']}"):
            c.h(f'<div class="sk-between"><b class="sk-h">{c.esc(s["problema"])}</b><span class="sk-badge">'
                f'{STARI[s["status"]]}</span></div><div class="sk-cap">{c.esc(cl["nume"].split()[0])} · '
                f'{c.esc(cl["cartier"])} · {c.meserie_nume(s["meserie"])} · {timp.de_cand(s["creat_la"])}</div>')
            if s["status"] == "asteapta":
                if st.button("Preiau apelul", type="primary", width="stretch", key=f"sos_acc{s['id']}"):
                    _act(logica.accepta_sos, s["id"], u["id"])
            elif st.button("Deschide", width="stretch", key=f"sos_open{s['id']}"):
                c.go("sos", s["id"])


def _apel(u, s):
    e_client = u["id"] == s["client_id"]
    alt = logica.user(s["mester_id"]) if e_client and s["mester_id"] else logica.user(s["client_id"])
    c.h(f'<div class="sk-between"><div class="sk-title" style="font-size:22px">{c.esc(s["problema"])}</div>'
        f'<span class="sk-badge">{STARI[s["status"]]}</span></div>')
    if s["status"] == "asteapta":
        c.alerta(f'Am anunțat meșterii disponibili. {c.lei(config.SOS_PRET)} sunt blocați până la final.', "escrow",
                 "clock")
        st.caption("Ecranul se actualizează singur când un meșter preia apelul.")
        return
    if s["status"] == "in_apel":
        c.h(f'<div class="sk-call"><div class="sk-call-av">{c.initiale(alt["nume"])}</div><div>'
            f'<div class="sk-h">{c.esc(alt["nume"])}</div><div class="sk-cap">Apel video securizat · înregistrat · '
            f'numerele rămân ascunse</div></div><span class="sk-rec">REC</span></div>')
        st.link_button("Intră în apelul video", JITSI + s["camera"], type="primary", width="stretch",
                       icon=":material/videocam:")
        st.caption("Apelul se deschide în browser, fără număr de telefon. Ambele părți intră în aceeași cameră.")
        if st.button("Închide apelul", width="stretch", key="sos_end", icon=":material/call_end:"):
            _act(logica.incheie_sos, s["id"], u["id"], ok="Apel încheiat.")
    if s["status"] == "incheiat":
        pana = timp.din_iso(s["incheiat_la"]) + timedelta(hours=config.FEREASTRA_DISPUTA_ORE)
        c.alerta(f'Apel încheiat. {c.lei(config.SOS_PRET)} pleacă la meșter pe {timp.data_ora(pana)}, dacă nu se '
                 f'deschide o dispută.', "escrow", "lock")
        if e_client and st.button("M-a ajutat, plătește acum", type="primary", width="stretch", key="sos_ok"):
            _act(logica.confirma_sos, s["id"], u["id"], ok="Mulțumim! Meșterul și-a primit banii.")
    if s["status"] in ("in_apel", "incheiat"):
        with st.expander("Nu m-a ajutat, deschid o dispută" if e_client else "Deschide o dispută"):
            motiv = st.text_input("Ce s-a întâmplat?", key="sos_disp")
            if st.button("Trimite mediatorului", key="danger_sos_disp"):
                _act(logica.disputa_sos, s["id"], u["id"], motiv, ok="Un mediator verifică înregistrarea apelului.")
    if s["status"] == "disputa":
        c.alerta("Un mediator SKILLIO ascultă înregistrarea și decide. Banii rămân blocați.", "escrow", "alert")
    if s["status"] in ("eliberat", "returnat"):
        c.alerta(("Meșterul a primit plata." if s["status"] == "eliberat" else "Banii s-au întors la client.")
                 + (f" Mediator: {c.esc(s['rezolutie'])}" if s["rezolutie"] else ""), "ai", "check")
