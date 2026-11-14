"""Ecranele meșterului: acasă, solicitări pe hartă, calendar."""
import streamlit as st

from core import config, logica, timp, trust
from services import geo
from ui import comp as c
from ui import harta


def acasa(u):
    t = trust.calculeaza(u["id"])
    stat = logica.statistici_mester(u["id"])
    c.h(f'<div class="sk-between"><div><div class="sk-cap">{c.ico("pin", 12)} {c.esc(u["cartier"])}</div>'
        f'<div class="sk-title">Salut, {c.esc(u["nume"].split()[0])}!</div></div>{c.trust_inel(t["scor"])}</div>')
    with st.container(key="card_disp" if u["disponibil"] else "cardflat_disp"):
        disp = st.toggle("Disponibil pentru lucrări noi", value=bool(u["disponibil"]), key="m_disp")
        if disp != bool(u["disponibil"]):
            logica.actualizeaza_profil(u["id"], disponibil=int(disp))
            st.rerun()
        st.caption("Clienții te văd în căutări și primești solicitări." if disp else
                   "Nu primești solicitări noi. Lucrările programate rămân.")

    sos_n = len([x for x in logica.sos_deschise(u["id"]) if x["status"] in ("asteapta", "in_apel")])
    with st.container(key="card_sos"):
        c.h(f'<div class="sk-row"><span class="sk-sos-dot"></span><div class="sk-grow"><div class="sk-h">Apeluri SOS'
            f'{f" · {sos_n} acum" if sos_n else ""}</div><div class="sk-cap">Ghidezi un client prin video și primești '
            f'{c.lei(config.SOS_MESTER)}.</div></div></div>')
        if st.button("Vezi apelurile", key="m_sos", width="stretch", type="primary" if sos_n else "secondary"):
            c.go("sos")
    urm = sorted([l for l in logica.lucrari_mester(u["id"]) if l["status"] in ("de_plata", "programata", "sosit", "reconfirmare", "in_lucru")
                  and l["programat_la"]], key=lambda l: l["programat_la"])
    if urm:
        l = urm[0]
        cand = timp.din_iso(l["programat_la"])
        c.h(c.card_hero(f'Următoarea: {timp.zi_frumos(cand.date())} · {timp.ora(cand)}',
                        f'{l["titlu"]} · {l["cartier"]}', logica.bani_lucrare(l["id"])["blocat"]))
        if st.button("Deschide lucrarea", key="link_hero_m", type="tertiary"):
            c.go("lucrare", l["id"])

    c.h('<div class="sk-stats">'
        f'<div class="sk-stat"><span class="v">{c.lei(stat["incasat_sapt"])}</span><span class="l">Încasat săptămâna asta'
        f'</span></div><div class="sk-stat"><span class="v" style="color:var(--sk-escrow)">{c.lei(stat["blocat"])}</span>'
        f'<span class="l">Blocat, de încasat</span></div><div class="sk-stat"><span class="v">{t["finalizate"]}</span>'
        f'<span class="l">Lucrări finalizate</span></div><div class="sk-stat"><span class="v">'
        f'{c.nota_txt(t["medie"])}</span><span class="l">Evaluare medie</span></div></div>')
    if not u["sim_ok"]:
        c.alerta("SIM-ul tău a fost schimbat recent. Clienții văd un avertisment până la următoarea verificare.",
                 "escrow", "alert")

    sol = logica.solicitari_pentru_mester(u["id"])
    noi = [s for s in sol if not s["oferta_mea"]]
    c.h(f'<div class="sk-between"><div class="sk-label">Solicitări noi ({len(noi)})</div></div>')
    if not noi:
        c.gol("Nicio solicitare nouă acum. Te anunțăm imediat ce apare una.", "clock")
    for s in noi[:3]:
        card_solicitare(u, s, f"h{s['id']}")
    if len(noi) > 3 and st.button("Vezi toate pe hartă", key="link_toate", type="tertiary"):
        c.go("solicitari")

    prog = [l for l in logica.lucrari_mester(u["id"]) if l["status"] in ("acceptata", "de_plata", "programata",
                                                                           "sosit", "gata", "disputa")]
    c.h(f'<div class="sk-label">Programări și lucrări în curs ({len(prog)})</div>')
    if not prog:
        c.gol("Nu ai programări încă.", "cal")
    for l in prog:
        cand = l["programat_la"] or l["prog_propus"]
        with st.container(key=f"card_p{l['id']}"):
            c.h(f'<div class="sk-between"><div class="sk-h">{c.esc(l["titlu"])}</div>{c.badge_status(l["status"])}</div>'
                f'<div class="sk-cap">{c.ico("cal", 12)} {timp.data_ora(cand) if cand else "–"} · {c.esc(l["cartier"])}'
                f'</div>')
            if st.button("Deschide", key=f"p_open{l['id']}", width="stretch"):
                c.go("lucrare", l["id"])

    rec = logica.recenzii_mester(u["id"], 3)
    if rec:
        c.h('<div class="sk-label">Evaluări recente</div>')
        for r in rec:
            com = f' · „{c.esc(r["comentariu"])}”' if r["comentariu"] else ""
            c.h(f'<div class="sk-card flat" style="gap:4px"><div class="sk-between"><b class="sk-b">'
                f'{c.esc(r["client_nume"].split()[0])}</b>{c.stele(r["nota"])}</div><div class="sk-cap">'
                f'{c.esc(r["titlu"])}{com}</div></div>')
    with st.expander("Statistici activitate"):
        rata = stat["oferte_acceptate"] / stat["oferte_trimise"] if stat["oferte_trimise"] else 0
        c.h(c.kv([("Încasat în total", c.lei(stat["incasat_total"])), ("Oferte trimise", stat["oferte_trimise"]),
                  ("Oferte acceptate", f'{stat["oferte_acceptate"]} ({rata:.0%})'),
                  ("Trust Score", f'{t["scor"]} · {t["nivel"]}')]))


