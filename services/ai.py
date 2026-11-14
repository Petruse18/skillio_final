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


def diagnosticheaza(text: str, poza: bytes | None = None, mime: str = "image/jpeg") -> dict:
    if activ():
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=config.GEMINI_API_KEY)
            parti = [PROMPT.format(meserii=list(config.MESERII), text=text or "(fără text, doar poză)")]
            if poza:
                parti.append(types.Part.from_bytes(data=poza, mime_type=mime))
            r = client.models.generate_content(
                model=config.GEMINI_MODEL, contents=parti,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2))
            d = json.loads(r.text)
            if isinstance(d, list):
                d = d[0]
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


def _gemini_json(parti):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    r = client.models.generate_content(
        model=config.GEMINI_MODEL, contents=parti,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2))
    d = json.loads(r.text)
    return d[0] if isinstance(d, list) else d


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
Răspunde DOAR cu JSON valid, în română:
{{"explicatie": "2-3 propoziții: ce se întâmplă și ce trebuie făcut",
  "pret_min": număr, "pret_max": număr, "zile": număr,
  "etape": [{{"titlu": "max 5 cuvinte", "meserie": una din meseriile permise, "descriere": "1 propoziție",
             "pret_min": număr, "pret_max": număr, "durata_min": număr, "materiale": ["..."]}}],
  "sfat": "o propoziție: la ce să fie atent clientul"}}
Prețuri Timișoara 2026, manoperă + materiale uzuale. O problemă mică are o singură etapă.
Cererea clientului: {text}"""

_SABLON_BAIE = [("Instalații sanitare noi", "instalator", "Trasee noi de apă și scurgere, înainte de faianță.", 900, 1800, 480),
                ("Circuite și prize baie", "electrician", "Circuit separat, prize protejate și corpuri de iluminat.", 500, 1100, 300),
                ("Montaj gresie și faianță", "universal", "Hidroizolație, apoi gresie și faianță.", 2200, 4200, 1440),
                ("Finisaje și zugrăveli", "zugrav", "Tavan și pereți, vopsea rezistentă la umezeală.", 400, 900, 300)]


def planifica(text: str, poza: bytes | None = None, mime: str = "image/jpeg") -> dict:
    if activ():
        try:
            from google.genai import types
            parti = [PROMPT_PLAN.format(meserii=list(config.MESERII), text=text or "(doar poză)")]
            if poza:
                parti.append(types.Part.from_bytes(data=poza, mime_type=mime))
            d = _gemini_json(parti)
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
