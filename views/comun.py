"""Ecrane comune: intrare în cont, ghid, notificări, mesaje, chat, profilul public al meșterului, contul meu."""
import streamlit as st

from core import config, db, logica, timp, trust
from core.logica import Eroare
from services import autentificare as autentificare_srv
from services import ai, geo, solana, stocare
from ui import comp as c

# ---------------------------------------------------------------------------
# Intrare în cont (fără parolă: numărul e verificat de rețea)
# ---------------------------------------------------------------------------
DEMO = [("Ana · client", "+40722000001"), ("Ionel · meșter", "+40722000101"), ("Admin", "+40700000000")]


def _logheaza(uid):
    token = logica.sesiune_noua(uid)
    st.query_params.clear()
    st.query_params["s"] = token
    st.query_params["p"] = "acasa"
    st.session_state.pop("istoric", None)
    st.rerun()


def autentificare():
    c.h(f'<div class="sk-col" style="align-items:center;text-align:center;padding:18px 0 4px">'
        f'{c.logo(72)}<div style="margin-top:6px">{c.wordmark(34)}</div>'
        f'<div class="sk-b" style="color:var(--sk-muted)">{config.SLOGAN}<br>Meșteri de încredere din '
        f'{config.ORAS}, cu plata blocată până confirmi.</div></div>')

    if autentificare_srv.activ():
        if st.button("Intră în cont", type="primary", width="stretch", key="auth0_btn", icon=":material/login:"):
            autentificare_srv.intra()
        c.alerta("Login securizat prin <b>Auth0</b>: cod pe email sau SMS, ori contul Google. "
                 "Nu păstrăm nicio parolă.", "trust", "shield")
    if not config.DEMO_LOGIN:
        if not autentificare_srv.activ():
            st.error("Login-ul nu e configurat. Adaugă datele Auth0 în .streamlit/secrets.toml "
                     "sau pune DEMO_LOGIN=1 în .env.")
        return
    if autentificare_srv.activ():
        st.space("small")
        st.caption("Mod demo, pentru prezentare (se oprește cu DEMO_LOGIN=0)")
    _intrare_demo()


def _intrare_demo():
    tab_in, tab_nou = st.tabs(["Intră cu telefonul", "Cont nou"])
    with tab_in:
        tel = st.text_input("Număr de telefon", placeholder="07xx xxx xxx", key="login_tel")
        c.alerta("Numărul tău rămâne privat: nu îl vede niciun meșter și niciun client.", "trust", "shield")
        if st.button("Continuă", type="primary" if not autentificare_srv.activ() else "secondary", width="stretch",
                     key="login_btn"):
            try:
                uid, mod, schimbat = logica.intra(tel)
                if schimbat:
                    st.session_state["_avert_sim"] = True
                _logheaza(uid)
            except Eroare as e:
                st.error(str(e))
        st.caption("Conturi demo pentru prezentare")
        with st.container(horizontal=True):
            for et, t in DEMO:
                if st.button(et, key=f"demo_{t}", width="stretch"):
                    uid, _, _ = logica.intra(t)
                    _logheaza(uid)

    with tab_nou:
        _formular_cont("reg")


def _formular_cont(k, info=None):
    """Formularul de cont nou. Cu info (de la Auth0), contul se leagă de login-ul Auth0."""
    info = info or {}
    rol = st.segmented_control("Sunt", ["Client", "Meșter"], default="Client", key=f"{k}_rol", width="stretch")
    nume = st.text_input("Nume și prenume", info.get("nume", ""), key=f"{k}_nume")
    tel = st.text_input("Număr de telefon", info.get("telefon", ""), placeholder="07xx xxx xxx", key=f"{k}_tel")
    cartier = st.selectbox("Cartier", list(config.CARTIERE), key=f"{k}_cartier")
    adresa = st.text_input("Adresa (stradă, număr)", key=f"{k}_adresa") if rol != "Meșter" else ""
    meserii = []
    if rol == "Meșter":
        meserii = st.multiselect("Meserii", list(config.MESERII), format_func=c.meserie_nume, key=f"{k}_meserii")
    if st.button("Creează contul", type="primary", width="stretch", key=f"{k}_btn"):
        try:
            rol_db = "mester" if rol == "Meșter" else "client"
            if autentificare_srv.e_admin_dupa_email(info.get("email")):
                rol_db = "admin"
            uid = logica.creeaza_cont(tel, nume, rol_db, cartier, adresa, meserii,
                                      email=info.get("email"), auth_sub=info.get("sub"))
            if info:
                st.query_params.clear()
                st.query_params["p"] = "acasa"
                st.rerun()
            _logheaza(uid)
        except Eroare as e:
            st.error(str(e))


