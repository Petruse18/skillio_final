"""Asistentul AI: din descriere (și poză) scoate meseria, urgența, prețul și ce să aducă meșterul.

Cu GEMINI_API_KEY în .env folosește Gemini. Fără cheie (sau dacă pică internetul)
folosește o clasificare simplă după cuvinte-cheie, ca demo-ul să nu se blocheze.
Rezultatul are mereu aceeași formă (vezi `_rezervă`).
"""
import json
import logging
import re

from core import config

log = logging.getLogger("skillio.ai")

PROMPT = """Ești asistentul aplicației SKILLIO din Timișoara, care leagă clienți de meșteri.
Clientul descrie o problemă din casă (și uneori trimite o poză). Răspunde DOAR cu JSON valid, în română:
{{
  "meserie": una dintre {meserii},
  "titlu": "titlu scurt al lucrării, max 6 cuvinte",
  "urgenta": "urgent" | "azi" | "saptamana" | "flexibil",
  "descriere": "descrierea problemei, reformulată clar, 1-2 propoziții",
  "pret_min": număr (lei, manoperă + materiale uzuale, prețuri Timișoara 2026),
  "pret_max": număr,
  "durata_min": număr (minute),
  "materiale": ["ce ar trebui să aducă meșterul", "..."],
  "intrebari": ["max 2 întrebări scurte care l-ar ajuta pe meșter", "..."],
  "sfat_siguranta": "ce să facă clientul până vine meșterul, 1 propoziție",
  "incredere": număr între 0 și 1
}}
Nu pune diagnostic definitiv: evaluarea finală o face meșterul.

Descrierea clientului: {text}"""


def activ() -> bool:
    return bool(config.GEMINI_API_KEY)


def _rezerva(text: str) -> dict:
    t = (text or "").lower()
    scoruri = {k: sum(1 for c in m["cuvinte"] if c in t) for k, m in config.MESERII.items()}
    meserie = max(scoruri, key=scoruri.get)
    if scoruri[meserie] == 0:
        meserie = "universal"
    m = config.MESERII[meserie]
    if any(c in t for c in ["urgent", "inund", "scântei", "scantei", "fum", "miros de gaz", "nu am apă",
                            "nu am apa", "nu am curent", "baltă", "balta", "curge tare", "blocat afar"]):
        urgenta = "urgent"
    elif any(c in t for c in ["azi", "nu merge", "nu mai merge", "nu funcțion", "nu functioneaza", "curge", "stricat"]):
        urgenta = "azi"
    else:
        urgenta = "saptamana"
    prop = re.split(r"[.!?\n]", text.strip())[0] if text else ""
    cuv = prop.split()[:6]
    while cuv and cuv[-1].lower().strip(",;:") in ("în", "in", "de", "la", "pe", "cu", "și", "si", "din", "sub", "a", "e"):
        cuv.pop()
    titlu = " ".join(cuv).rstrip(",;:") or m["nume"]
    return {
        "meserie": meserie,
        "titlu": titlu[:1].upper() + titlu[1:],
        "urgenta": urgenta,
        "descriere": text.strip(),
        "pret_min": m["pret"][0],
        "pret_max": m["pret"][1],
        "durata_min": m["durata"],
        "materiale": m["materiale"],
        "intrebari": ["De când a apărut problema?", "Poți trimite o poză de aproape?"],
        "sfat_siguranta": m["sfat"],
        "incredere": 0.55 if scoruri[meserie] else 0.3,
        "sursa": "reguli",
    }


def _curata(d: dict, text: str) -> dict:
    baza = _rezerva(text)
    if d.get("meserie") not in config.MESERII:
        d["meserie"] = baza["meserie"]
    if d.get("urgenta") not in ("urgent", "azi", "saptamana", "flexibil"):
        d["urgenta"] = baza["urgenta"]
    for k in ("pret_min", "pret_max", "durata_min", "incredere"):
        try:
            d[k] = float(d.get(k)) if k == "incredere" else int(float(d.get(k)))
        except (TypeError, ValueError):
            d[k] = baza[k]
    if d["pret_max"] < d["pret_min"]:
        d["pret_min"], d["pret_max"] = d["pret_max"], d["pret_min"]
    for k in ("titlu", "descriere", "sfat_siguranta"):
        if not isinstance(d.get(k), str) or not d[k].strip():
            d[k] = baza[k]
    for k in ("materiale", "intrebari"):
        if not isinstance(d.get(k), list):
            d[k] = baza[k]
        d[k] = [str(x) for x in d[k]][:5]
    return d


