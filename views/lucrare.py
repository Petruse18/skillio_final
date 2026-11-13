"""Ecranul unei lucrări, pentru client și pentru meșter. Arată pasul curent și acțiunea potrivită."""
from datetime import timedelta

import streamlit as st

from core import config, logica, timp
from core.logica import Eroare
from services import geo, solana
from ui import comp as c
from ui import harta


def _actiune(fn, *a, ok=None, **kw):
    """Rulează o acțiune; arată eroarea frumos sau un mesaj de succes."""
    try:
        r = fn(*a, **kw)
        if ok:
            c.toast(ok)
        st.rerun()
        return r
    except Eroare as e:
        st.error(str(e))


def _cronologie(l):
    s = l["status"]
    ordine = ["deschisa", "acceptata", "de_plata", "programata", "sosit", "gata", "finalizata"]
    idx = ordine.index(s) if s in ordine else (5 if s == "disputa" else -1)
    pasi = [
        ("Solicitare trimisă", timp.de_cand(l["creat_la"])),
        ("Ofertă aleasă", ""),
        ("Ora stabilită", timp.data_ora(l["programat_la"]) if l["programat_la"] else ""),
        ("Plătit, bani blocați", ""),
        ("Sosire confirmată de rețea", timp.ora(l["sosit_la"]) if l["sosit_la"] else ""),
        ("Lucrare gata", timp.ora(l["gata_la"]) if l["gata_la"] else ""),
        ("Confirmată, bani eliberați", ""),
    ]
    lst = []
    for i, (t, d) in enumerate(pasi):
        stare = "done" if i < idx + 1 and s != "anulata" else ("now" if i == idx + 1 else "")
        if s == "finalizata":
            stare = "done"
        lst.append((t, d, stare))
    return c.pasi(lst)


def _detalii(l, eu_sunt_mester):
    d = logica.diagnostic(l)
    if l["poza"]:
        c.poza(l["poza"], 180)
    urg = c.badge_urgent() if l["urgent"] else ""
    buget = f'<span class="sk-badge">Buget ~{l["buget"]} lei</span>' if l["buget"] else ""
    c.h(f'<div class="sk-badges"><span class="sk-badge">{config.MESERII[l["meserie"]]["emoji"]} '
        f'{c.meserie_nume(l["meserie"])}</span>{urg}{buget}</div><div class="sk-b">{c.esc(l["descriere"])}</div>'
        f'<div class="sk-cap">{c.ico("pin", 12)} {c.esc(l["adresa"] if (not eu_sunt_mester or l["mester_id"]) else l["cartier"])}'
        f' · {c.esc(l["cartier"])}</div>')
    if d:
        mat = ", ".join(d.get("materiale", []))
        c.alerta(f'<b>Asistent AI:</b> {d.get("pret_min")}–{d.get("pret_max")} lei orientativ, ~{d.get("durata_min")} '
                 f'min. {"De adus: " + c.esc(mat) + "." if mat else ""}', "ai", "sparkles")


def ecran(u, lid):
    l = logica.lucrare(int(lid))
    if not l:
        c.gol("Lucrarea nu există.")
        return
    e_client = u["id"] == l["client_id"]
    e_mester = u["rol"] == "mester" and not e_client
    if u["rol"] == "admin":
        e_client = False
    c.bara_sus(l["titlu"], "lucrari" if e_client else "acasa")
    c.h(f'<div class="sk-between">{c.badge_status(l["status"])}<span class="sk-cap">#{l["id"]} · '
        f'{timp.de_cand(l["creat_la"])}</span></div>')

    if e_client:
        _client(u, l)
    elif e_mester:
        _mester(u, l)
    else:
        _detalii(l, False)

    if l["mester_id"] and u["id"] in (l["client_id"], l["mester_id"]):
        nec = logica.necitite(l["id"], u["id"])
        if st.button(f"Chat{f' ({nec} noi)' if nec else ''}", icon=":material/chat:", width="stretch",
                     key="lucr_chat"):
            c.go("chat", l["id"])
    _blockchain(l)
    if l["status"] not in ("deschisa",) or e_client:
        with st.expander("Cum a decurs până acum"):
            c.h(_cronologie(l))


