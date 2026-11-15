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
        media = c.media_client("ag")
        with st.container(horizontal=True):
            for ex in ("Baia renovată până pe 20 decembrie, buget 9000 lei", "Picură robinetul", "Nu merge priza"):
                if st.button(ex, key=f"ag_ex_{ex}", type="tertiary"):
                    st.session_state["ag_txt_val"] = ex
        if st.button("Analizează", type="primary", width="stretch", key="ag_go", icon=":material/auto_awesome:"):
            text = txt or st.session_state.get("ag_txt_val", "")
            if not text and not poza and not media:
                st.error("Scrie ce vrei să rezolvi sau pune o poză.")
            else:
                with st.spinner("Agentul analizează..."):
                    st.session_state["ag_plan"] = ai.planifica(text or "(vezi înregistrarea)",
                                                               poza.getvalue() if poza else None,
                                                               poza.type if poza else "image/jpeg", media)
                    st.session_state["ag_plan"]["_text"] = text
    if st.session_state.get("ag_txt_val") and not st.session_state.get("ag_plan"):
        with st.spinner("Agentul analizează..."):
            _t = st.session_state.pop("ag_txt_val")
            st.session_state["ag_plan"] = ai.planifica(_t)
            st.session_state["ag_plan"]["_text"] = _t
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
    if plan.get("calcule"):
        with st.expander(f"Cum am calculat · {len(plan['calcule'])} calcule cu uneltele Gemini", icon=":material/calculate:"):
            for j in plan["calcule"]:
                r = j.get("rezultat") or {}
                if "total_min" in r:
                    val = f'{r["total_min"]}–{r["total_max"]} lei'
                elif "total_client" in r:
                    val = f'{r["total_client"]} lei cu protecția'
                elif "total" in r:
                    val = f'{r["total"]} lei'
                elif "pret_min" in r:
                    val = f'{r["pret_min"]}–{r["pret_max"]} lei/{r.get("unitate", "buc")}'
                elif "interval_obisnuit" in r:
                    val = f'{r["interval_obisnuit"][0]}–{r["interval_obisnuit"][1]} lei ({r.get("lucrari", 0)} lucrări)'
                else:
                    val = "—"
                ce = r.get("lucrare") or r.get("material") or r.get("meserie") or ""
                cant = f' · {r["cantitate"]} {r.get("unitate", "")}' if r.get("cantitate") else ""
                c.h(f'<div class="sk-between sk-cap" style="padding:4px 0"><span><b>{c.esc(j["nume"])}</b> · '
                    f'{c.esc(str(ce))}{c.esc(cant)}</span><span>{c.esc(val)}</span></div>')
                if r.get("surse"):
                    c.h('<div class="sk-cap" style="padding:0 0 6px 10px">Surse: ' + ", ".join(
                        f'<a href="{c.esc(x["url"])}" target="_blank">{c.esc(x["titlu"])}</a>' for x in r["surse"])
                        + "</div>")
    if plan.get("sfat"):
        c.alerta(c.esc(plan["sfat"]), "ai", "info")
    st.caption(f"Plătești doar ofertele acceptate, cu banii blocați până confirmi. Taxa de protecție "
               f"{config.PCT_PROTECTIE} finanțează mediatorii umani.")
    if len(etape) > 1:
        _echipa(u, plan)
        return
    eticheta = "Creează cererea" if len(etape) == 1 else f"Creează {len(etape)} cereri, câte una pe etapă"
    if st.button(eticheta, type="primary", width="stretch", key="ag_creeaza", icon=":material/send:"):
        try:
            ids = logica.creeaza_etape(u, plan)
            st.session_state.pop("ag_plan", None)
            c.toast("Cererile au plecat la meșterii potriviți." if len(ids) > 1 else "Cererea a plecat.")
            c.go("lucrare", ids[0]) if len(ids) == 1 else c.go("lucrari")
        except Eroare as e:
            st.error(str(e))


def _termen_buget(plan):
    from datetime import date
    termen, buget = logica.citeste_termen_buget(plan.get("_text", ""))
    try:
        termen = date.fromisoformat(plan["termen"]) if plan.get("termen") else termen
    except (TypeError, ValueError):
        pass
    if isinstance(plan.get("buget"), (int, float)) and plan["buget"] > 0:
        buget = float(plan["buget"])
    return termen, buget


