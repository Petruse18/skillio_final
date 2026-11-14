"""Agentul clientului: explică problema, dă costul așteptat și împarte lucrările mari în etape.
La final creează singur câte o cerere pentru fiecare etapă."""
import streamlit as st

from core import config, logica
from core.logica import Eroare
from services import ai
from ui import comp as c


def ecran(u):
    c.bara_sus("Agentul tău", "acasa")
    c.h('<div class="sk-title">Ce vrei să rezolvi?</div><div class="sk-b" style="color:var(--sk-muted)">'
        'Spune-mi cu cuvintele tale. Îți explic, îți spun cât costă și organizez meșterii, etapă cu etapă.</div>')
    with st.container(key="card_agent"):
        txt = st.text_area("Descriere", key="ag_txt", height=90, label_visibility="collapsed",
                           placeholder="Ex: Vreau să renovez baia complet, e din 1985.")
        poza = st.file_uploader("Poză (opțional)", type=["jpg", "jpeg", "png"], key="ag_poza")
        with st.container(horizontal=True):
            for ex in ("Renovez baia", "Picură robinetul", "Nu merge priza"):
                if st.button(ex, key=f"ag_ex_{ex}", type="tertiary"):
                    st.session_state["ag_txt_val"] = ex
        if st.button("Analizează", type="primary", width="stretch", key="ag_go", icon=":material/auto_awesome:"):
            text = txt or st.session_state.get("ag_txt_val", "")
            if not text and not poza:
                st.error("Scrie ce vrei să rezolvi sau pune o poză.")
            else:
                with st.spinner("Agentul analizează..."):
                    st.session_state["ag_plan"] = ai.planifica(text, poza.getvalue() if poza else None,
                                                               poza.type if poza else "image/jpeg")
    if st.session_state.get("ag_txt_val") and not st.session_state.get("ag_plan"):
        with st.spinner("Agentul analizează..."):
            st.session_state["ag_plan"] = ai.planifica(st.session_state.pop("ag_txt_val"))
    plan = st.session_state.get("ag_plan")
    if not plan:
        return
    etape = plan.get("etape", [])
    c.h(f'<div class="sk-card flat"><div class="sk-label">Ce am înțeles</div><div class="sk-b">'
        f'{c.esc(plan.get("explicatie", ""))}</div><div class="sk-between" style="margin-top:8px">'
        f'<span class="sk-cap">Cost estimat total</span><span class="sk-price">{plan.get("pret_min")}–'
        f'{plan.get("pret_max")} lei</span></div></div>')
    c.asculta(plan.get("explicatie", ""), "ag_voce")
    if len(etape) > 1:
        c.h(f'<div class="sk-label">{len(etape)} etape, în ordinea corectă</div>')
    rows = "".join(
        f'<div class="sk-step"><span class="sk-step-n">{i}</span><div class="sk-grow"><div class="sk-between">'
        f'<b class="sk-b">{c.esc(e["titlu"])}</b><span class="sk-cap">{e.get("pret_min")}–{e.get("pret_max")} lei'
        f'</span></div><div class="sk-cap">{c.esc(c.meserie_nume(e["meserie"]))} · {c.esc(e.get("descriere", ""))}'
        f'</div></div></div>' for i, e in enumerate(etape, 1))
    c.h(f'<div class="sk-steps">{rows}</div>')
    if plan.get("sfat"):
        c.alerta(c.esc(plan["sfat"]), "ai", "info")
    st.caption(f"Plătești doar ofertele acceptate, cu banii blocați până confirmi. Taxa de protecție "
               f"{config.PCT_PROTECTIE} finanțează mediatorii umani.")
    eticheta = "Creează cererea" if len(etape) == 1 else f"Creează {len(etape)} cereri, câte una pe etapă"
    if st.button(eticheta, type="primary", width="stretch", key="ag_creeaza", icon=":material/send:"):
        try:
            ids = logica.creeaza_etape(u, plan)
            st.session_state.pop("ag_plan", None)
            c.toast("Cererile au plecat la meșterii potriviți." if len(ids) > 1 else "Cererea a plecat.")
            c.go("lucrare", ids[0]) if len(ids) == 1 else c.go("lucrari")
        except Eroare as e:
            st.error(str(e))