def diagnosticheaza(text: str, poza: bytes | None = None, mime: str = "image/jpeg", media=None) -> dict:
    if activ():
        try:
            from google.genai import types
            parti = [PROMPT.format(meserii=list(config.MESERII), text=text or "(fără text, doar poză)")]
            if poza:
                parti.append(types.Part.from_bytes(data=poza, mime_type=mime))
            parti += _parti_media(media)
            d = _gemini_json(parti)
            d = _curata(d, text)
            d["sursa"] = "gemini"
            return d
        except Exception as e:  # noqa: BLE001
            log.warning("Gemini a eșuat, folosesc regulile: %s", e)
    return _rezerva(text)


# ---------------------------------------------------------------------------
# Părerea AI despre prețul reconfirmat la fața locului (doar consultativ: decide clientul)
# ---------------------------------------------------------------------------
PROMPT_PRET = """Ești consultantul de prețuri SKILLIO din Timișoara (prețuri 2026). Un meșter a ajuns la client și
reconfirmă prețul. Lucrarea: {titlu}. Descrierea clientului: {descriere}. Estimarea inițială: {pmin}-{pmax} lei.
Oferta acceptată: {vechi} lei. Prețul reconfirmat acum: {nou} lei. Motivul meșterului: {motiv}.
Uită-te și la poză, dacă există. Răspunde DOAR cu JSON valid, în română:
{{"verdict": "rezonabil" | "de_discutat" | "ridicat",
  "interval_min": număr, "interval_max": număr,
  "explicatie": "1-2 propoziții simple pentru client: ce se vede în poză și dacă motivul justifică prețul"}}"""


_MODELE = []  # modelul care a mers ultima dată e pus primul


NOTA_MEDIA = ("Clientul a trimis și {ce}. Privește și ascultă atent (apă care curge sau picură, zgomote de la "
              "centrală sau mașină, scântei, fum) și spune în explicație, la început, ce ai observat în {ce}.")


def _parti_media(media):
    """Video și audio trimise direct la Gemini (multimodal). media = [(bytes, mime), ...]"""
    from google.genai import types
    parti, ce = [], []
    for date, mime in media or []:
        if date:
            parti.append(types.Part.from_bytes(data=date, mime_type=mime))
            ce.append("o înregistrare video" if mime.startswith("video") else "o înregistrare vocală")
    if parti:
        parti.append(NOTA_MEDIA.format(ce=" și ".join(dict.fromkeys(ce))))
    return parti