def profil_nou():
    """Prima intrare prin Auth0: omul e logat, dar încă nu are cont SKILLIO."""
    i = autentificare_srv.info()
    c.h(f'<div class="sk-title">Bun venit!</div><div class="sk-b" style="color:var(--sk-muted)">Ești logat ca '
        f'<b>{c.esc(i.get("email") or i.get("nume") or "")}</b>. Mai avem nevoie de câteva date ca să-ți '
        f'facem contul.</div>')
    _formular_cont("auth", i)
    if st.button("Ieși", key="danger_auth_iesi"):
        autentificare_srv.iesi()


# ---------------------------------------------------------------------------
# Ghid interactiv
# ---------------------------------------------------------------------------
GHID = {
    "client": [
        ("leaf", "Bun venit în SKILLIO", "Aici tu nu riști nimic: banii stau blocați până confirmați amândoi, "
                                         "iar numărul tău rămâne privat."),
        ("wrench", "Alege serviciul", "Pe ecranul de start alegi o categorie (instalator, electrician...) sau "
                                      "cauți direct un meșter."),
        ("sparkles", "Vorbește cu agentul", "Spune-i ce vrei. Îți explică, îți dă costul și împarte lucrările mari "
                                            "în etape, cu câte o cerere pentru fiecare."),
        ("shield", "Compară meșterii", "Fiecare meșter are un Trust Score 0-100, calculat din lucrări reale: "
                                       "recenzii, punctualitate, cât rezistă lucrările."),
        ("pin", "Trimite solicitarea", "Solicitarea ajunge la meșterii potriviți din zona ta. Bifează Urgent "
                                       f"(+{config.PCT_URGENT}) dacă nu poate aștepta."),
        ("wallet", "Alege oferta", "Primești oferte cu preț și oră. Alegi una, apoi stabiliți ora împreună."),
        ("lock", "Plătești în siguranță", "Banii rămân blocați. La sosire, meșterul reconfirmă prețul cu o poză: "
                                          f"dacă refuzi, plătești doar deplasarea ({config.TAXA_DEPLASARE} lei)."),
        ("star", "Mediator uman, nu robot", f"După confirmare mai ai {config.FEREASTRA_DISPUTA_ORE} de ore pentru o "
                                            "dispută. O decide un om din echipa SKILLIO."),
    ],
    "mester": [
        ("leaf", "Bun venit în SKILLIO", "Contul tău profesional e gata. Nu plătești pentru lead-uri: doar "
                                         f"{config.PCT_COMISION} din lucrările făcute."),
        ("wrench", "Completează profilul", "Adaugă o descriere, experiența și poze cu lucrări. Clienții aleg mai "
                                           "ușor un profil complet."),
        ("check", "Adaugă specializările", "Alege meseriile tale. Primești doar solicitările care ți se potrivesc."),
        ("cal", "Setează disponibilitatea", "În calendar blochezi orele în care nu lucrezi. Clienții văd doar orele "
                                            "libere."),
        ("pin", "Primește solicitări", f"Le vezi cu poză, descriere și urgență. Cele urgente (+{config.PCT_URGENT}) apar "
                                       "primele."),
        ("wallet", "Trimite oferte", "Pui un preț și o oră. Dacă clientul acceptă, plătește, iar banii sunt "
                                     "blocați pentru tine."),
        ("shield", "Ziua lucrării", "Apeși „Am ajuns” și reconfirmi prețul cu o poză. Dacă clientul refuză, "
                                    f"primești deplasarea ({config.TAXA_DEPLASARE} lei)."),
        ("star", "Construiește-ți reputația", f"Primești banii la {config.FEREASTRA_DISPUTA_ORE} h după confirmare. Și tu poți deschide o dispută. "
                                              "Recenziile și feedback-ul în timp îți ridică Trust Score-ul."),
    ],
}
FAQ = [
    ("Ce e Trust Score?", "Un scor 0-100 calculat doar din activitatea reală din aplicație: recenzii, cât rezistă "
                          "lucrările, programări respectate, punctualitate, lucrări finalizate, "
                          "verificarea identității și reclamații. Fiecare factor e afișat pe profil."),
    ("Când primește meșterul banii?", f"După ce confirmați amândoi, banii mai stau blocați "
                                      f"{config.FEREASTRA_DISPUTA_ORE} de ore. Dacă nimeni nu deschide o dispută, "
                                      f"pleacă automat la meșter."),
    ("Ce se întâmplă dacă prețul se schimbă la fața locului?", f"Meșterul reconfirmă prețul cu o poză și un motiv, "
     f"iar AI-ul îți dă o părere. Dacă refuzi, plătești doar deplasarea ({config.TAXA_DEPLASARE} lei)."),
    ("Cine rezolvă disputele?", f"Un mediator uman din echipa SKILLIO, niciodată un robot. Îl plătește taxa de "
                                f"protecție de {config.PCT_PROTECTIE}."),
    ("Ce e SOS?", f"Pentru {config.SOS_PRET} lei, un meșter te ghidează prin video cu instrucțiuni de siguranță. "
                  f"Apelul se înregistrează cu acordul tău și se șterge după 30 de zile."),
    ("Ce înseamnă Urgent?", f"Lucrarea costă cu {config.PCT_URGENT} mai mult, iar meșterii o văd prima. Cei {config.PCT_URGENT} merg la meșter."),
    ("Ce fac dacă meșterul nu vine?", "La o oră după ora programată poți semnala asta, iar banii se întorc la tine."),
    ("Cum verificați meșterii?", "Actul de identitate e verificat de echipa SKILLIO, iar Trust Score-ul vine "
                                 "doar din lucrări reale. Numerele de telefon rămân ascunse în ambele sensuri."),
]


