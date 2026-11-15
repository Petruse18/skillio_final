"""Lista de materiale pentru meșter, cu prețurile de azi la Dedeman, Hornbach și Leroy Merlin (Gemini + Google)."""
import streamlit as st

from core import config, logica
from services import ai
from ui import comp as c


def card(l):
    cheie = f"mat_{l['id']}"
    d = st.session_state.get(cheie)
    with st.container(key=f"card_mat_{l['id']}"):
        c.h('<div class="sk-h">Ce ai nevoie</div><div class="sk-cap">Gemini face lista de materiale și caută '
            'prețul de azi la fiecare magazin.</div>')
        if not d:
            if st.button("Fă lista și caută prețurile", key=f"btn_{cheie}", width="stretch",
                         icon=":material/shopping_cart:"):
                diag = logica.diagnostic(l)
                with st.spinner("Gemini caută prețurile în magazine…"):
                    st.session_state[cheie] = ai.lista_materiale(
                        l["titlu"], l["descriere"], config.MESERII.get(l["meserie"], {}).get("nume", "meșter"),
                        diag.get("materiale") or config.MESERII.get(l["meserie"], {}).get("materiale"))
                st.rerun()
            return
        mat = d.get("materiale", [])
        if not mat:
            st.caption("Nu am găsit materiale pentru lucrarea asta.")
            return
        cap = "".join(f"<th style='text-align:right;padding:4px'>{m.split()[0]}</th>" for m in ai.MAGAZINE)
        rows = ""
        for x in mat:
            pr = x.get("preturi") or {}
            vals = [v for v in pr.values() if isinstance(v, (int, float))]
            minim = min(vals) if vals else None
            cel = "".join(
                f"<td style='text-align:right;padding:4px;{'font-weight:700;color:var(--sk-primary)' if v == minim else ''}'>"
                f"{round(v) if isinstance(v, (int, float)) else '–'}</td>" for v in (pr.get(m) for m in ai.MAGAZINE))
            rows += (f"<tr style='border-top:1px solid var(--sk-line)'><td style='padding:4px'>{c.esc(x.get('produs'))}"
                     f"<div class='sk-cap'>{c.esc(x.get('cantitate'))} {c.esc(x.get('unitate', ''))}</div></td>{cel}</tr>")
        tot = d.get("totaluri", {})
        rtot = "".join(f"<td style='text-align:right;padding:4px'><b>{tot[m]['total'] if m in tot else '–'}</b></td>"
                       for m in ai.MAGAZINE)
        c.h(f"<table style='width:100%;font-size:13px;border-collapse:collapse'><tr class='sk-cap'>"
            f"<th style='text-align:left;padding:4px'>Produs</th>{cap}</tr>{rows}"
            f"<tr style='border-top:2px solid var(--sk-ink)'><td style='padding:4px'><b>Total (lei)</b></td>{rtot}</tr>"
            f"</table>")
        ief = d.get("cel_mai_ieftin")
        if ief and len(tot) > 1:
            scump = max(v["total"] for v in tot.values())
            c.alerta(f"Cel mai ieftin la <b>{c.esc(ief)}</b>: {tot[ief]['total']} lei. "
                     f"Economisești {scump - tot[ief]['total']} lei față de cel mai scump.", "ai", "wallet")
        if d.get("sfat"):
            st.caption(d["sfat"])
        if d.get("surse"):
            c.h('<div class="sk-cap">Surse: ' + ", ".join(
                f'<a href="{c.esc(x["url"])}" target="_blank">{c.esc(x["titlu"])}</a>' for x in d["surse"]) + "</div>")
        if d.get("sursa") == "gemini":
            st.caption("Prețuri găsite de Gemini cu Google Search.")
        elif d.get("total_orientativ"):
            st.caption(f"Total orientativ din tabelul SKILLIO: circa {d['total_orientativ']} lei.")
        if st.button("Caută din nou", key=f"re_{cheie}", type="tertiary", icon=":material/refresh:"):
            st.session_state.pop(cheie, None)
            st.rerun()
