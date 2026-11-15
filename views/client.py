"""Ecranele clientului: acasă, căutare, solicitare nouă (cu asistentul AI), lucrările mele."""
import streamlit as st

from core import config, logica, timp
from core.logica import Eroare
from services import ai, geo
from ui import comp as c
from ui import harta


# ---------------------------------------------------------------------------
# Acasă
# ---------------------------------------------------------------------------
def acasa(u):
    prenume = u["nume"].split()[0]
    c.h(f'<div class="sk-cap">{c.ico("pin", 12)} {c.esc(u["cartier"])}, {config.ORAS}</div>'
        f'<div class="sk-title">Salut, {c.esc(prenume)}!</div>'
        f'<div class="sk-b" style="color:var(--sk-muted)">Ce reparăm azi?</div>')

    with st.container(horizontal=True, vertical_alignment="bottom", key="cauta_bar"):
        txt = st.text_input("Caută", placeholder="Caută un meșter sau un serviciu", label_visibility="collapsed",
                            key="home_q")
        if st.button("", icon=":material/search:", key="home_q_btn", type="primary"):
            st.session_state["f_text"] = txt
            st.session_state["f_meserie"] = None
            c.go("cauta")
    if txt and txt != st.session_state.get("_home_q_prev"):
        st.session_state["_home_q_prev"] = txt
        st.session_state["f_text"] = txt
        st.session_state["f_meserie"] = None
        c.go("cauta")

    # Lucrarea următoare (cardul verde din design)
    urm = sorted([l for l in logica.lucrari_client(u["id"]) if l["status"] in ("de_plata", "programata", "sosit", "gata")
                  and l["programat_la"]], key=lambda l: l["programat_la"])
    if urm:
        l = urm[0]
        bani = logica.bani_lucrare(l["id"])["blocat"]
        m = logica.user(l["mester_id"]) if l["mester_id"] else None
        cand = timp.din_iso(l["programat_la"])
        c.h(c.card_hero(f'Lucrarea ta {timp.zi_frumos(cand.date())} · {timp.ora(cand)}',
                        f'{m["nume"] if m else "Meșterul"} · {l["titlu"]} · {logica.STATUS[l["status"]][0]}', bani))
        if st.button("Deschide lucrarea", key="link_hero", type="tertiary"):
            c.go("lucrare", l["id"])

    # Promisiunea: clientul nu riscă nimic
    c.h(f'<div class="sk-promise"><div class="sk-promise-t">Tu nu riști nimic.</div><div class="sk-promise-l">'
        f'<span>Bani blocați până confirmați amândoi</span><span>Preț reconfirmat cu poză, la fața locului</span>'
        f'<span>Mediator uman la orice dispută</span><span>Numărul tău rămâne privat</span></div></div>')

    # Agentul clientului
    with st.container(key="card_ai"):
        c.h(f'<div class="sk-row">{c.ico("sparkles", 22)}<div class="sk-grow"><div class="sk-h">Agentul tău</div>'
            f'<div class="sk-cap">Îi spui ce vrei. Îți explică, îți dă costul și organizează meșterii, etapă cu etapă.'
            f'</div></div></div>')
        with st.container(horizontal=True):
            if st.button("Vorbește cu agentul", type="primary", width="stretch", key="home_ai"):
                c.go("asistent")
            if st.button("Cerere rapidă", width="stretch", key="home_cerere"):
                st.session_state.pop("mester_tinta", None)
                c.go("solicitare")
    from views import sos
    sos.card_acasa(u)

    # Feedback scadent: lucrarea mai ține?
    for f in logica.feedback_de_dat(u["id"]):
        if f["etapa"] == "final":
            continue
        _card_durabilitate(u, f)

    # Categorii
    c.h('<div class="sk-label">Categorii</div>')
    chei = list(config.MESERII)
    for i, rand in enumerate((chei[:4], chei[4:])):
        with st.container(horizontal=True, gap="small", key=f"cats{i}", wrap=False):
            for k in rand:
                m = config.MESERII[k]
                if st.button(m["scurt"], icon=f":material/{m['icon']}:", key=f"cat_{k}", width="stretch"):
                    st.session_state["f_meserie"] = k
                    st.session_state["f_text"] = ""
                    c.go("cauta")

    # Solicitările active
    active = [l for l in logica.lucrari_client(u["id"]) if l["status"] in logica.ACTIVE]
    if active:
        c.h('<div class="sk-label">Solicitările tale active</div>')
        for l in active[:3]:
            _card_lucrare(l, f"home_{l['id']}")

    toti = logica.mesteri(lat=u["lat"], lon=u["lon"])
    recomandati = [m for m in toti if m["disponibil"]][:3]
    if recomandati:
        c.h('<div class="sk-label">Meșteri recomandați pentru tine</div>')
        for m in recomandati:
            _card_mester(m, f"rec_{m['id']}")

    top = sorted(toti, key=lambda m: -m["trust"]["scor"])[:4]
    c.h('<div class="sk-label">Cele mai bine evaluați</div>')
    for m in top:
        with st.container(horizontal=True, vertical_alignment="center", key=f"cardflat_top_{m['id']}"):
            c.h(f'<div class="sk-row">{c.avatar(m)}<div class="sk-grow"><b class="sk-b">{c.esc(m["nume"])}</b>'
                f'<div class="sk-cap">{c.esc(c.meserie_nume(m["meserii_l"][0]))} · {c.stele(m["trust"]["medie"])}'
                f'</div></div>{c.trust_pill(m["trust"]["scor"])}</div>')
            if st.button("", icon=":material/chevron_right:", key=f"top_{m['id']}", type="tertiary"):
                c.go("mester", m["id"])


