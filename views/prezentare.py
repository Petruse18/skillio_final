"""Modul de prezentare: două telefoane simulate unul lângă altul (client și meșter) și controalele demo.

Deschide-l cu  http://localhost:8501/?mod=prezentare
Fiecare telefon e aplicația reală, într-o fereastră separată, logată cu alt cont.
Ce faci pe un telefon apare pe celălalt în 1-2 secunde.
"""
import streamlit as st

from core import config, db, logica, timp
from services import ai
from ui import comp as c


def _token(telefon):
    cheie = f"prez_{telefon}"
    if cheie not in st.session_state:
        u = logica.user_dupa_telefon(telefon)
        st.session_state[cheie] = logica.sesiune_noua(u["id"]) if u else None
    return st.session_state[cheie]


def ecran():
    st.markdown('<style>[data-testid="stMainBlockContainer"]{max-width:1400px !important;'
                'padding:20px 28px !important}</style>', unsafe_allow_html=True)
    c.h(f'<div class="sk-between"><div class="sk-row">{c.logo(44)}'
        f'<div>{c.wordmark(26)}<div class="sk-cap">{config.SLOGAN} · mod prezentare</div></div></div>'
        f'<div class="sk-badges"><span class="sk-badge {"ok" if ai.activ() else ""}">Gemini: '
        f'{"conectat" if ai.activ() else "offline"}</span></div></div>')

    t_client, t_mester = _token("+40722000001"), _token("+40722000101")
    if not t_client or not t_mester:
        st.error("Lipsesc conturile demo. Resetează datele din panoul de admin.")
        return
    col1, col2, col3 = st.columns([1, 1, 0.8], gap="large")
    with col1:
        c.h('<div class="sk-label" style="text-align:center">Ana · client</div>')
        with st.container(key="tel_client"):
            st.iframe(f"/?embed=true&s={t_client}", height=800)
    with col2:
        c.h('<div class="sk-label" style="text-align:center">Ionel · meșter</div>')
        with st.container(key="tel_mester"):
            st.iframe(f"/?embed=true&s={t_mester}", height=800)
    with col3:
        c.h('<div class="sk-h">Scenariul demo</div>')
        c.h(c.pasi([
            ("Agentul Anei", "„Vreau să renovez baia” devine 4 etape, cu cost și meseriile potrivite.", ""),
            ("Ionel trimite oferta", "Preț și oră din calendarul lui.", ""),
            ("Ana plătește, banii se blochează", f"Plus {config.PCT_PROTECTIE} taxă de protecție (mediatori umani).", ""),
            ("Ionel ajunge și reconfirmă prețul", "Poză + motiv. AI-ul dă o părere, Ana decide.", ""),
            ("Ana poate refuza", f"Plătește doar deplasarea ({config.TAXA_DEPLASARE} lei).", ""),
            ("Confirmare + 24 h", "Oricine poate deschide o dispută. Dă ceasul +1 zi: banii pleacă.", ""),
            ("Chat fără numere", "Încearcă să scrii un număr: SKILLIO îl ascunde.", ""),
            (f"SOS · {config.SOS_PRET} lei", "Apel video cu un meșter, înregistrat, cu dispută.", ""),
        ]))
        c.h(f'<div class="sk-cap">Ceasul aplicației: {timp.data_ora(timp.acum())}</div>')
        with st.container(horizontal=True):
            for zile, et in ((1, "+1 zi"), (6, "+6 zile"), (23, "+23 zile")):
                if st.button(et, key=f"pz_t{zile}", width="stretch"):
                    db.pune_setare("decalaj_zile", timp.decalaj_zile() + zile)
                    st.rerun()
        ionel = logica.user_dupa_telefon("+40722000101")
        if ionel:
            dep = st.toggle("Ionel e departe de adresă", value=bool(ionel["departe_demo"]), key="pz_dep")
            if dep != bool(ionel["departe_demo"]):
                logica.actualizeaza_profil(ionel["id"], departe_demo=int(dep))
                st.rerun()
        if st.button("Resetează demo", key="danger_pz_reset"):
            db.reseteaza()
            for k in list(st.session_state):
                if k.startswith("prez_"):
                    del st.session_state[k]
            st.rerun()
        st.caption("Pe telefonul real: deschide aplicația în browser (Chrome → Instrumente pentru dezvoltatori → "
                   "modul telefon), sau din rețeaua locală, la adresa afișată în terminal.")