def ghid(u):
    pasi = GHID["mester" if u["rol"] == "mester" else "client"]
    i = st.session_state.setdefault("ghid_pas", 0)
    icon, titlu, text = pasi[i]
    dots = "".join(f'<i class="{"on" if k == i else ""}"></i>' for k in range(len(pasi)))
    c.h(f'<div class="sk-between"><span class="sk-cap">Ghid · pasul {i + 1} din {len(pasi)}</span></div>'
        f'<div class="sk-progress"><i style="width:{(i + 1) / len(pasi) * 100:.0f}%"></i></div>'
        f'<div class="sk-col" style="align-items:center;text-align:center;padding:36px 8px 12px">'
        f'<div style="width:112px;height:112px;border-radius:32px;background:var(--sk-primary-soft);display:grid;'
        f'place-items:center;color:var(--sk-primary)">{c.ico(icon, 52)}</div>'
        f'<div class="sk-title" style="margin-top:10px">{c.esc(titlu)}</div>'
        f'<div class="sk-b" style="color:var(--sk-muted);max-width:320px">{c.esc(text)}</div></div>'
        f'<div class="sk-dots">{dots}</div>')
    with st.container(horizontal=True):
        if st.button("Pasul anterior", disabled=i == 0, width="stretch", key="ghid_prev"):
            st.session_state.ghid_pas = i - 1
            st.rerun()
        if i < len(pasi) - 1:
            if st.button("Următorul pas", type="primary", width="stretch", key="ghid_next"):
                st.session_state.ghid_pas = i + 1
                st.rerun()
        else:
            if st.button("Începe", type="primary", width="stretch", key="ghid_gata"):
                logica.actualizeaza_profil(u["id"], ghid_vazut=1)
                st.session_state.ghid_pas = 0
                c.go("acasa", push=False)
    if st.button("Sari peste ghid", type="tertiary", key="link_sari"):
        logica.actualizeaza_profil(u["id"], ghid_vazut=1)
        st.session_state.ghid_pas = 0
        c.go("acasa", push=False)
    with st.expander("Întrebări frecvente"):
        for q, a in FAQ:
            st.markdown(f"**{q}**  \n{a}")


