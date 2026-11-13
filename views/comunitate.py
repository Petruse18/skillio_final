"""Living Labs: părerea oamenilor (chestionar în aplicație) și „Ce e nou” (cum am schimbat aplicația după feedback)."""
import streamlit as st

from core import db, timp
from ui import comp as c

# Ce am schimbat și de ce. Adaugă aici fiecare versiune nouă. După chestionar, pune la „de ce”
# citate REALE din răspunsuri (Admin → Living Labs), ca juriul să vadă că ați ascultat oamenii.
NOUTATI = [
    ("15 nov 2026", "v1.3", "Plăți verificabile pe blockchain", [
        "Plata blocată, eliberarea și returnarea au acum fiecare câte o tranzacție publică pe Solana (devnet).",
        "La final, „pașaportul lucrării” (amprenta ei) rămâne scris on-chain.",
    ], "Plata blocată cere încredere: oricine poate verifica public că banii chiar sunt blocați și unde ajung."),
    ("14 nov 2026", "v1.2", "Ascultă diagnosticul și ofertele", [
        "Butonul „Ascultă” citește cu voce diagnosticul AI și ofertele primite.",
    ], "Nu toată lumea citește ușor textele mici de pe telefon, mai ales părinții și bunicii."),
    ("14 nov 2026", "v1.1", "Producție: login sigur, poze în cloud, notificări", [
        "Intrare prin Auth0 (cod pe email sau SMS), în loc de orice număr de telefon.",
        "Email și SMS la ofertă nouă, programare, plată și confirmare.",
    ], "O ofertă ratată pentru că nu erai în aplicație e o lucrare pierdută pentru meșter."),
    ("13 nov 2026", "v1.0", "Prima versiune", [
        "Solicitare cu poză, diagnostic AI, oferte, programare, plată blocată, sosire confirmată de rețea.",
        "Trust Score din 7 factori și feedback după o zi, o săptămână și o lună.",
    ], "Problema de la care am pornit: nu știi pe cine să chemi și ți-e frică să nu dai banii degeaba."),
]

INTREBARI = [
    ("usor", "Cât de ușor ți-a fost să ceri o ofertă?"),
    ("incredere", "Cât de mult ai avea încredere să plătești prin SKILLIO?"),
    ("recomanda", "Cât de probabil e să recomanzi SKILLIO unui prieten?"),
]


def feedback(u):
    c.bara_sus("Spune-ne părerea", "cont")
    c.h('<div class="sk-b" style="color:var(--sk-muted)">Construim SKILLIO împreună cu oamenii din Timișoara. '
        'Durează un minut, iar fiecare răspuns ajunge direct la echipă.</div>')
    note = {}
    for k, q in INTREBARI:
        c.h(f'<div class="sk-b"><b>{q}</b></div>')
        v = st.feedback("stars", key=f"sd_{k}")
        note[k] = None if v is None else v + 1
    ar = st.radio("Ai folosi SKILLIO data viitoare când ai nevoie de un meșter?",
                  ["Da, sigur", "Poate", "Nu"], index=None, key="sd_ar", horizontal=True)
    lipsa = st.text_area("Ce ți-a lipsit sau ce ai schimba?", key="sd_lipsa", height=90)
    if st.button("Trimite părerea", type="primary", width="stretch", key="sd_send"):
        if any(v is None for v in note.values()) or not ar:
            st.error("Dă o notă la fiecare întrebare și alege un răspuns.")
        else:
            db.ex("INSERT INTO sondaj(user_id, rol, usor, incredere, recomanda, ar_folosi, ce_lipseste, creat_la) "
                  "VALUES(?,?,?,?,?,?,?,?)", (u["id"], u["rol"], note["usor"], note["incredere"], note["recomanda"],
                                              ar, lipsa.strip(), timp.iso(timp.acum())))
            for k in [f"sd_{x}" for x, _ in INTREBARI] + ["sd_ar", "sd_lipsa"]:
                st.session_state.pop(k, None)
            c.toast("Mulțumim! Ne uităm la fiecare răspuns.")
            c.go("noutati")


def noutati(u):
    c.bara_sus("Ce e nou", "cont")
    c.h('<div class="sk-b" style="color:var(--sk-muted)">Ce am schimbat și de ce. Următoarea versiune pornește de la părerea ta.</div>')
    for data, ver, titlu, puncte, din in NOUTATI:
        li = "".join(f"<li>{c.esc(p)}</li>" for p in puncte)
        c.h(f'<div class="sk-card" style="gap:6px"><div class="sk-between"><b class="sk-h">{c.esc(titlu)}</b>'
            f'<span class="sk-badge">{ver}</span></div><div class="sk-cap">{data}</div>'
            f'<ul class="sk-b" style="margin:0;padding-left:18px">{li}</ul>'
            f'<div class="sk-alert ai" style="margin-top:4px">{c.ico("info", 16)}<div><b>De ce:</b> '
            f'{c.esc(din)}</div></div></div>')
    if st.button("Spune-ne părerea", type="primary", width="stretch", key="nout_fb"):
        c.go("feedback")


def rezultate():
    """Pentru panoul de admin: ce spun oamenii."""
    r = db.q("SELECT * FROM sondaj ORDER BY id DESC")
    if not r:
        st.caption("Încă niciun răspuns. Trimite linkul aplicației și roagă oamenii să apese „Spune-ne părerea”.")
        return
    n = len(r)
    medie = {k: sum(x[k] for x in r) / n for k, _ in INTREBARI}
    da = sum(1 for x in r if x["ar_folosi"] == "Da, sigur") / n
    c.h('<div class="sk-stats">' + "".join(
        f'<div class="sk-stat"><span class="v">{medie[k]:.1f}</span><span class="l">{q}</span></div>'
        for k, q in INTREBARI) + f'<div class="sk-stat"><span class="v">{da:.0%}</span><span class="l">Ar folosi '
        f'sigur ({n} răspunsuri)</span></div></div>')
    for x in r[:10]:
        if x["ce_lipseste"]:
            st.caption(f'„{x["ce_lipseste"]}” · {x["rol"]}')
