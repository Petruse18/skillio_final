"""Componente vizuale reutilizabile (stil SKILLIO) și navigarea între ecrane.

Folosim clasele din ui/components.css (designul „Cartier”). HTML-ul e scris
pe un singur rând per bloc, ca Streamlit să nu-l interpreteze ca Markdown.
"""
import html
from pathlib import Path

import streamlit as st

from core import config, timp
from services import stocare

DIR = Path(__file__).parent

# Iconițe Lucide (contur 2px), folosite în HTML. În butoane Streamlit folosim :material/...:
_L = {
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 '
              '6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    "sim": '<path d="M12 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9z"/><path d="M8 13h8v5H8z"/>',
    "pin": '<path d="M20 10c0 4.99-5.54 10.19-7.4 11.8a1 1 0 0 1-1.2 0C9.54 20.19 4 14.99 4 10a8 8 0 0 1 16 0"/>'
           '<circle cx="12" cy="10" r="3"/>',
    "lock": '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/>'
             '<path d="M12 17h.01"/>',
    "sparkles": '<path d="M9.94 15.5A2 2 0 0 0 8.5 14.06l-6.13-1.58a.5.5 0 0 1 0-.96L8.5 9.94A2 2 0 0 0 9.94 8.5l1.58-6.13'
                'a.5.5 0 0 1 .96 0L14.06 8.5A2 2 0 0 0 15.5 9.94l6.13 1.58a.5.5 0 0 1 0 .96L15.5 14.06a2 2 0 0 0-1.44 '
                '1.44l-1.58 6.13a.5.5 0 0 1-.96 0z"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "star": '<path d="M11.52 2.3a.53.53 0 0 1 .96 0l2.31 4.68a2.12 2.12 0 0 0 1.6 1.16l5.16.76a.53.53 0 0 1 .3.9l-3.74 '
            '3.64a2.12 2.12 0 0 0-.61 1.88l.88 5.14a.53.53 0 0 1-.77.56l-4.62-2.43a2.12 2.12 0 0 0-1.97 0L6.4 21.01a.53'
            '.53 0 0 1-.77-.56l.88-5.14a2.12 2.12 0 0 0-.61-1.88L2.16 9.8a.53.53 0 0 1 .29-.9l5.17-.76a2.12 2.12 0 0 0 '
            '1.6-1.16z"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 '
              '2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    "cal": '<path d="M8 2v4M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "wallet": '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 '
              '1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    "leaf": '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/>'
            '<path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
}


def ico(nume, size=18):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_L[nume]}</svg>')


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def h(markup: str):
    """Afișează un bloc de HTML (clasele sk-*)."""
    st.markdown(f'<div class="sk">{markup}</div>', unsafe_allow_html=True)