def cauta_pret_web(material: str) -> dict:
    """Google Search grounding: prețul de azi al unui material la magazinele din Timișoara, cu surse."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=types.HttpOptions(api_version="v1beta"))
    prompt = (f"Caută prețul actual (lei, cu TVA) pentru „{material}” la magazinele de bricolaj din România "
              "(Dedeman, Hornbach, Leroy Merlin, Brico Depot). Răspunde DOAR cu JSON: "
              '{"pret_min": număr, "pret_max": număr, "unitate": "mp|buc|l|kg", "nota": "o propoziție"}')
    eroare = None
    for m in list(_MODELE) or [config.GEMINI_MODEL]:
        try:
            r = client.models.generate_content(model=m, contents=prompt, config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.1))
        except Exception as e:  # noqa: BLE001
            eroare = e
            continue
        d = _json_din_text(r.text)
        surse = []
        try:
            for ch in r.candidates[0].grounding_metadata.grounding_chunks or []:
                if ch.web and ch.web.uri:
                    surse.append({"titlu": ch.web.title or ch.web.uri, "url": ch.web.uri})
        except (AttributeError, IndexError, TypeError):
            pass
        d["surse"] = surse[:3]
        return d
    raise eroare or RuntimeError("căutarea nu a mers")


MAGAZINE = ("Dedeman", "Hornbach", "Leroy Merlin")


def lista_materiale(titlu: str, descriere: str, meserie: str, sugestii=None) -> dict:
    """Lista de materiale pentru meșter, cu prețul de azi la fiecare magazin (Google Search grounding)."""
    if activ():
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=types.HttpOptions(api_version="v1beta"))
        prompt = (f"Ești un {meserie} din Timișoara. Lucrarea: {titlu}. Descrierea clientului: {descriere}. "
                  f"Materiale sugerate: {', '.join(sugestii or [])}. Fă lista exactă de materiale și consumabile "
                  f"necesare (maximum 7), cu cantități realiste. Caută pe Google prețul de azi (lei, cu TVA) la "
                  f"{', '.join(MAGAZINE)} pentru fiecare. Dacă un magazin nu are produsul, pune null. "
                  'Răspunde DOAR cu JSON: {"materiale": [{"produs": "nume concret", "cantitate": număr, '
                  '"unitate": "buc|m|mp|kg|l", "preturi": {"Dedeman": preț unitar sau null, "Hornbach": ..., '
                  '"Leroy Merlin": ...}}], "sfat": "o propoziție practică pentru meșter"}')
        for m in list(_MODELE) or [config.GEMINI_MODEL, "gemini-3.5-flash", "gemini-flash-latest"]:
            try:
                r = client.models.generate_content(model=m, contents=prompt, config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.1))
                d = _json_din_text(r.text)
            except Exception as e:  # noqa: BLE001
                log.warning("Gemini (materiale) %s a eșuat: %s", m, e)
                continue
            surse = []
            try:
                for ch in r.candidates[0].grounding_metadata.grounding_chunks or []:
                    if ch.web and ch.web.uri:
                        surse.append({"titlu": ch.web.title or ch.web.uri, "url": ch.web.uri})
            except (AttributeError, IndexError, TypeError):
                pass
            d["surse"], d["sursa"] = surse[:5], "gemini"
            return _totaluri(d)
    from services import unelte
    mat, orient = [], 0
    for x in sugestii or []:
        r = unelte.pret_materiale(x, 1)
        orient += r.get("total", 0)
        mat.append({"produs": x, "cantitate": 1, "unitate": r.get("unitate", "buc"), "preturi": {}})
    return _totaluri({"materiale": mat, "surse": [], "sursa": "reguli", "total_orientativ": orient,
                      "sfat": "Fără conexiune la Gemini nu pot căuta prețurile din magazine."})


def _totaluri(d: dict) -> dict:
    tot = {}
    for mg in MAGAZINE:
        sume = []
        for x in d.get("materiale", []):
            p = (x.get("preturi") or {}).get(mg)
            if isinstance(p, (int, float)):
                sume.append(p * float(x.get("cantitate") or 1))
        if sume:
            tot[mg] = {"total": round(sum(sume)), "gasite": len(sume)}
    n = len(d.get("materiale", []))
    complete = {k: v for k, v in tot.items() if v["gasite"] == n} or tot
    d["totaluri"] = tot
    d["cel_mai_ieftin"] = min(complete, key=lambda k: complete[k]["total"]) if complete else None
    return d


LIMBI = {"ro": "Română", "en": "English", "uk": "Українська", "hu": "Magyar", "de": "Deutsch", "it": "Italiano"}


def traduce(texte: list[str], limba: str) -> list[str]:
    """Traduce mesajele din chat în limba aleasă de utilizator (un singur apel pentru toate)."""
    if not texte or not activ():
        return list(texte)
    nume = LIMBI.get(limba, limba)
    d = _gemini_json([f"Tradu fiecare mesaj în {nume}, natural, ca într-un chat între un client și un meșter. "
                      "Păstrează numele și sumele. Dacă un mesaj e deja în limba aceasta, lasă-l neschimbat. "
                      'Răspunde DOAR cu JSON: {"traduceri": ["..."]}, în aceeași ordine. Mesaje: '
                      + json.dumps(texte, ensure_ascii=False)])
    t = d.get("traduceri") if isinstance(d, dict) else None
    return t if isinstance(t, list) and len(t) == len(texte) else list(texte)


def timp_azi():
    from core import timp
    return timp.azi().isoformat()


def _json_din_text(t: str):
    t = (t or "").strip()
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1] if a >= 0 and b > a else t)


def _cu_jurnal(f, jurnal):
    """Învelește o unealtă ca să notăm ce a calculat Gemini (apare în aplicație la „Cum am calculat”)."""
    import functools

    @functools.wraps(f)
    def w(*a, **k):
        r = f(*a, **k)
        jurnal.append({"unealta": f.__name__, "argumente": k or list(a), "rezultat": r})
        return r
    return w


def _gemini_json(parti, unelte=None, jurnal=None):
    """Încearcă mai multe modele Gemini; dacă unul lipsește sau e supraîncărcat, trece la următorul."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=types.HttpOptions(api_version="v1beta"))
    if not _MODELE:
        for m in (config.GEMINI_MODEL, "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-flash-lite-latest",
                  "gemini-flash-latest", "gemini-3-flash-preview", "gemini-2.5-flash"):
            if m and m not in _MODELE:
                _MODELE.append(m)
    eroare = None
    for m in list(_MODELE):
        try:
            if unelte:
                if jurnal is not None:
                    jurnal.clear()
                cfg = types.GenerateContentConfig(
                    temperature=0.2, tools=[_cu_jurnal(f, jurnal if jurnal is not None else []) for f in unelte],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=12))
            else:
                cfg = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2)
            r = client.models.generate_content(model=m, contents=parti, config=cfg)
        except Exception as e:  # noqa: BLE001
            log.info("Gemini %s indisponibil, încerc alt model", m)
            if any(k in str(e) for k in ("404", "NOT_FOUND", "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED",
                                         "500", "INTERNAL")):
                eroare = e
                continue
            raise
        if _MODELE[0] != m:
            _MODELE.remove(m)
            _MODELE.insert(0, m)
        d = _json_din_text(r.text)
        return d[0] if isinstance(d, list) else d
    raise eroare or RuntimeError("niciun model Gemini disponibil")