def _echipa(u, plan):
    """O propoziție, o echipă întreagă: meșterii aleși și programați în ordinea corectă."""
    from core import timp
    if "_echipa" not in plan:
        termen, buget = _termen_buget(plan)
        plan["_echipa"] = logica.echipa_instant(u, plan, termen, buget)
    e = plan["_echipa"]
    et = e["etape"]
    c.h('<div class="sk-label" style="margin-top:14px">Echipa ta, programată de agent</div>')
    chips = []
    if e["gata_la"]:
        ok = e["in_termen"]
        culoare = "ok" if ok in (True, None) else "danger"
        extra = "" if ok is None else (f" · în termen ({timp.zi_frumos(e['termen'], True)})" if ok
                                       else f" · după termen ({timp.zi_frumos(e['termen'], True)})")
        chips.append(f'<span class="sk-badge {culoare}">Gata {timp.zi_frumos(e["gata_la"], True)}{extra}</span>')
    if e["buget"]:
        chips.append(f'<span class="sk-badge {"ok" if e["in_buget"] else ("urgent" if not e["peste_buget"] else "danger")}">'
                     f'Buget {c.lei(e["buget"])}: ' + ("încadrat" if e["in_buget"] else
                     (f"depășești cu {c.lei(e['peste_buget'])}" if e["peste_buget"] else "la limită")) + "</span>")
    c.h('<div class="sk-row" style="flex-wrap:wrap;gap:6px">' + "".join(chips) + "</div>")
    starturi = [x["start"].date() for x in et if x["start"]]
    if starturi:
        t0 = min(starturi)
        span = max(1, (e["gata_la"] - t0).days + 1)
        rows = ""
        for i, x in enumerate(et, 1):
            m = x["mester"]
            if not m:
                rows += (f'<div class="sk-step"><span class="sk-step-n">{i}</span><div class="sk-grow">'
                         f'<b class="sk-b">{c.esc(x["etapa"]["titlu"])}</b><div class="sk-cap">Niciun meșter liber '
                         f'în următoarele 60 de zile. Cererea pleacă la toți meșterii din zonă.</div></div></div>')
                continue
            alt = f" · încă {x['alternative']} variante" if x.get("alternative") else ""
            st0 = (x["start"].date() - t0).days / span * 100
            lat = max(4, ((x["final"] - x["start"].date()).days + 1) / span * 100)
            per = timp.zi_frumos(x["start"], True) + ("" if x["zile"] == 1 else f" – {timp.zi_frumos(x['final'], True)}")
            rows += (f'<div class="sk-step"><span class="sk-step-n">{i}</span><div class="sk-grow">'
                     f'<div class="sk-between"><b class="sk-b">{c.esc(x["etapa"]["titlu"])}</b>'
                     f'<span class="sk-cap">{c.esc(per)}</span></div>'
                     f'<div class="sk-cap">{c.esc(m["nume"])} · Trust {m["scor"]} · ora 08:00'
                     f'{alt}</div>'
                     f'<div style="position:relative;height:8px;background:var(--sk-surface-2);border-radius:99px;'
                     f'margin-top:6px"><div style="position:absolute;left:{st0:.1f}%;width:{lat:.1f}%;top:0;bottom:0;'
                     f'background:var(--sk-primary);border-radius:99px"></div></div></div></div>')
        c.h(f'<div class="sk-steps">{rows}</div>')
    if e["buget"] and not e["in_buget"] and plan.get("taieri"):
        c.alerta("Ca să intri în buget:<br>" + "<br>".join(f"• {c.esc(t)}" for t in plan["taieri"][:3]), "ai", "wallet")
    st.caption("Fiecare meșter primește cererea cu ziua propusă și confirmă printr-o ofertă. Plătești fiecare etapă "
               "separat, cu banii blocați până confirmi.")
    n = sum(1 for x in et if x["mester"])
    if st.button(f"Trimite cererile echipei ({n} meșteri)", type="primary", width="stretch", key="ag_echipa",
                 icon=":material/groups:"):
        try:
            ids = logica.rezerva_echipa(u, plan, e)
            st.session_state.pop("ag_plan", None)
            c.toast(f"Am trimis {len(ids)} cereri, câte una pe etapă, cu ziua propusă.")
            c.go("lucrari")
        except Eroare as ex:
            st.error(str(ex))