def _blockchain(l):
    """Tranzacțiile Solana ale lucrării (dacă plata a mers on-chain) și pașaportul ei."""
    plati = logica.bani_lucrare(l["id"])["rows"]
    rand = []
    for p in plati:
        if p.get("tx_lock"):
            rand.append((f'Blocat: {c.lei(p["suma"])} ({p["tip"]})', p["tx_lock"]))
    finale = {p["tx_final"]: p["status"] for p in plati if p.get("tx_final")}
    for sig, stare in finale.items():
        rand.append(("Eliberat către meșter (90%) și SKILLIO (10%)" if stare == "eliberat" else "Returnat clientului",
                     sig))
    if not rand and not l.get("pasaport"):
        return
    li = "".join(f'<div class="sk-li"><span class="sk-grow">{c.esc(t)}</span><a href="{solana.link_tx(sig)}" '
                 f'target="_blank" style="color:var(--sk-primary);font-weight:700">{sig[:6]}…{sig[-4:]} ↗</a></div>'
                 for t, sig in rand)
    pas = ""
    if l.get("pasaport"):
        pas = (f'<div class="sk-cap" style="margin-top:6px"><b>Pașaportul lucrării</b> (amprentă sha256): '
               f'<code>{l["pasaport"][:16]}…</code>' +
               (f' · <a href="{solana.link_tx(l["tx_pasaport"])}" target="_blank">scris pe Solana ↗</a>'
                if l.get("tx_pasaport") else "") + '</div>')
    c.h(f'<div class="sk-card flat" style="gap:6px"><div class="sk-row">{c.ico("lock", 16)}<b class="sk-b">'
        f'Plată verificabilă pe blockchain</b><span class="sk-badge" style="margin-left:auto">Solana devnet</span>'
        f'</div><div class="sk-list">{li}</div>{pas}</div>')