def card_solicitare(u, s, key):
    urg = c.badge_urgent() if s["urgent"] else ""
    img = (f'<img class="sk-photo" src="{c.img_uri(s["poza"])}" style="width:64px;height:64px">' if s["poza"] else
           f'<div class="sk-av" style="width:64px;height:64px;border-radius:14px;font-size:26px">'
           f'{config.MESERII[s["meserie"]]["emoji"]}</div>')
    d = logica.diagnostic(s)
    pret = f'{d.get("pret_min")}–{d.get("pret_max")} lei' if d else ""
    stare = (f'<span class="sk-badge ok">Ofertă trimisă: {c.lei(s["oferta_mea"]["total"])}</span>' if s["oferta_mea"]
             else f'<span class="sk-cap">{s["nr_oferte"]} {"ofertă" if s["nr_oferte"] == 1 else "oferte"}</span>')
    with st.container(key=f"card{'urg' if s['urgent'] else ''}_{key}"):
        c.h(f'<div class="sk-row top">{img}<div class="sk-grow"><div class="sk-between"><div class="sk-h">'
            f'{c.esc(s["titlu"])}</div></div><div class="sk-cap">{c.esc(s["cartier"])} · {geo.km(s["dist"])} · '
            f'{timp.de_cand(s["creat_la"])}</div><div class="sk-b" style="margin-top:4px;display:-webkit-box;'
            f'-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">{c.esc(s["descriere"])}</div></div>'
            f'</div><div class="sk-between"><div class="sk-badges">{urg}<span class="sk-badge">AI: {pret}</span></div>'
            f'{stare}</div>')
        if st.button("Vezi și trimite ofertă" if not s["oferta_mea"] else "Vezi oferta",
                     type="primary" if s["urgent"] and not s["oferta_mea"] else "secondary",
                     key=f"{'urg' if s['urgent'] else ''}sol_{key}", width="stretch"):
            c.go("lucrare", s["id"])


def solicitari(u):
    c.h('<div class="sk-title">Solicitări lângă tine</div>')
    sol = logica.solicitari_pentru_mester(u["id"])
    meserii = ", ".join(c.meserie_nume(x) for x in logica.meserii_lista(u))
    st.caption(f"{meserii} · pe o rază de {u['raza_km']:.0f} km. Urgentele (portocaliu) apar primele.")
    ales = harta.harta_lucrari(sol, u["lat"], u["lon"], key="m_map", inaltime=280)
    if ales:
        c.go("lucrare", ales)
    if not sol:
        c.gol("Nicio solicitare deschisă în zona ta acum.", "clock")
    filtru = st.segmented_control("Filtru", ["Toate", "Urgente", "Fără ofertă"], default="Toate",
                                  key="m_filtru", label_visibility="collapsed", width="stretch")
    for s in sol:
        if filtru == "Urgente" and not s["urgent"]:
            continue
        if filtru == "Fără ofertă" and s["oferta_mea"]:
            continue
        card_solicitare(u, s, f"s{s['id']}")


def calendar(u):
    c.h('<div class="sk-title">Calendar</div>')
    zile = logica.calendar_mester(u["id"])
    st.caption("Verde = lucrare programată (atinge ca s-o deschizi). Gri = liber. Hașurat = blocat. "
               "Atinge o oră liberă ca s-o blochezi. Clienții văd doar orele libere.")
    for z in zile:
        zi = z["zi"]
        ocupate = sum(1 for s in z["sloturi"] if s["lucrare"])
        nume_zi = timp.zi_frumos(zi)
        eticheta = f"{nume_zi.capitalize()} · {zi.day} {timp.LUNI[zi.month - 1]}" if nume_zi in ("azi", "mâine") \
            else nume_zi.capitalize()
        c.h(f'<div class="sk-between"><div class="sk-label">{eticheta}</div>'
            f'<span class="sk-cap">{ocupate} lucrări</span></div>')
        with st.container(horizontal=True, gap="small", key=f"calrow{zi}"):
            for s in z["sloturi"]:
                l = s["lucrare"]
                if l:
                    if st.button(f"{s['ora']}:00", key=f"cal_l{zi}{s['ora']}", type="primary",
                                 width="stretch"):
                        c.go("lucrare", l["id"])
                else:
                    if st.button(f"{s['ora']}:00", key=f"cal_{zi}{s['ora']}", width="stretch",
                                 type="tertiary" if s["blocat"] else "secondary"):
                        logica.comuta_blocare(u["id"], zi.isoformat(), s["ora"])
                        st.rerun()
    with st.expander("Blochează o zi întreagă"):
        zi = st.selectbox("Ziua", [z["zi"] for z in zile], format_func=lambda d: timp.zi_frumos(d), key="bl_zi")
        if st.button("Comută ziua (liberă / blocată)", key="bl_btn"):
            logica.comuta_blocare(u["id"], zi.isoformat(), -1)
            st.rerun()