def verifica_pret(l, vechi, nou, motiv, poza=None, mime="image/jpeg") -> dict:
    try:
        d = json.loads(l.get("diagnostic") or "{}")
    except (TypeError, ValueError):
        d = {}
    pmin, pmax = d.get("pret_min") or round(vechi * 0.8), d.get("pret_max") or round(vechi * 1.2)
    if activ():
        try:
            from google.genai import types
            parti = [PROMPT_PRET.format(titlu=l["titlu"], descriere=l["descriere"], pmin=pmin, pmax=pmax,
                                        vechi=round(vechi), nou=round(nou), motiv=motiv)]
            if poza:
                parti.append(types.Part.from_bytes(data=poza, mime_type=mime))
            r = _gemini_json(parti)
            if r.get("verdict") in ("rezonabil", "de_discutat", "ridicat"):
                r["sursa"] = "gemini"
                return r
        except Exception as e:  # noqa: BLE001
            log.warning("Gemini (preț) a eșuat: %s", e)
    sus = max(pmax, vechi) * 1.15
    verdict = "rezonabil" if nou <= sus else ("de_discutat" if nou <= sus * 1.3 else "ridicat")
    return {"verdict": verdict, "interval_min": round(min(pmin, vechi)), "interval_max": round(sus),
            "explicatie": ("Prețul e în intervalul obișnuit pentru o lucrare de acest fel." if verdict == "rezonabil"
                           else "Prețul e peste ce se plătește de obicei. Cere meșterului detalii înainte să accepți."),
            "sursa": "reguli"}