def _card_durabilitate(u, f):
    with st.container(key=f"cardsel_fb{f['id']}"):
        c.h(f'<div class="sk-row">{c.ico("clock", 20)}<div class="sk-grow"><div class="sk-h">'
            f'{logica.ETAPE[f["etapa"]][0]}: {c.esc(f["titlu"])}</div><div class="sk-b">{logica.INTREBARI[f["etapa"]]}'
            f'</div></div></div>')
        com = st.text_input("Comentariu (opțional)", key=f"fbc_{f['id']}", label_visibility="collapsed",
                            placeholder="Comentariu (opțional)")
        with st.container(horizontal=True):
            if st.button("Da, totul e bine", type="primary", key=f"fbok_{f['id']}", width="stretch"):
                logica.raspunde_durabilitate(f["id"], u["id"], True, com)
                c.toast("Mulțumim! Răspunsul tău contează în Trust Score-ul meșterului.")
                st.rerun()
            if st.button("Au apărut probleme", key=f"fbno_{f['id']}", width="stretch"):
                logica.raspunde_durabilitate(f["id"], u["id"], False, com)
                c.toast("Am anunțat meșterul. Îi poți scrie în chat.", "⚠️")
                st.rerun()


def _card_mester(m, key):
    with st.container(key=f"card_{key}"):
        c.h(c.card_mester(m))
        if st.button("Vezi profilul", key=f"vezi_{key}", width="stretch"):
            c.go("mester", m["id"])


def _card_lucrare(l, key):
    urg = c.badge_urgent() if l["urgent"] else ""
    extra = ""
    if l["status"] == "deschisa":
        n = logica.db.val("SELECT COUNT(*) FROM oferte WHERE lucrare_id = ? AND status = 'trimisa'", (l["id"],), 0)
        extra = f'<span class="sk-cap">{n} {"ofertă" if n == 1 else "oferte"}</span>'
    elif l["programat_la"]:
        extra = f'<span class="sk-cap">{c.ico("cal", 12)} {timp.data_ora(l["programat_la"])}</span>'
    with st.container(key=f"card{'urg' if l['urgent'] and l['status'] == 'deschisa' else ''}_{key}"):
        c.h(f'<div class="sk-between"><div class="sk-h">{c.esc(l["titlu"])}</div>{c.badge_status(l["status"])}</div>'
            f'<div class="sk-between"><div class="sk-badges"><span class="sk-badge">{c.meserie_nume(l["meserie"])}'
            f'</span>{urg}</div>{extra}</div>')
        if st.button("Deschide", key=f"open_{key}", width="stretch"):
            c.go("lucrare", l["id"])


# ---------------------------------------------------------------------------
# Căutare și filtre
# ---------------------------------------------------------------------------
SORTARI = {"potrivire": "Recomandați", "distanta": "Cei mai apropiați", "trust": "Trust Score",
           "rating": "Evaluare", "pret": "Preț orientativ", "experienta": "Experiență"}