# ---------------------------------------------------------------------------
# Notificări
# ---------------------------------------------------------------------------
def notificari(u):
    c.bara_sus("Notificări")
    lst = logica.notificari(u["id"])
    if not lst:
        c.gol("Nu ai notificări încă.")
    for n in lst:
        with st.container(key=f"cardflat_n{n['id']}"):
            c.h(f'<div class="sk-between"><div class="sk-b" style="{"font-weight:700" if not n["citit"] else ""}">'
                f'{c.esc(n["text"])}</div></div><div class="sk-cap">{timp.de_cand(n["creat_la"])}</div>')
            if n["lucrare_id"] and st.button("Deschide", key=f"link_n{n['id']}", type="tertiary"):
                c.go("lucrare", n["lucrare_id"])
    logica.marcheaza_notificari(u["id"])


# ---------------------------------------------------------------------------
# Mesaje și chat
# ---------------------------------------------------------------------------
def mesaje(u):
    c.h('<div class="sk-title">Mesaje</div>')
    conv = logica.conversatii(u["id"])
    if not conv:
        c.gol("Conversațiile apar aici după ce alegi o ofertă sau primești o lucrare.", "info")
    for l in conv:
        o = l["celalalt"]
        ult = l["ultimul"]
        text = (ult["text"] if ult and ult["autor_id"] else (ult["text"] if ult else "")) or "Poză"
        nec = f'<span class="sk-badge ok">{l["necitite"]}</span>' if l["necitite"] else ""
        with st.container(key=f"card_conv{l['id']}"):
            c.h(f'<div class="sk-row">{c.avatar(o)}<div class="sk-grow"><div class="sk-between"><b>{c.esc(o["nume"])}'
                f'</b>{nec}</div><div class="sk-cap">{c.esc(l["titlu"])}</div><div class="sk-b" style="color:'
                f'var(--sk-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{c.esc(text)}</div>'
                f'</div></div>')
            if st.button("Deschide conversația", key=f"conv{l['id']}", width="stretch"):
                c.go("chat", l["id"])