def css():
    tokens = (DIR / "tokens.css").read_text(encoding="utf-8")
    comp = (DIR / "components.css").read_text(encoding="utf-8")
    extra = (DIR / "streamlit.css").read_text(encoding="utf-8") + (DIR / "modern.css").read_text(encoding="utf-8")
    fonturi = ("@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700"
               "&family=Geist+Mono:wght@500;600&display=swap');")
    st.markdown(f"<style>{fonturi}</style>", unsafe_allow_html=True)
    for bucata in (tokens, comp, extra):
        curat = "\n".join(r for r in bucata.splitlines() if r.strip())
        st.markdown(f"<style>{curat}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Navigare: ecranul curent stă în URL (?p=...&id=...), ca să supraviețuiască
# reîmprospătării și să meargă în ferestrele modului de prezentare.
# ---------------------------------------------------------------------------
def pagina():
    return st.query_params.get("p", "acasa"), st.query_params.get("id")


def go(p, id_=None, push=True):
    cur = pagina()
    if push and cur != (p, str(id_) if id_ is not None else None):
        st.session_state.setdefault("istoric", []).append(cur)
        st.session_state["istoric"] = st.session_state["istoric"][-20:]
    st.query_params["p"] = p
    if id_ is not None:
        st.query_params["id"] = str(id_)
    elif "id" in st.query_params:
        del st.query_params["id"]
    st.rerun()


def inapoi(implicit="acasa"):
    ist = st.session_state.get("istoric", [])
    if ist:
        p, i = ist.pop()
        go(p, i, push=False)
    go(implicit, push=False)


def toast(msg, icon="✅"):
    st.session_state["_toast"] = (msg, icon)


def arata_toast():
    t = st.session_state.pop("_toast", None)
    if t:
        st.toast(t[0], icon=t[1])


def bara_sus(titlu, inapoi_la=None, dreapta=None):
    """Bară de sus cu buton Înapoi."""
    with st.container(key=f"appbar_{titlu[:12]}", horizontal=True, vertical_alignment="center"):
        if inapoi_la is not False:
            if st.button("", icon=":material/arrow_back:", key=f"back_{titlu[:12]}", type="tertiary"):
                inapoi(inapoi_la or "acasa")
        st.markdown(f'<div class="sk"><div class="sk-h" style="font-size:19px">{esc(titlu)}</div></div>',
                    unsafe_allow_html=True)
        if dreapta:
            dreapta()


# ---------------------------------------------------------------------------
# Bucăți de HTML
# ---------------------------------------------------------------------------
def initiale(nume):
    p = (nume or "?").split()
    return (p[0][0] + (p[-1][0] if len(p) > 1 else "")).upper()


def avatar(u, mare=False):
    tick = f'<span class="tick">{ico("check", 10)}</span>' if u.get("numar_verificat") else ""
    if u.get("poza") and img_uri(u["poza"]):
        img = f'<img src="{img_uri(u["poza"])}" style="width:100%;height:100%;border-radius:50%;object-fit:cover">'
        return f'<div class="sk-av{" lg" if mare else ""}">{img}{tick}</div>'
    return f'<div class="sk-av{" lg" if mare else ""}">{esc(initiale(u.get("nume")))}{tick}</div>'


def logo(marime=64):
    """Logo-ul SKILLIO (din designul final): S alb pe pătrat verde, cu frunză."""
    return (f'<svg width="{marime}" height="{marime}" viewBox="0 0 48 48" aria-hidden="true"><rect width="48" '
            f'height="48" rx="14" fill="var(--sk-primary)"></rect><path d="M31.5 17.2c-1.4-2.4-4.2-3.7-7.6-3.7-4.6 '
            f'0-7.8 2.4-7.8 5.9 0 7.4 15.8 4.3 15.8 11.2 0 3.6-3.3 5.9-8.1 5.9-3.8 0-6.8-1.5-8.3-4.2" fill="none" '
            f'stroke="#fff" stroke-width="4.6" stroke-linecap="round"></path><path d="M33 6.5c3.8 0 6.8 2.8 6.8 '
            f'6.7-3.8 0-6.8-2.8-6.8-6.7z" fill="var(--sk-leaf)"></path></svg>')


def wordmark(marime=34):
    return (f'<div style="font-weight:800;font-size:{marime}px;letter-spacing:-.045em;color:var(--sk-ink);'
            f'line-height:1">skill<b style="color:var(--sk-primary)">io</b></div>')


def card_hero(titlu, sub, suma=None):
    """Cardul verde „Lucrarea ta de azi” din design."""
    bani = (f'<div><span class="sk-badge escrow" style="background:var(--sk-surface)">{ico("lock", 12)} '
            f'{lei(suma)} blocați</span></div>' if suma else "")
    return (f'<div class="sk-card hero" style="gap:6px"><b class="sk-b">{esc(titlu)}</b>'
            f'<div class="sk-cap">{esc(sub)}</div>{bani}</div>')


def asculta(text, key):
    """Butonul „Ascultă”: voce ElevenLabs dacă avem cheie, altfel vocea browserului."""
    from services import voce
    if st.button("Ascultă", icon=":material/volume_up:", key=f"link_voce_{key}", type="tertiary"):
        st.session_state[f"_voce_{key}"] = True
    if not st.session_state.pop(f"_voce_{key}", False):
        return
    audio = voce.sintetizeaza(text)
    if audio:
        st.audio(audio, format="audio/mpeg", autoplay=True)
        return
    import json as _json
    st.html(f"""<script>(function(){{const s=window.speechSynthesis;if(!s)return;s.cancel();
const u=new SpeechSynthesisUtterance({_json.dumps(text)});u.lang="ro-RO";u.rate=1.0;s.speak(u);}})();</script>""",
            unsafe_allow_javascript=True)


def trust_pill(scor):
    return f'<span class="sk-tpill"><i>{ico("shield", 11)}</i>{scor}</span>'


def trust_inel(scor, marime="", eticheta=True):
    mic = '<small>TRUST SCORE</small>' if marime == "lg" and eticheta else ""
    return f'<div class="sk-trust {marime}" style="--v:{scor}"><b>{scor}{mic}</b></div>'


def insigne_nokia(u, sosire=None):
    b = []
    if u.get("numar_verificat"):
        b.append(f'<span class="sk-badge trust">{ico("check", 12)} Număr verificat</span>')
    if u.get("sim_ok"):
        b.append(f'<span class="sk-badge trust">{ico("sim", 12)} SIM stabil</span>')
    else:
        b.append(f'<span class="sk-badge danger">{ico("alert", 12)} SIM schimbat recent</span>')
    if u.get("act_status") == "verificat":
        b.append(f'<span class="sk-badge ok">{ico("shield", 12)} Act verificat</span>')
    if sosire:
        b.append(f'<span class="sk-badge trust">{ico("pin", 12)} Sosire confirmată</span>')
    return '<div class="sk-badges">' + "".join(b) + "</div>"


def stele(nota, n=5):
    if nota is None:
        return '<span class="sk-cap">fără recenzii</span>'
    plin = int(round(nota))
    return (f'<span style="color:var(--sk-escrow);letter-spacing:1px">{"★" * plin}{"☆" * (n - plin)}</span>')


def nota_txt(x):
    return f"{x:.1f}".replace(".", ",") if x is not None else "–"


def badge_status(status):
    from core.logica import STATUS
    txt, ton = STATUS.get(status, (status, "neutru"))
    cls = {"ok": "ok", "escrow": "escrow", "danger": "danger"}.get(ton, "")
    return f'<span class="sk-badge {cls}">{esc(txt)}</span>'


def badge_urgent():
    return f'<span class="sk-badge urgent">{ico("alert", 12)} Urgent +{config.PCT_URGENT}</span>'


def meserie_nume(k):
    return config.MESERII.get(k, {}).get("nume", k)


def img_uri(ref):
    """Adresa unei poze (cloud sau locală), pentru <img src>."""
    return stocare.url(ref)


def poza(ref, inaltime=170):
    src = img_uri(ref) if ref else ""
    if src:
        h(f'<img class="sk-photo" src="{src}" style="width:100%;height:{inaltime}px">')


def alerta(text, tip="ai", icon="info"):
    h(f'<div class="sk-alert {tip}">{ico(icon, 18)}<div>{text}</div></div>')


def sursa_api(mod):
    """Etichetă sinceră: rezultatul vine de la rețea sau e simulat."""
    return "rețeaua Nokia" if mod == "live" else "simulare (fără cheie Nokia)"


def card_mester(m, extra_html=""):
    t = m["trust"]
    meserii = ", ".join(meserie_nume(x) for x in m["meserii_l"])
    dist = ""
    if m.get("dist") is not None:
        from services.geo import km
        dist = f' · {km(m["dist"])}'
    disp = ('<span class="sk-badge ok">Disponibil</span>' if m["disponibil"]
            else '<span class="sk-badge">Indisponibil</span>')
    nota = (f'{stele(t["medie"])} <b>{nota_txt(t["medie"])}</b> <span class="sk-cap">({t["nr_recenzii"]})</span>'
            if t["medie"] else '<span class="sk-cap">fără recenzii încă</span>')
    tarif = f'de la {m["tarif_ora"]} lei/oră' if m.get("tarif_ora") else ""
    sim = "" if m["sim_ok"] else '<span class="sk-badge danger">SIM schimbat recent</span>'
    return (f'<div class="sk-row top">{avatar(m)}<div class="sk-grow"><div class="sk-between"><div class="sk-h">'
            f'{esc(m["nume"])}</div>{trust_pill(t["scor"])}</div><div class="sk-cap">{esc(meserii)} · '
            f'{esc(m["cartier"])}{dist}</div><div class="sk-b" style="margin-top:4px">{nota}</div></div></div>'
            f'<div class="sk-between"><div class="sk-badges">{disp}'
            f'{sim}'
            f'<span class="sk-badge">{m["experienta_ani"]} ani exp.</span></div>'
            f'<span class="sk-cap">{tarif}</span></div>{extra_html}')


def factori_trust(t):
    rows = []
    for f in t["factori"]:
        proc = f["puncte"] / f["max"] * 100
        pts = f'{f["puncte"]:.0f}' if f["puncte"] == int(f["puncte"]) else nota_txt(f["puncte"])
        rows.append(f'<div class="sk-factor"><span><b>{esc(f["eticheta"])}</b><br><span class="sk-cap">'
                    f'{esc(f["detaliu"])}</span></span><span class="pts">{pts}<small>/{f["max"]}</small></span>'
                    f'<span class="bar"><i style="width:{proc:.0f}%;{"opacity:.45" if f["fara_date"] else ""}"></i>'
                    f'</span></div>')
    return '<div class="sk-factors">' + "".join(rows) + "</div>"


def gol(text, icon="leaf"):
    h(f'<div class="sk-col" style="align-items:center;text-align:center;padding:24px 8px;color:var(--sk-muted)">'
      f'{ico(icon, 32)}<div class="sk-b">{text}</div></div>')


def kv(rows):
    out = []
    for r in rows:
        k, v = r[0], r[1]
        tot = len(r) > 2 and r[2]
        cls = ' class="tot"' if tot else ""
        out.append(f"<dt{cls}>{esc(k)}</dt><dd{cls}>{v}</dd>")
    return '<dl class="sk-kv">' + "".join(out) + "</dl>"


def pasi(lista):
    """lista de (titlu, detaliu, stare) cu stare în done | now | ''"""
    li = []
    for i, (t, d, s) in enumerate(lista, 1):
        semn = ico("check", 13) if s == "done" else str(i)
        li.append(f'<li class="{s}"><span class="d">{semn}</span><div><b>{esc(t)}</b><span>{d}</span></div></li>')
    return '<ol class="sk-steps">' + "".join(li) + "</ol>"


def lei(x):
    return timp.lei(x)