def cauta(u):
    c.h('<div class="sk-title">Caută meșteri</div>')
    txt = st.text_input("Caută", value=st.session_state.get("f_text", ""), placeholder="Nume, serviciu, cartier",
                        label_visibility="collapsed", key="f_text_in")
    st.session_state["f_text"] = txt
    meserii = [None] + list(config.MESERII)
    mes = st.pills("Serviciu", meserii, default=st.session_state.get("f_meserie"),
                   format_func=lambda k: "Toate" if k is None else f'{config.MESERII[k]["emoji"]} {c.meserie_nume(k)}',
                   key="f_mes_pills", label_visibility="collapsed")
    st.session_state["f_meserie"] = mes
    with st.expander("Filtre și sortare"):
        dist = st.slider("Distanță maximă (km)", 1, 20, 10, key="f_dist")
        disp = st.toggle("Doar disponibili acum", True, key="f_disp")
        scor = st.slider("Trust Score minim", 0, 100, 0, step=5, key="f_scor")
        rating = st.slider("Evaluare minimă", 0.0, 5.0, 0.0, step=0.5, key="f_rating")
        pret = st.slider("Preț orientativ maxim (lei/oră)", 40, 150, 150, step=5, key="f_pret")
        exp = st.slider("Experiență minimă (ani)", 0, 20, 0, key="f_exp")
        sort = st.selectbox("Sortează după", list(SORTARI), format_func=SORTARI.get, key="f_sort")
    st_ = st.session_state
    rez = logica.mesteri(meserie=mes, lat=u["lat"], lon=u["lon"], max_km=st_.get("f_dist", 10),
                         doar_disponibili=st_.get("f_disp", True), scor_minim=st_.get("f_scor", 0),
                         pret_max=st_.get("f_pret", 150) if st_.get("f_pret", 150) < 150 else None,
                         exp_min=st_.get("f_exp", 0), rating_min=st_.get("f_rating", 0), text=txt,
                         sortare=st_.get("f_sort", "potrivire"))
    vedere = "Listă"
    st.caption(f"{len(rez)} meșteri găsiți")
    if not rez:
        c.gol("Niciun meșter nu se potrivește filtrelor. Mărește distanța sau scoate filtrul „Doar disponibili”.")
        return
    if vedere == "Hartă":
        ales = harta.harta_mesteri(rez, u["lat"], u["lon"], key="cauta_map", inaltime=420)
        st.caption("Atinge un pin ca să deschizi profilul.")
        if ales:
            c.go("mester", ales)
    else:
        for m in rez:
            _card_mester(m, f"r_{m['id']}")


# ---------------------------------------------------------------------------
# Solicitare nouă, cu asistentul AI
# ---------------------------------------------------------------------------
URGENTE = {"urgent": "Urgent, azi", "azi": "Azi sau mâine", "saptamana": "Săptămâna asta", "flexibil": "Flexibil"}