def chat(u, lid):
    l = logica.lucrare(int(lid))
    if not l or u["id"] not in (l["client_id"], l["mester_id"]):
        c.gol("Conversația nu există.")
        return
    alt = logica.user(l["mester_id"] if u["id"] == l["client_id"] else l["client_id"])
    c.bara_sus(alt["nume"] if alt else "Chat")
    c.h(f'<div class="sk-between"><span class="sk-cap">{c.esc(l["titlu"])}</span>{c.badge_status(l["status"])}</div>')
    if st.button("Vezi lucrarea", key="link_vezi_lucr", type="tertiary"):
        c.go("lucrare", l["id"])
    limba = st.selectbox("Limba chatului", list(ai.LIMBI), format_func=lambda k: f"Citesc mesajele în: {ai.LIMBI[k]}",
                         key="limba_chat", label_visibility="collapsed")
    msgs = logica.mesaje(l["id"])
    trad = st.session_state.setdefault("trad_chat", {})
    if limba != "ro":
        lipsa = [m for m in msgs if m["autor_id"] not in (None, u["id"]) and m["text"] and (m["id"], limba) not in trad]
        if lipsa:
            try:
                for m, t in zip(lipsa, ai.traduce([m["text"] for m in lipsa], limba)):
                    trad[(m["id"], limba)] = t
            except Exception:  # noqa: BLE001
                for m in lipsa:
                    trad[(m["id"], limba)] = m["text"]
    bule = []
    for m in msgs:
        poza = (f'<img src="{c.img_uri(m["poza"])}" style="max-width:100%;border-radius:10px;display:block;'
                f'margin-bottom:4px">' if m["poza"] else "")
        if m["autor_id"] is None:
            bule.append(f'<div class="sk-bubble sys">{c.ico("lock", 12)} {c.esc(m["text"])}</div>')
        else:
            cls = "me" if m["autor_id"] == u["id"] else "them"
            tr = trad.get((m["id"], limba)) if cls == "them" and limba != "ro" else None
            corp = c.esc(m["text"])
            if tr and tr.strip() != (m["text"] or "").strip():
                corp = (f'{c.esc(tr)}<div style="font-size:11px;opacity:.65;margin-top:3px">'
                        f'{c.ico("sparkles", 11)} tradus de Gemini · „{c.esc(m["text"])}”</div>')
            bule.append(f'<div class="sk-bubble {cls}">{poza}{corp}'
                        f'<div style="font-size:10px;opacity:.7;margin-top:2px">{timp.ora(m["creat_la"])}</div></div>')
    with st.container(height=430, key="chat_box", autoscroll=True):
        c.h('<div class="sk-col" style="gap:8px">' + "".join(bule) + "</div>")
    logica.marcheaza_citit(l["id"], u["id"])
    if l["status"] in ("anulata",):
        st.caption("Conversația e închisă.")
        return
    msg = st.chat_input("Scrie un mesaj…", accept_file=True, file_type=["jpg", "jpeg", "png"], key="chat_in")
    if msg:
        text = msg.text if hasattr(msg, "text") else str(msg)
        files = getattr(msg, "files", None) or []
        poza = logica.salveaza_poza(files[0], "chat") if files else None
        logica.trimite_mesaj(l["id"], u["id"], text, poza)
        if alt:
            logica.notifica(alt["id"], f"Mesaj nou de la {u['nume']}: {text[:50]}", l["id"])
        st.rerun()