# ---------------------------------------------------------------------------
# Clientul
# ---------------------------------------------------------------------------
def _client(u, l):
    s = l["status"]
    bani = logica.bani_lucrare(l["id"])
    mester = logica.user(l["mester_id"]) if l["mester_id"] else None

    if mester:
        with st.container(key="card_mesterul"):
            c.h(f'<div class="sk-row">{c.avatar(mester)}<div class="sk-grow"><div class="sk-h">{c.esc(mester["nume"])}'
                f'</div><div class="sk-cap">Meșterul tău</div></div>{c.trust_pill(logica.trust.scor(mester["id"]))}'
                f'</div>{c.insigne_nokia(mester, sosire=bool(l["sosit_la"]))}')
            if st.button("Vezi profilul", key="link_prof_m", type="tertiary"):
                c.go("mester", mester["id"])

    if s == "deschisa":
        oferte = logica.oferte(l["id"])
        inv = logica.db.val("SELECT COUNT(*) FROM invitatii WHERE lucrare_id = ? AND status = 'noua'", (l["id"],), 0)
        c.h(f'<div class="sk-title" style="font-size:20px">Oferte primite ({len(oferte)})</div>'
            f'<div class="sk-cap">Solicitarea a ajuns la {inv} meșteri potriviți. Ofertele apar aici în timp real.'
            f'{f" Prețurile includ +{config.PCT_URGENT} urgent." if l["urgent"] else ""}</div>')
        if not oferte:
            c.gol("Așteptăm primele oferte. De obicei vin în câteva minute.", "clock")
        if len(oferte) > 1:
            sortare = st.segmented_control("Sortează", ["Preț", "Trust Score", "Cel mai devreme"], default="Preț",
                                           key="of_sort", label_visibility="collapsed", width="stretch")
            if sortare == "Trust Score":
                oferte.sort(key=lambda o: -o["trust"]["scor"])
            elif sortare == "Cel mai devreme":
                oferte.sort(key=lambda o: o["propus_la"])
        cel_mai_bun = max(oferte, key=lambda o: o["trust"]["scor"] - o["total"] / 40)["id"] if oferte else None
        if oferte:
            c.asculta(f"Ai {len(oferte)} {'ofertă' if len(oferte) == 1 else 'oferte'}. " + " ".join(
                f'{o["mester"]["nume"]}: {o["total"]:.0f} de lei, {timp.data_ora(o["propus_la"])}, '
                f'Trust Score {o["trust"]["scor"]}.' for o in oferte), f"of{l['id']}")
        for o in oferte:
            m = o["mester"]
            rec = '<span class="sk-badge ok">Recomandat</span>' if o["id"] == cel_mai_bun and len(oferte) > 1 else ""
            msg = f'<div class="sk-b">„{c.esc(o["mesaj"])}”</div>' if o["mesaj"] else ""
            with st.container(key=f"card{'sel' if o['id'] == cel_mai_bun and len(oferte) > 1 else ''}_of{o['id']}"):
                c.h(f'<div class="sk-row">{c.avatar(m)}<div class="sk-grow"><div class="sk-between"><b class="sk-h">'
                    f'{c.esc(m["nume"])}</b><span class="sk-price">{c.lei(o["total"])}</span></div><div class="sk-cap">'
                    f'Trust {o["trust"]["scor"]} · {c.stele(o["trust"]["medie"])} {c.nota_txt(o["trust"]["medie"])} · '
                    f'{geo.km(o["dist"])}</div></div></div>'
                    f'<div class="sk-between"><span class="sk-b">{c.ico("cal", 14)} {timp.data_ora(o["propus_la"])}</span>'
                    f'{rec}</div>{msg}{c.insigne_nokia(m)}')
                with st.container(horizontal=True):
                    if st.button("Profil", key=f"of_prof{o['id']}", width="stretch"):
                        c.go("mester", m["id"])
                    if st.button("Acceptă oferta", type="primary", key=f"of_acc{o['id']}", width="stretch"):
                        _actiune(logica.accepta_oferta, o["id"], u["id"], ok="Ofertă acceptată. Confirmă ora.")
        _detalii(l, False)
        if st.button("Anulează solicitarea", key="danger_anul"):
            _actiune(logica.anuleaza_lucrare, l["id"], u["id"], ok="Solicitare anulată.")

    elif s == "acceptata":
        c.h('<div class="sk-title" style="font-size:20px">Stabiliți ora</div>')
        if l["prog_propus"] and l["prog_propus_de"] == "mester":
            c.alerta(f'{c.esc(mester["nume"])} propune <b>{timp.data_ora(l["prog_propus"])}</b>.', "ai", "cal")
            if st.button(f"Confirm {timp.data_ora(l['prog_propus'])}", type="primary", width="stretch", key="conf_ora"):
                _actiune(logica.confirma_ora, l["id"], u["id"], ok="Ora e stabilită. Poți plăti.")
        elif l["prog_propus"]:
            c.alerta(f'Ai propus <b>{timp.data_ora(l["prog_propus"])}</b>. Așteptăm confirmarea meșterului.', "ai", "clock")
        _alege_alta_ora(u, l)

    elif s == "de_plata":
        o = logica.db.q1("SELECT * FROM oferte WHERE id = ?", (l["oferta_id"],))
        c.h('<div class="sk-title" style="font-size:20px">Plată</div>')
        rows = [("Ofertă meșter", c.lei(o["pret"]))]
        if l["urgent"]:
            rows.append((f"Urgent +{config.PCT_URGENT}", c.lei(o["total"] - o["pret"])))
        rows.append(("Programare", timp.data_ora(l["programat_la"])))
        rows.append(("Total de plată", c.lei(o["total"]), True))
        with st.container(key="card_plata"):
            c.h(c.kv(rows))
            c.alerta("<b>Banii rămân blocați în SKILLIO</b> până confirmi că lucrarea e în regulă. Dacă meșterul nu "
                     "vine, îi primești înapoi.", "escrow", "lock")
        if st.button(f"Plătește {c.lei(o['total'])}", type="primary", width="stretch", key="plateste",
                     icon=":material/lock:"):
            _actiune(logica.plateste, l["id"], u["id"], ok="Plată efectuată. Banii sunt blocați până la final.")
        st.caption("Plată simulată pentru prezentare.")

    elif s == "programata":
        c.alerta(f'<b>{timp.data_ora(l["programat_la"])}</b> · {c.lei(bani["blocat"])} blocați în SKILLIO până '
                 f'la final.', "escrow", "lock")
        harta.harta_traseu((mester["lat"], mester["lon"]), (l["lat"], l["lon"]), key="tr_cl", inaltime=180)
        dist = geo.distanta_km(mester["lat"], mester["lon"], l["lat"], l["lon"])
        st.caption(f"Meșterul pornește din {mester['cartier']} ({geo.km(dist)}, ~{geo.minute_drum(dist)} min). "
                   f"Când ajunge, rețeaua confirmă sosirea.")
        if timp.acum() >= timp.din_iso(l["programat_la"]) + timedelta(hours=1):
            if st.button("Meșterul nu a venit, vreau banii înapoi", key="danger_noshow"):
                _actiune(logica.nu_a_venit, l["id"], u["id"], ok="Am returnat banii. Ne pare rău!")
        if st.button("Anulează programarea (primești banii înapoi)", key="danger_anul2"):
            _actiune(logica.anuleaza_lucrare, l["id"], u["id"], ok="Programare anulată, banii s-au întors.")

    elif s in ("sosit", "gata"):
        mod = "rețeaua Nokia" if l["sosire_mod"] == "live" else "rețea (simulare)"
        c.alerta(f'<b>{c.esc(mester["nume"])} a ajuns la {timp.ora(l["sosit_la"])}</b>. Sosire confirmată de {mod}'
                 f'{", la timp" if l["punctual"] else ", cu întârziere"}.', "trust", "pin")
        for e in logica.extra_lucrare(l["id"]):
            if e["status"] == "trimisa":
                with st.container(key=f"cardsel_extra{e['id']}"):
                    c.h(f'<div class="sk-h">Lucrare în plus: {c.lei(e["suma"])}</div><div class="sk-b">{c.esc(e["motiv"])}'
                        f'</div><div class="sk-cap">Dacă accepți, suma se plătește și rămâne blocată ca restul.</div>')
                    with st.container(horizontal=True):
                        if st.button("Refuz", key=f"ex_no{e['id']}", width="stretch"):
                            _actiune(logica.raspunde_extra, e["id"], u["id"], False, ok="Ai refuzat lucrarea în plus.")
                        if st.button(f"Accept și plătesc {c.lei(e['suma'])}", type="primary", key=f"ex_ok{e['id']}",
                                     width="stretch"):
                            _actiune(logica.raspunde_extra, e["id"], u["id"], True, ok="Lucrare în plus acceptată.")
        if s == "sosit":
            c.h('<div class="sk-b">Meșterul lucrează. Când termină, îți cerem confirmarea.</div>')
        else:
            c.h('<div class="sk-title" style="font-size:20px">Verifică lucrarea</div>')
            if l["nota_mester"]:
                c.h(f'<div class="sk-b">Meșterul: „{c.esc(l["nota_mester"])}”</div>')
            if l["poza_dupa"]:
                c.poza(l["poza_dupa"], 180)
            rows = [(("Ofertă" if p["tip"] == "oferta" else "Lucrare în plus"), c.lei(p["suma"]))
                    for p in bani["rows"] if p["status"] == "blocat"]
            rows.append(("Merge la meșter", c.lei(bani["blocat"]), True))
            with st.container(key="card_confirm"):
                c.h(c.kv(rows))
                ok = st.checkbox("Am verificat, totul e în regulă", key="conf_ok")
                if st.button(f"Eliberează {c.lei(bani['blocat'])} către {mester['nume'].split()[0]}", type="primary",
                             width="stretch", key="elibereaza", disabled=not ok):
                    _actiune(logica.confirma_lucrare, l["id"], u["id"], ok="Gata! Meșterul și-a primit banii.")
        with st.expander("Nu e în regulă, raportez"):
            st.caption("Banii rămân blocați până verifică echipa SKILLIO.")
            motiv = st.selectbox("Motiv", config.MOTIVE_RAPORT_CLIENT, key="disp_motiv")
            det = st.text_area("Ce nu e în regulă?", key="disp_det", height=80)
            if st.button("Trimite raportul", key="danger_disp"):
                _actiune(logica.raporteaza, l["id"], u["id"], l["mester_id"], motiv, det,
                         ok="Raport trimis. Banii rămân blocați până la verificare.")

    elif s == "finalizata":
        c.alerta(f'Lucrare confirmată. {c.lei(bani["eliberat"])} au ajuns la meșter.', "ai", "check")
        _recenzie_si_durabilitate(u, l)

    elif s == "disputa":
        c.alerta("Ai raportat o problemă. Echipa SKILLIO verifică, iar banii rămân blocați până atunci.", "escrow", "lock")

    elif s == "anulata":
        c.alerta(f'Lucrare anulată: {c.esc(l["anulat_motiv"] or "")}.'
                 + (f' {c.lei(bani["returnat"])} s-au întors la tine.' if bani["returnat"] else ""), "escrow", "info")

    if s != "deschisa":
        with st.expander("Detaliile solicitării"):
            _detalii(l, False)
    if mester and s not in ("deschisa", "anulata"):
        with st.expander("Raportează o problemă cu meșterul"):
            from views.comun import _form_raport
            _form_raport(u, l["id"], mester["id"], config.MOTIVE_RAPORT_CLIENT, "rp_l")