# ---------------------------------------------------------------------------
# Agentul clientului: explică problema și împarte lucrările mari în etape
# ---------------------------------------------------------------------------
PROMPT_PLAN = """Ești agentul personal al unui client SKILLIO din Timișoara. Clientul descrie ce vrea să repare
sau să renoveze. Explică-i pe înțeles și, dacă e nevoie de mai multe meserii, împarte lucrarea în etape în ordinea
corectă (ex. baie: instalator, electrician, faianțar, zugrav). Meserii permise: {meserii}.
La final, după ce ai calculat cu uneltele, răspunde DOAR cu JSON valid (fără ```), în română:
{{"explicatie": "2-3 propoziții: ce se întâmplă și ce trebuie făcut",
  "pret_min": număr, "pret_max": număr, "zile": număr,
  "etape": [{{"titlu": "max 5 cuvinte", "meserie": una din meseriile permise, "descriere": "1 propoziție",
             "pret_min": număr, "pret_max": număr, "durata_min": număr, "materiale": ["..."]}}],
  "sfat": "o propoziție: la ce să fie atent clientul",
  "termen": "YYYY-MM-DD dacă clientul a spus până când vrea lucrarea, altfel null",
  "buget": număr în lei dacă clientul a spus un buget, altfel null,
  "taieri": ["dacă bugetul nu ajunge: ce poate schimba clientul și cât economisește, ex. „faianță economică: -900 lei”"]}}
Azi este {azi}. Durata etapelor (durata_min) e în minute de lucru efectiv; o zi de lucru are 480 de minute.
Calculează costurile DOAR cu uneltele, nu din memorie: pentru fiecare etapă apelează tarif_manopera
(estimează cantitatea: mp, bucăți, circuite; o baie obișnuită are ~4 mp pardoseală și ~20 mp faianță) și
pret_materiale (calitate "mediu" dacă clientul nu spune altfel), iar preturi_platforma pentru meseria etapei.
Pentru cel mult 2 materiale principale (cele mai scumpe), verifică prețul de azi cu pret_live_material.
Prețul etapei = manoperă + materiale. Pentru totalul final apelează taxe_skillio și pune în explicație cât plătește
clientul cu taxa de protecție. O problemă mică are o singură etapă.
Cererea clientului: {text}"""

_SABLON_BAIE = [("Instalații sanitare noi", "instalator", "Trasee noi de apă și scurgere, înainte de faianță.", 900, 1800, 480),
                ("Circuite și prize baie", "electrician", "Circuit separat, prize protejate și corpuri de iluminat.", 500, 1100, 300),
                ("Montaj gresie și faianță", "universal", "Hidroizolație, apoi gresie și faianță.", 2200, 4200, 1440),
                ("Finisaje și zugrăveli", "zugrav", "Tavan și pereți, vopsea rezistentă la umezeală.", 400, 900, 300)]


def planifica(text: str, poza: bytes | None = None, mime: str = "image/jpeg", media=None) -> dict:
    if activ():
        try:
            from google.genai import types
            parti = [PROMPT_PLAN.format(meserii=list(config.MESERII), text=text or "(doar poză)",
                                       azi=timp_azi())]
            if poza:
                parti.append(types.Part.from_bytes(data=poza, mime_type=mime))
            parti += _parti_media(media)
            from services import unelte
            jurnal = []
            d = _gemini_json(parti, unelte.UNELTE, jurnal)
            d["calcule"] = [dict(j, nume=unelte.NUME.get(j["unealta"], j["unealta"])) for j in jurnal]
            etape = [e for e in d.get("etape", []) if isinstance(e, dict) and e.get("titlu")]
            for e in etape:
                if e.get("meserie") not in config.MESERII:
                    e["meserie"] = _rezerva(e.get("titlu", "") + " " + e.get("descriere", ""))["meserie"]
            if etape:
                d["etape"], d["sursa"] = etape, "gemini"
                return d
        except Exception as e:  # noqa: BLE001
            log.warning("Gemini (plan) a eșuat: %s", e)
    t = (text or "").lower()
    if any(k in t for k in ("baie", "renov", "faian", "gresie")):
        etape = [{"titlu": a, "meserie": b if b in config.MESERII else "universal", "descriere": c, "pret_min": d,
                  "pret_max": e, "durata_min": f, "materiale": []} for a, b, c, d, e, f in _SABLON_BAIE]
        return {"explicatie": "O renovare de baie are patru etape care trebuie făcute în ordine: instalațiile și "
                              "electricul înainte de faianță, finisajele la final. Fiecare etapă primește meșterul ei.",
                "pret_min": sum(e["pret_min"] for e in etape), "pret_max": sum(e["pret_max"] for e in etape),
                "zile": 7, "etape": etape, "sfat": "Nu lăsa faianța să se pună înainte să verifici instalațiile.",
                "sursa": "reguli"}
    d = _rezerva(text)
    return {"explicatie": d["descriere"] + " " + d["sfat_siguranta"], "pret_min": d["pret_min"],
            "pret_max": d["pret_max"], "zile": 1,
            "etape": [{"titlu": d["titlu"], "meserie": d["meserie"], "descriere": d["descriere"],
                       "pret_min": d["pret_min"], "pret_max": d["pret_max"], "durata_min": d["durata_min"],
                       "materiale": d["materiale"]}],
            "sfat": d["sfat_siguranta"], "sursa": "reguli"}