# ---------------------------------------------------------------------------
# Profilul public al meșterului (văzut de client)
# ---------------------------------------------------------------------------
def profil_mester(u, mid, vizitator=True):
    m = logica.user(int(mid))
    if not m or m["rol"] != "mester":
        c.gol("Profilul nu există.")
        return
    t = trust.calculeaza(m["id"])
    if vizitator:
        c.bara_sus("Profil meșter")
    meserii = ", ".join(c.meserie_nume(x) for x in logica.meserii_lista(m))
    c.h(f'<div class="sk-row top">{c.avatar(m, True)}<div class="sk-grow"><div class="sk-title">{c.esc(m["nume"])}'
        f'</div><div class="sk-cap">{c.esc(meserii)}</div><div class="sk-cap">{c.ico("pin", 12)} {c.esc(m["cartier"])}'
        f' · lucrează pe o rază de {m["raza_km"]:.0f} km</div></div></div>')

    # Trust Score
    programate = next(f for f in t["factori"] if f["cheie"] == "programari")
    with st.container(key="card_trust"):
        c.h(f'<div class="sk-row">{c.trust_inel(t["scor"], "lg")}<div class="sk-col" style="gap:4px">'
            f'<span class="sk-badge ok" style="align-self:flex-start">{t["nivel"]}</span>'
            f'<div class="sk-b">Calculat din activitatea reală din SKILLIO, nu din popularitate.</div></div></div>'
            + c.kv([("Lucrări finalizate", t["finalizate"]),
                    ("Evaluare medie", f'{c.nota_txt(t["medie"])}/5' if t["medie"] else "–"),
                    ("Programări respectate", programate["detaliu"]),
                    ("Recenzii verificate", t["nr_recenzii"])]))
        with st.expander("Cum se calculează scorul"):
            c.h(c.factori_trust(t))

    # Cât rezistă lucrările
    durab = db.q("SELECT etapa, AVG(ok) AS p, COUNT(*) AS n FROM feedback WHERE mester_id = ? AND ok IS NOT NULL "
                 "GROUP BY etapa", (m["id"],))
    d = {x["etapa"]: x for x in durab}
    if d:
        bare = "".join(f'<div class="b"><span>{et}</span><span class="t"><i style="width:{d[k]["p"] * 100:.0f}%">'
                       f'</i></span><span class="n">{d[k]["p"]:.0%}</span></div>'
                       for k, et in (("zi1", "După 1 zi"), ("sapt1", "După 1 săpt."), ("luna1", "După 1 lună"))
                       if k in d)
        c.h(f'<div class="sk-card flat"><div class="sk-label">Cât rezistă lucrările</div><div class="sk-bars">{bare}'
            f'</div><div class="sk-cap">Procentul clienților care spun că lucrarea e încă în regulă.</div></div>')

    if m["despre"]:
        c.h(f'<div class="sk-col" style="gap:4px"><div class="sk-label">Despre</div><div class="sk-b">'
            f'{c.esc(m["despre"])}</div></div>')
    servicii = "".join(f'<span class="sk-chip">{config.MESERII[x]["emoji"]} {c.meserie_nume(x)}</span>'
                       for x in logica.meserii_lista(m) if x in config.MESERII)
    c.h(f'<div class="sk-col" style="gap:6px"><div class="sk-label">Servicii și prețuri orientative</div>'
        f'<div class="sk-chips">{servicii}</div>'
        + c.kv([("Experiență", f'{m["experienta_ani"]} ani'),
                ("Tarif orientativ", f'{m["tarif_ora"]} lei/oră' if m["tarif_ora"] else "la ofertă"),
                ("Zonă", f'{m["cartier"]} + {m["raza_km"]:.0f} km')]) + "</div>")

    libere = logica.sloturi_libere(m["id"])[:6]
    if m["disponibil"] and libere:
        sl = "".join(f'<span class="sk-chip">{timp.zi_frumos(x, True)} {x:%H:%M}</span>' for x in libere)
        c.h(f'<div class="sk-col" style="gap:6px"><div class="sk-label">Primele ore libere</div>'
            f'<div class="sk-chips">{sl}</div></div>')
    elif not m["disponibil"]:
        c.alerta("Meșterul nu primește lucrări noi în acest moment.", "escrow", "clock")

    port = logica.portofoliu(m["id"])
    if port:
        c.h('<div class="sk-label">Lucrări anterioare</div>')
        imgs = "".join(f'<div style="flex:none;width:200px"><img class="sk-photo" src="{c.img_uri(p["poza"])}" '
                       f'style="width:200px;height:140px"><div class="sk-cap" style="margin-top:4px">'
                       f'{c.esc(p["descriere"])}</div></div>' for p in port)
        c.h(f'<div class="sk-hscroll">{imgs}</div>')

    rec = logica.recenzii_mester(m["id"], 6)
    medii = logica.medii_criterii(m["id"])
    if rec:
        crit = "".join(f'<div class="b"><span>{et}</span><span class="t"><i style="width:{medii.get(k, 0) / 5 * 100:.0f}%">'
                       f'</i></span><span class="n">{c.nota_txt(medii.get(k))}</span></div>'
                       for k, et in config.CRITERII_RECENZIE)
        c.h(f'<div class="sk-label">Recenzii ({t["nr_recenzii"]}, doar de la lucrări confirmate)</div>'
            f'<div class="sk-bars">{crit}</div>')
        for r in rec:
            tine = " ".join(f'<span class="sk-badge {"ok" if ok else "danger"}">{ {"zi1": "1 zi", "sapt1": "1 săpt.", "luna1": "1 lună"}[e]}'
                            f' {"✓" if ok else "✗"}</span>' for e, ok in r["tine"].items())
            com = f'<div class="sk-b">„{c.esc(r["comentariu"])}”</div>' if r["comentariu"] else ""
            c.h(f'<div class="sk-card flat" style="gap:6px"><div class="sk-between"><b class="sk-b">'
                f'{c.esc(r["client_nume"].split()[0])}</b><span class="sk-cap">{timp.de_cand(r["raspuns_la"])}</span>'
                f'</div><div>{c.stele(r["nota"])} <span class="sk-cap">{c.esc(r["titlu"])}</span></div>{com}'
                f'<div class="sk-badges">{tine}</div></div>')

    if vizitator and u["rol"] == "client":
        st.space("small")
        if st.button("Cere ofertă de la " + m["nume"].split()[0], type="primary", width="stretch", key="cere_oferta",
                     disabled=not m["disponibil"]):
            st.session_state["mester_tinta"] = m["id"]
            st.session_state["sol_meserie"] = logica.meserii_lista(m)[0]
            c.go("solicitare")
        with st.expander("Raportează acest profil"):
            _form_raport(u, None, m["id"], config.MOTIVE_RAPORT_CLIENT, "rp_prof")


