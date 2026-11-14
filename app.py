"""SKILLIO · Find skills. Build trust.

Pornire:   streamlit run app.py
Telefon:   http://localhost:8501              (aplicația, în format de telefon)
Prezenctare: http://localhost:8501/?mod=prezentare   (client și meșter unul lângă altul)
"""
import streamlit as st

from core import config, db, logica
from ui import comp as c
from services import autentificare
from views import admin, asistent, client, comun, comunitate, lucrare, mester, prezentare, sos

st.set_page_config(page_title="SKILLIO", page_icon="🌿",
                   layout="wide" if st.query_params.get("mod") == "prezentare" else "centered",
                   initial_sidebar_state="collapsed")


@st.cache_resource
def _init():
    db.init()
    return True


_init()
c.css()

# ---------------------------------------------------------------------------
# Reîmprospătare automată: când altcineva schimbă ceva (o ofertă, un mesaj),
# ecranul se actualizează singur în 1-2 secunde.
# ---------------------------------------------------------------------------
@st.fragment(run_every=2)
def _urmareste():
    v = db.versiune()
    if st.session_state.get("_v") is None:
        st.session_state["_v"] = v
    elif v != st.session_state["_v"]:
        st.session_state["_v"] = v
        st.rerun(scope="app")


NAV = {
    "client": [("acasa", "Acasă", ":material/home:"), ("asistent", "Agent", ":material/auto_awesome:"),
               ("solicitare", "Cerere", ":material/add:"), ("mesaje", "Chat", ":material/chat:"),
               ("cont", "Profil", ":material/person:")],
    "mester": [("acasa", "Acasă", ":material/home:"), ("solicitari", "Cereri", ":material/inbox:"),
               ("calendar", "Calendar", ":material/calendar_month:"), ("mesaje", "Chat", ":material/chat:"),
               ("cont", "Profil", ":material/person:")],
    "admin": [("acasa", "Mediere", ":material/gavel:"), ("notificari", "Alerte", ":material/notifications:"),
              ("cont", "Cont", ":material/person:")],
}


def _bara_jos(u, pag):
    nec = logica.total_necitite(u["id"])
    with st.container(key="nav", horizontal=True):
        for p, et, icon in NAV[u["rol"]]:
            label = f"{et} ({nec})" if p == "mesaje" and nec else et
            if st.button(label, icon=icon, key=f"nav_{'nou' if p == 'solicitare' else p}",
                         type="primary" if pag == p else "secondary", width="stretch"):
                if p == "solicitare":
                    st.session_state.pop("mester_tinta", None)
                st.session_state["istoric"] = []
                c.go(p, push=False)


def _clopotel(u):
    n = logica.notificari_necitite(u["id"])
    if n:
        with st.container(horizontal=True, horizontal_alignment="right", key="bell"):
            if st.button(f"{n} notificări noi", icon=":material/notifications_active:", key="link_bell",
                         type="tertiary"):
                c.go("notificari")


def main():
    if st.query_params.get("mod") == "prezentare" and config.MOD_PREZENTARE and config.DEMO_LOGIN:
        prezentare.ecran()
        return

    # 1. sesiunea demo din adresă (?s=...), folosită și de telefoanele din modul de prezentare
    u = logica.user_din_sesiune(st.query_params.get("s")) if config.DEMO_LOGIN else None
    # 2. login-ul securizat prin Auth0
    if not u and autentificare.activ():
        u = autentificare.user_curent()
        if not u and autentificare.logat():
            comun.profil_nou()
            return
    c.arata_toast()
    if not u:
        comun.autentificare()
        return

    pag, id_ = c.pagina()
    if not u["ghid_vazut"] and u["rol"] != "admin" and pag != "ghid":
        pag = "ghid"
    st.session_state.pop("_avert_sim", None)
    logica.elibereaza_scadente()

    rol = u["rol"]
    if pag not in ("ghid", "chat", "lucrare", "solicitare", "mester", "notificari", "feedback", "noutati", "sos",
                   "asistent"):
        _clopotel(u)

    ecrane = {
        "ghid": lambda: comun.ghid(u),
        "notificari": lambda: comun.notificari(u),
        "mesaje": lambda: comun.mesaje(u),
        "chat": lambda: comun.chat(u, id_),
        "mester": lambda: comun.profil_mester(u, id_),
        "cont": lambda: comun.cont(u),
        "feedback": lambda: comunitate.feedback(u),
        "noutati": lambda: comunitate.noutati(u),
        "lucrare": lambda: lucrare.ecran(u, id_),
        "sos": lambda: sos.ecran(u, id_),
    }
    if rol == "client":
        ecrane.update({"acasa": lambda: client.acasa(u), "cauta": lambda: client.cauta(u),
                       "solicitare": lambda: client.solicitare(u), "lucrari": lambda: client.lucrari(u),
                       "asistent": lambda: asistent.ecran(u)})
    elif rol == "mester":
        ecrane.update({"acasa": lambda: mester.acasa(u), "solicitari": lambda: mester.solicitari(u),
                       "calendar": lambda: mester.calendar(u)})
    else:
        ecrane.update({"acasa": lambda: admin.panou(u)})

    ecrane.get(pag, ecrane["acasa"])()

    if pag != "ghid":
        _bara_jos(u, pag)
    st.session_state["_v"] = db.versiune()
    _urmareste()


main()