def _alege_alta_ora(u, l, ca_mester=False):
    libere = logica.sloturi_libere(l["mester_id"], ignora_lucrare=l["id"])
    if not libere:
        return
    with st.expander("Propune altă oră" if not ca_mester else "Propune altă oră clientului"):
        zile = sorted({x.date() for x in libere})
        zi = st.pills("Ziua", zile, default=zile[0], format_func=lambda d: timp.zi_frumos(d, True),
                      key=f"alt_zi{ca_mester}")
        ore = [x for x in libere if x.date() == zi] if zi else []
        if ore:
            ora = st.pills("Ora", ore, default=ore[0], format_func=lambda x: f"{x:%H:%M}", key=f"alt_ora{ca_mester}")
            if ora and st.button(f"Propune {timp.data_ora(ora)}", key=f"alt_btn{ca_mester}", width="stretch"):
                _actiune(logica.propune_ora, l["id"], u["id"], ora, ok="Oră propusă.")


def _recenzie_si_durabilitate(u, l):
    fb = logica.feedback_lucrare(l["id"])
    final = next((f for f in fb if f["etapa"] == "final"), None)
    if final and not final["raspuns_la"]:
        with st.container(key="cardsel_recenzie"):
            c.h('<div class="sk-h">Cum a fost?</div><div class="sk-cap">Recenzia apare pe profilul meșterului ca '
                '„verificată”, pentru că lucrarea a fost confirmată în SKILLIO.</div>')
            note = {}
            for k, et in config.CRITERII_RECENZIE:
                st.markdown(f"<div class='sk'><div class='sk-label'>{et}</div></div>", unsafe_allow_html=True)
                v = st.feedback("stars", key=f"rv_{k}")
                note[k] = v + 1 if v is not None else None
            com = st.text_area("Comentariu (opțional)", key="rv_com", height=80)
            if st.button("Trimite recenzia", type="primary", width="stretch", key="rv_send",
                         disabled=any(v is None for v in note.values())):
                _actiune(logica.da_recenzie, final["id"], u["id"], note, com, ok="Mulțumim pentru recenzie!")
    elif final:
        c.h(f'<div class="sk-b">Recenzia ta: {c.stele(final["nota"])} {c.nota_txt(final["nota"])}</div>')
    pasi = []
    for f in fb:
        if f["etapa"] == "final":
            continue
        if f["raspuns_la"]:
            pasi.append((logica.ETAPE[f["etapa"]][0], "Totul e în regulă" if f["ok"] else "Au apărut probleme", "done"))
        elif f["scadent_la"] <= timp.iso(timp.acum()):
            pasi.append((logica.ETAPE[f["etapa"]][0], "Te întrebăm acum, pe ecranul de start", "now"))
        else:
            pasi.append((logica.ETAPE[f["etapa"]][0], timp.zi_frumos(f["scadent_la"]), ""))
    if pasi:
        c.h('<div class="sk-label">Lucrarea mai ține? Te întrebăm de 3 ori</div>' + c.pasi(pasi))
    for f in fb:
        if f["etapa"] != "final" and not f["raspuns_la"] and f["scadent_la"] <= timp.iso(timp.acum()):
            from views.client import _card_durabilitate
            _card_durabilitate(u, f)
            break