def _form_raport(u, lid, vizat, motive, key):
    motiv = st.selectbox("Motiv", motive, key=f"{key}_motiv")
    det = st.text_area("Detalii", key=f"{key}_det", height=80)
    if st.button("Trimite raportul", key=f"danger_{key}"):
        logica.raporteaza(lid, u["id"], vizat, motiv, det)
        c.toast("Raport trimis. Echipa SKILLIO îl verifică.")
        st.rerun()


# ---------------------------------------------------------------------------
# Contul meu
# ---------------------------------------------------------------------------
def cont(u):
    c.h(f'<div class="sk-row">{c.avatar(u, True)}<div class="sk-grow"><div class="sk-title">{c.esc(u["nume"])}</div>'
        f'<div class="sk-cap">{c.esc(u["telefon"])} · {"Meșter" if u["rol"] == "mester" else "Client"}</div></div>'
        f'</div><div class="sk-cap">Numărul tău nu e arătat niciodată celeilalte părți.</div>')
    if u["rol"] == "mester":
        t = trust.calculeaza(u["id"])
        with st.container(key="card_mytrust"):
            c.h(f'<div class="sk-row">{c.trust_inel(t["scor"])}<div><div class="sk-h">Trust Score: {t["nivel"]}</div>'
                f'<div class="sk-cap">Așa te văd clienții. Vezi ce poți îmbunătăți.</div></div></div>')
            with st.expander("Detalii scor"):
                c.h(c.factori_trust(t))
            if st.button("Vezi profilul public", key="link_pub", type="tertiary"):
                c.go("mester", u["id"])

    with st.expander("Date personale", expanded=False):
        nume = st.text_input("Nume", u["nume"], key="ed_nume")
        cartier = st.selectbox("Cartier", list(config.CARTIERE), index=list(config.CARTIERE).index(u["cartier"])
                               if u["cartier"] in config.CARTIERE else 0, key="ed_cartier")
        adresa = st.text_input("Adresa", u["adresa"] or "", key="ed_adresa")
        poza = st.file_uploader("Poză de profil", type=["jpg", "jpeg", "png"], key="ed_poza")
        if st.button("Salvează", type="primary", key="ed_save", width="stretch"):
            camp = {"nume": nume, "cartier": cartier, "adresa": adresa}
            if poza:
                camp["poza"] = logica.salveaza_poza(poza, "profil")
            if adresa.strip() and adresa != u["adresa"]:
                camp["lat"], camp["lon"], _ = geo.coordonate(adresa, cartier)
            logica.actualizeaza_profil(u["id"], **camp)
            c.toast("Profil salvat.")
            st.rerun()

    if u["rol"] == "mester":
        with st.expander("Profil profesional", expanded=False):
            meserii = st.multiselect("Meserii și specializări", list(config.MESERII), logica.meserii_lista(u),
                                     format_func=c.meserie_nume, key="ed_meserii")
            despre = st.text_area("Descriere profesională", u["despre"] or "", key="ed_despre")
            col1, col2 = st.columns(2)
            ani = col1.number_input("Experiență (ani)", 0, 60, int(u["experienta_ani"] or 0), key="ed_ani")
            tarif = col2.number_input("Tarif orientativ (lei/oră)", 0, 1000, int(u["tarif_ora"] or 0), step=5,
                                      key="ed_tarif")
            raza = st.slider("Zona de activitate (km)", 1, 25, int(u["raza_km"] or 8), key="ed_raza")
            wallet = u.get("sol_wallet") or ""
            if solana.activ():
                wallet = st.text_input("Adresa ta Solana (opțional, de ex. din Phantom)", wallet, key="ed_wallet",
                                       help="Aici primești banii on-chain. Gol: îi primești în portofelul creat de "
                                            "SKILLIO pentru tine.")
                adr = solana.portofel_mester(u["id"], wallet)
                c.h(f'<div class="sk-cap">Plățile tale ajung la <a href="{solana.link_adresa(adr)}" target="_blank">'
                    f'{adr[:6]}…{adr[-4:]} ↗</a> (Solana devnet)</div>')
            if st.button("Salvează profilul profesional", type="primary", key="ed_save_pro", width="stretch"):
                if not meserii:
                    st.error("Alege cel puțin o meserie.")
                elif wallet.strip() and not (32 <= len(wallet.strip()) <= 44):
                    st.error("Adresa Solana nu pare corectă.")
                else:
                    logica.actualizeaza_profil(u["id"], meserii=",".join(meserii), despre=despre, experienta_ani=ani,
                                               tarif_ora=tarif, raza_km=raza, sol_wallet=wallet.strip() or None)
                    c.toast("Profil profesional salvat.")
                    st.rerun()
        with st.expander("Poze cu lucrări anterioare"):
            for p in logica.portofoliu(u["id"])[:6]:
                date = stocare.citeste(p["poza"])
                if date:
                    st.image(date, caption=p["descriere"])
            f = st.file_uploader("Adaugă o poză", type=["jpg", "jpeg", "png"], key="port_up")
            desc = st.text_input("Ce ai lucrat", key="port_desc")
            if st.button("Adaugă în portofoliu", key="port_btn", disabled=f is None):
                logica.adauga_portofoliu(u["id"], logica.salveaza_poza(f, "port"), desc or "Lucrare")
                c.toast("Poză adăugată.")
                st.rerun()
        with st.expander("Verificare identitate și calificări"):
            st.caption("Încarcă actul de identitate sau un atestat (ex. ANRE). Echipa SKILLIO îl verifică.")
            stare = {"lipsa": "Neîncărcat", "in_asteptare": "În verificare", "verificat": "Verificat"}
            st.markdown(f"Stare: **{stare.get(u['act_status'], u['act_status'])}**")
            act = st.file_uploader("Document", type=["jpg", "jpeg", "png", "pdf"], key="act_up")
            if act and st.button("Trimite la verificare", key="act_btn"):
                logica.actualizeaza_profil(u["id"], act_poza=logica.salveaza_poza(act, "act"), act_status="in_asteptare")
                c.toast("Document trimis la verificare.")
                st.rerun()


    with st.container(horizontal=True):
        if st.button("Reia ghidul", key="reia_ghid", width="stretch", icon=":material/school:"):
            st.session_state.ghid_pas = 0
            c.go("ghid")
        if st.button("Notificări", key="cont_notif", width="stretch", icon=":material/notifications:"):
            c.go("notificari")
    with st.container(horizontal=True):
        if st.button("Spune-ne părerea", key="cont_fb", width="stretch", icon=":material/rate_review:"):
            c.go("feedback")
        if st.button("Ce e nou", key="cont_nou", width="stretch", icon=":material/new_releases:"):
            c.go("noutati")
    if st.button("Ieși din cont", key="danger_logout"):
        logica.sterge_sesiune(st.query_params.get("s"))
        st.query_params.clear()
        st.session_state.clear()
        if autentificare_srv.logat():
            autentificare_srv.iesi()
        st.rerun()