def solicitare(u):
    c.bara_sus("Solicitare nouă", "acasa")
    tinta = st.session_state.get("mester_tinta")
    if tinta:
        mt = logica.user(tinta)
        c.alerta(f"Solicitarea ajunge întâi la <b>{c.esc(mt['nume'])}</b>, apoi și la alți meșteri potriviți.",
                 "ai", "info")

    d = st.session_state.get("sol_diag")
    if not d:
        c.h('<div class="sk-label">1. Ce s-a stricat?</div>')
        text = st.text_area("Descrie problema", placeholder="Ex: Curge apă de sub chiuveta din baie de "
                            "azi-dimineață, pe jos e o baltă.", key="sol_text", height=110,
                            label_visibility="collapsed")
        foto = st.file_uploader("Adaugă o poză (opțional, ajută mult)", type=["jpg", "jpeg", "png"], key="sol_foto")
        media = c.media_client("sol")
        if st.button("Analizează cu AI", type="primary", width="stretch", key="sol_analiza", icon=":material/auto_awesome:",
                     disabled=not (text or "").strip() and foto is None and not media):
            with st.spinner("Asistentul analizează problema…"):
                d = ai.diagnosticheaza(text or "(vezi înregistrarea)", foto.getvalue() if foto else None,
                                       foto.type if foto else "image/jpeg", media)
            if st.session_state.get("sol_meserie") and tinta:
                mt = logica.user(tinta)
                if d["meserie"] not in logica.meserii_lista(mt):
                    d["meserie"] = st.session_state["sol_meserie"]
            st.session_state["sol_diag"] = d
            st.session_state["sol_poza"] = logica.salveaza_poza(foto, "sol") if foto else None
            st.session_state["sol_descriere"] = text or d.get("descriere", "")
            st.rerun()
        st.caption("Asistentul te ajută să alegi meseria, dar evaluarea finală o face meșterul.")
        return

    # 2. Rezultatul asistentului
    m = config.MESERII[d["meserie"]]
    sursa = "Gemini" if d.get("sursa") == "gemini" else "asistent (mod offline)"
    mat = "".join(f'<span class="sk-chip">{c.esc(x)}</span>' for x in d["materiale"])
    intreb = "".join(f"<li>{c.esc(q)}</li>" for q in d.get("intrebari", []))
    with st.container(key="card_diag"):
        c.h(f'<div class="sk-row top"><div class="sk-av" style="background:var(--sk-primary-soft)">{c.ico("sparkles")}'
            f'</div><div class="sk-grow"><div class="sk-h">{m["emoji"]} {c.esc(m["nume"])}</div><div class="sk-cap">'
            f'{c.esc(d["descriere"])}</div></div></div>'
            + c.kv([("Preț orientativ", f'{d["pret_min"]} – {d["pret_max"]} lei'),
                    ("Durată estimată", f'~{d["durata_min"]} min'), ("Urgență", URGENTE[d["urgenta"]])])
            + f'<div class="sk-label">Meșterul ar trebui să aducă</div><div class="sk-chips">{mat}</div>'
            + (f'<div class="sk-label">Ar ajuta să știm</div><ul style="margin:0;padding-left:18px" class="sk-b">'
               f'{intreb}</ul>' if intreb else "")
            + f'<div class="sk-cap">Analiză: {sursa} · încredere {d.get("incredere", .5):.0%}</div>')
    c.alerta(f'<b>Până vine meșterul:</b> {c.esc(d["sfat_siguranta"])}', "escrow", "alert")
    c.asculta(f'Ai nevoie de un {m["nume"].lower()}. {d["descriere"]} Prețul orientativ e între {d["pret_min"]} și '
              f'{d["pret_max"]} de lei, iar lucrarea durează cam {d["durata_min"]} de minute. '
              f'Până vine meșterul: {d["sfat_siguranta"]}', "diag")
    if st.session_state.get("sol_poza"):
        c.poza(st.session_state["sol_poza"], 150)

    # 3. Detaliile solicitării
    c.h('<div class="sk-label">2. Detalii solicitare</div>')
    chei = list(config.MESERII)
    meserie = st.selectbox("Categorie", chei, index=chei.index(d["meserie"]), format_func=c.meserie_nume,
                           key="sol_meserie_sel")
    titlu = st.text_input("Titlu", d["titlu"], key="sol_titlu")
    descriere = st.text_area("Descriere", st.session_state.get("sol_descriere") or d["descriere"], key="sol_desc",
                             height=90)
    adresa = st.text_input("Adresa", u["adresa"] or "", key="sol_adresa")
    cartier = st.selectbox("Cartier", list(config.CARTIERE), index=list(config.CARTIERE).index(u["cartier"])
                           if u["cartier"] in config.CARTIERE else 0, key="sol_cartier")
    buget = st.number_input("Buget orientativ (lei, opțional)", 0, 20000, int(d["pret_max"]), step=10, key="sol_buget")
    with st.container(key="cardurg_urgent" if st.session_state.get("sol_urgent") else "cardflat_urgent"):
        urgent = st.toggle(f"Urgent (+{config.PCT_URGENT})", value=d["urgenta"] == "urgent", key="sol_urgent")
        st.caption(f"Meșterii văd solicitarea ta prima. Prețul crește cu {config.PCT_URGENT}, iar diferența merge la meșter.")
    with st.container(horizontal=True):
        if st.button("Reia analiza", key="sol_reset", width="stretch"):
            for k in ("sol_diag", "sol_poza", "sol_descriere"):
                st.session_state.pop(k, None)
            st.rerun()
        if st.button("Trimite solicitarea", type="primary", key="urg_sol_send" if urgent else "sol_send",
                     width="stretch"):
            try:
                d["urgenta"] = "urgent" if urgent else d["urgenta"]
                lid, n = logica.creeaza_lucrare(u["id"], titlu, descriere, adresa, cartier, meserie, urgent, buget,
                                                st.session_state.get("sol_poza"), d, tinta)
                for k in ("sol_diag", "sol_poza", "sol_descriere", "mester_tinta", "sol_meserie", "sol_text"):
                    st.session_state.pop(k, None)
                if adresa.strip() and not u["adresa"]:
                    logica.actualizeaza_profil(u["id"], adresa=adresa)
                c.toast(f"Solicitare trimisă la {n} meșteri. Ofertele apar aici.")
                c.go("lucrare", lid, push=False)
            except Eroare as e:
                st.error(str(e))


# ---------------------------------------------------------------------------
# Lucrările mele
# ---------------------------------------------------------------------------
def lucrari(u):
    c.h('<div class="sk-title">Lucrările mele</div>')
    toate = logica.lucrari_client(u["id"])
    active = [l for l in toate if l["status"] in logica.ACTIVE]
    istoric = [l for l in toate if l["status"] not in logica.ACTIVE]
    t1, t2 = st.tabs([f"Active ({len(active)})", f"Istoric ({len(istoric)})"])
    with t1:
        if not active:
            c.gol("Nu ai solicitări active.")
            if st.button("Începe o solicitare", type="primary", width="stretch", key="lucr_nou"):
                c.go("solicitare")
        for l in active:
            _card_lucrare(l, f"a{l['id']}")
    with t2:
        if not istoric:
            c.gol("Lucrările terminate apar aici.")
        for l in istoric:
            _card_lucrare(l, f"i{l['id']}")