# ---------------------------------------------------------------------------
# Meșterul
# ---------------------------------------------------------------------------
def _mester(u, l):
    s = l["status"]
    client = logica.user(l["client_id"])
    e_al_meu = l["mester_id"] == u["id"]
    bani = logica.bani_lucrare(l["id"])

    if s == "deschisa":
        dist = geo.distanta_km(u["lat"], u["lon"], l["lat"], l["lon"])
        _detalii(l, True)
        c.h(f'<div class="sk-row">{c.avatar(client)}<div class="sk-grow"><b class="sk-b">{c.esc(client["nume"])}</b>'
            f'<div class="sk-cap">{c.esc(l["cartier"])} · {geo.km(dist)} de tine</div></div></div>'
            f'{c.insigne_nokia(client)}')
        nr = logica.db.val("SELECT COUNT(*) FROM oferte WHERE lucrare_id = ? AND status = 'trimisa' AND mester_id != ?",
                           (l["id"], u["id"]), 0)
        st.caption(f"{nr} alți meșteri au trimis deja oferte." if nr else "Ești printre primii. Trimite o ofertă.")
        of = logica.db.q1("SELECT * FROM oferte WHERE lucrare_id = ? AND mester_id = ? AND status = 'trimisa'",
                          (l["id"], u["id"]))
        if of:
            c.alerta(f'Ai trimis <b>{c.lei(of["total"])}</b> pentru {timp.data_ora(of["propus_la"])}. Poți modifica '
                     f'oferta mai jos.', "ai", "check")
        d = logica.diagnostic(l)
        with st.container(key="card_oferta"):
            c.h('<div class="sk-h">Oferta ta</div>')
            pret = st.number_input("Prețul tău (lei, manoperă + materiale)", 10, 20000,
                                   int(of["pret"] if of else (d.get("pret_min", 100) + d.get("pret_max", 200)) // 2),
                                   step=10, key="of_pret")
            if l["urgent"]:
                c.h(f'<div class="sk-alert" style="background:var(--sk-urgent-soft);color:var(--sk-urgent)">'
                    f'{c.ico("alert")}<div>Urgent: clientul plătește <b>{c.lei(logica.total_cu_urgenta(pret, 1))}</b>. '
                    f'Cei {config.PCT_URGENT} în plus sunt ai tăi.</div></div>')
            libere = logica.sloturi_libere(u["id"])
            if not libere:
                st.warning("Nu ai ore libere în următoarele 7 zile. Eliberează ceva din calendar.")
                return
            zile = sorted({x.date() for x in libere})
            zi = st.pills("Ziua", zile, default=zile[0], format_func=lambda x: timp.zi_frumos(x, True), key="of_zi")
            ore = [x for x in libere if x.date() == zi] if zi else []
            ora = st.pills("Ora", ore, default=ore[0] if ore else None, format_func=lambda x: f"{x:%H:%M}",
                           key="of_ora") if ore else None
            mesaj = st.text_input("Mesaj pentru client (opțional)", key="of_msg",
                                  placeholder="Ex: Aduc racordul nou, durează cam o oră.")
            with st.container(horizontal=True):
                if not of and st.button("Refuz", key="of_ref", width="stretch"):
                    logica.refuza_solicitare(l["id"], u["id"])
                    c.go("solicitari", push=False)
                if st.button("Actualizează oferta" if of else "Trimite oferta", type="primary", key="of_send",
                             width="stretch", disabled=ora is None):
                    _actiune(logica.trimite_oferta, l["id"], u["id"], pret, ora, mesaj, ok="Ofertă trimisă clientului.")
        return

    if not e_al_meu:
        c.alerta("Clientul a ales altă ofertă pentru această lucrare.", "escrow", "info")
        return

    c.h(f'<div class="sk-row">{c.avatar(client)}<div class="sk-grow"><b class="sk-h">{c.esc(client["nume"])}</b>'
        f'<div class="sk-cap">{c.esc(l["adresa"])}, {c.esc(l["cartier"])}</div></div></div>')

    if s == "acceptata":
        c.h('<div class="sk-title" style="font-size:20px">Oferta ta a fost acceptată!</div>')
        if l["prog_propus"] and l["prog_propus_de"] == "client":
            c.alerta(f'Clientul propune <b>{timp.data_ora(l["prog_propus"])}</b>.', "ai", "cal")
            if st.button(f"Confirm {timp.data_ora(l['prog_propus'])}", type="primary", width="stretch", key="m_conf"):
                _actiune(logica.confirma_ora, l["id"], u["id"], ok="Programare confirmată.")
        else:
            c.alerta(f'Ai propus <b>{timp.data_ora(l["prog_propus"])}</b>. Așteptăm confirmarea clientului.', "ai", "clock")
        _alege_alta_ora(u, l, ca_mester=True)

    elif s == "de_plata":
        c.alerta(f'Programare stabilită: <b>{timp.data_ora(l["programat_la"])}</b>. Așteptăm plata clientului.', "ai",
                 "clock")

    elif s == "programata":
        c.alerta(f'<b>{timp.data_ora(l["programat_la"])}</b> · Clientul a plătit {c.lei(bani["blocat"])}, blocați '
                 f'pentru tine până confirmă lucrarea.', "escrow", "lock")
        harta.harta_traseu((u["lat"], u["lon"]), (l["lat"], l["lon"]), key="tr_m", inaltime=180)
        st.link_button("Navighează (Google Maps)", f"https://www.google.com/maps/dir/?api=1&destination={l['lat']},"
                       f"{l['lon']}", width="stretch", icon=":material/navigation:")
        d = logica.diagnostic(l)
        if d.get("materiale"):
            c.h('<div class="sk-label">Nu uita să iei</div><div class="sk-chips">' +
                "".join(f'<span class="sk-chip">{c.esc(x)}</span>' for x in d["materiale"]) + "</div>")
        if st.button("Am ajuns", type="primary", width="stretch", key="am_ajuns", icon=":material/where_to_vote:"):
            try:
                mod, punctual = logica.am_ajuns(l["id"], u["id"])
                c.toast(f"Sosire confirmată de {c.sursa_api(mod)}" + ("." if punctual else " (cu întârziere)."))
                st.rerun()
            except Eroare as e:
                st.error(str(e))
        st.caption("Rețeaua mobilă verifică dacă telefonul tău e la adresa clientului (Nokia Device Location).")
        if st.button("Anulează programarea", key="danger_m_anul"):
            _actiune(logica.anuleaza_lucrare, l["id"], u["id"], "Anulată de meșter",
                     ok="Programare anulată. Contează la „programări respectate”.")

    elif s == "sosit":
        c.alerta(f'Sosire confirmată la {timp.ora(l["sosit_la"])}'
                 f'{" (la timp)" if l["punctual"] else " (cu întârziere)"}.', "trust", "pin")
        with st.expander("A apărut ceva în plus? Trimite o ofertă nouă"):
            suma = st.number_input("Suma în plus (lei)", 10, 10000, 50, step=10, key="ex_suma")
            motiv = st.text_input("Ce trebuie făcut în plus", key="ex_motiv")
            if st.button("Trimite clientului", key="ex_send", width="stretch"):
                _actiune(logica.cere_extra, l["id"], u["id"], suma, motiv, ok="Oferta pentru lucrarea în plus a fost trimisă.")
        for e in logica.extra_lucrare(l["id"]):
            st.caption(f"Lucrare în plus {c.lei(e['suma'])}: " +
                       {"trimisa": "așteaptă clientul", "acceptata": "acceptată și plătită",
                        "respinsa": "refuzată"}[e["status"]])
        with st.container(key="card_gata"):
            c.h('<div class="sk-h">Ai terminat?</div>')
            nota = st.text_area("Ce ai făcut (îl vede clientul)", key="gata_nota", height=80,
                                placeholder="Ex: Am înlocuit racordul flexibil și garniturile.")
            poza = st.file_uploader("Poză după lucrare (opțional)", type=["jpg", "jpeg", "png"], key="gata_poza")
            if st.button("Lucrare gata, cere confirmarea", type="primary", width="stretch", key="gata_btn"):
                _actiune(logica.lucrare_gata, l["id"], u["id"], nota, logica.salveaza_poza(poza, "dupa") if poza else None,
                         ok="Am cerut confirmarea clientului.")

    elif s == "gata":
        c.alerta(f'Așteptăm confirmarea clientului. Apoi primești {c.lei(bani["blocat"] * (1 - config.COMISION))} '
                 f'(din {c.lei(bani["blocat"])}, minus {config.COMISION:.0%} comision).', "escrow", "lock")

    elif s == "finalizata":
        net = bani["eliberat"] - bani["comision"]
        with st.container(key="card_incasat"):
            c.h('<div class="sk-h">Ai încasat</div>' + c.kv([("Plătit de client", c.lei(bani["eliberat"])),
                                                           (f"Comision SKILLIO ({config.COMISION:.0%})",
                                                            "−" + c.lei(bani["comision"])),
                                                           ("Încasat", c.lei(net), True)]))
        fb = logica.feedback_lucrare(l["id"])
        final = next((f for f in fb if f["etapa"] == "final"), None)
        if final and final["raspuns_la"]:
            c.h(f'<div class="sk-b">Recenzia clientului: {c.stele(final["nota"])} {c.nota_txt(final["nota"])}'
                f'{" · „" + c.esc(final["comentariu"]) + "”" if final["comentariu"] else ""}</div>')

    elif s == "disputa":
        c.alerta("Clientul a raportat o problemă. Banii rămân blocați până decide echipa SKILLIO. Scrie-i în chat.",
                 "escrow", "alert")

    elif s == "anulata":
        c.alerta(f'Lucrare anulată: {c.esc(l["anulat_motiv"] or "")}.', "escrow", "info")

    with st.expander("Detaliile lucrării"):
        _detalii(l, True)
    if s not in ("anulata",):
        with st.expander("Raportează clientul"):
            from views.comun import _form_raport
            _form_raport(u, l["id"], client["id"], config.MOTIVE_RAPORT_MESTER, "rp_mc")
