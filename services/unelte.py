"""Unelte (function calling) pe care Gemini le poate apela ca să calculeze costurile din date, nu din memorie.

Tarifele sunt orientative pentru Timișoara, 2026 (manoperă fără materiale). În producție vin din ofertele reale
acceptate pe platformă, iar tabelul de mai jos rămâne doar rezerva pentru lucrările fără istoric.
"""
from core import config, db

# lucrare: (meserie, unitate, pret_min, pret_max) pe unitate, doar manoperă
TARIFE = {
    "inlocuire baterie / robinet": ("instalator", "buc", 80, 150),
    "desfundare scurgere": ("instalator", "buc", 100, 250),
    "montaj wc / lavoar": ("instalator", "buc", 150, 300),
    "trasee noi apa si scurgere baie": ("instalator", "baie", 900, 1800),
    "montaj cabina dus / cada": ("instalator", "buc", 250, 500),
    "montaj priza / intrerupator": ("electrician", "buc", 40, 80),
    "circuit electric nou": ("electrician", "circuit", 250, 500),
    "inlocuire tablou electric": ("electrician", "buc", 600, 1200),
    "montaj corp iluminat": ("electrician", "buc", 50, 120),
    "revizie centrala termica": ("termice", "buc", 200, 350),
    "montaj calorifer": ("termice", "buc", 200, 400),
    "montaj boiler": ("termice", "buc", 200, 400),
    "montaj usa interior": ("tamplar", "buc", 200, 400),
    "reglaj ferestre termopan": ("tamplar", "buc", 50, 100),
    "zugravit pereti si tavan": ("zugrav", "mp", 12, 22),
    "glet si slefuire": ("zugrav", "mp", 20, 35),
    "deblocare / schimbare yala": ("lacatus", "buc", 120, 300),
    "reparatie masina de spalat": ("electrocasnice", "buc", 150, 350),
    "montaj gresie / faianta": ("universal", "mp", 60, 110),
    "hidroizolatie": ("universal", "mp", 30, 60),
    "demontare faianta veche": ("universal", "mp", 20, 40),
    "montaj mobila": ("universal", "ora", 60, 100),
}

# material: (unitate, economic, mediu, premium) în lei
MATERIALE = {
    "gresie / faianta": ("mp", 45, 90, 180),
    "adeziv si chit": ("mp", 15, 25, 40),
    "hidroizolatie": ("mp", 20, 35, 60),
    "vopsea lavabila": ("mp", 4, 8, 15),
    "baterie / robinet": ("buc", 120, 300, 800),
    "wc complet": ("buc", 450, 900, 2000),
    "lavoar cu mobilier": ("buc", 500, 1100, 2500),
    "cabina dus": ("buc", 900, 1800, 4000),
    "teava ppr si fitinguri": ("baie", 250, 400, 700),
    "priza / intrerupator": ("buc", 15, 35, 90),
    "cablu si doze": ("circuit", 120, 200, 350),
    "siguranta automata": ("buc", 25, 45, 90),
    "boiler 80 l": ("buc", 700, 1100, 1800),
    "calorifer": ("buc", 300, 500, 900),
    "yala": ("buc", 60, 150, 400),
    "racord flexibil": ("buc", 15, 22, 40),
    "garnituri": ("buc", 5, 10, 20),
    "banda teflon": ("buc", 5, 8, 15),
    "sifon": ("buc", 25, 45, 90),
    "silicon sanitar": ("buc", 15, 25, 40),
}


def _cauta(tabel: dict, nume: str):
    n = (nume or "").lower()
    if n in tabel:
        return n
    cuvinte = [c for c in n.replace("/", " ").split() if len(c) > 3]
    scor = {k: sum(c[:5] in k for c in cuvinte) for k in tabel}
    best = max(scor, key=scor.get)
    return best if scor[best] else None


def tarif_manopera(lucrare: str, cantitate: float) -> dict:
    """Costul manoperei pentru o lucrare în Timișoara (lei, fără materiale).

    Args:
        lucrare: tipul lucrării, de ex. "montaj gresie / faianta" sau "zugravit pereti si tavan".
        cantitate: câte unități (mp, bucăți, circuite, ore), conform unității lucrării.
    """
    k = _cauta(TARIFE, lucrare)
    if not k:
        return {"eroare": "lucrare necunoscută", "lucrari_cunoscute": list(TARIFE)}
    meserie, um, a, b = TARIFE[k]
    q = max(float(cantitate or 1), 1)
    return {"lucrare": k, "meserie": meserie, "unitate": um, "cantitate": q,
            "pret_unitar": [a, b], "total_min": round(a * q), "total_max": round(b * q)}


def pret_materiale(material: str, cantitate: float, calitate: str = "mediu") -> dict:
    """Prețul materialelor în magazinele din Timișoara (lei).

    Args:
        material: de ex. "gresie / faianta", "baterie / robinet", "vopsea lavabila".
        cantitate: câte unități (mp sau bucăți).
        calitate: "economic", "mediu" sau "premium".
    """
    k = _cauta(MATERIALE, material)
    if not k:
        return {"eroare": "material necunoscut", "materiale_cunoscute": list(MATERIALE)}
    um, e, m, p = MATERIALE[k]
    pret = {"economic": e, "premium": p}.get((calitate or "").lower(), m)
    q = max(float(cantitate or 1), 1)
    pierderi = 1.1 if um == "mp" else 1.0           # 10% pierderi la tăiere pentru suprafețe
    return {"material": k, "unitate": um, "cantitate": round(q * pierderi, 1), "pret_unitar": pret,
            "total": round(pret * q * pierderi), "nota": "include 10% pierderi" if pierderi > 1 else ""}


def preturi_platforma(meserie: str) -> dict:
    """Prețurile reale acceptate pe SKILLIO pentru o meserie (ofertele plătite de clienți).

    Args:
        meserie: una din meseriile platformei, de ex. "instalator", "electrician", "zugrav".
    """
    rows = db.q("SELECT o.pret FROM oferte o JOIN lucrari l ON l.id = o.lucrare_id "
                "WHERE o.status = 'acceptata' AND l.meserie = ?", (meserie,))
    preturi = sorted(r["pret"] for r in rows if r["pret"])
    if len(preturi) < 3:
        a, b = config.MESERII.get(meserie, {}).get("pret", (100, 300))
        return {"meserie": meserie, "lucrari": len(preturi), "interval_obisnuit": [a, b],
                "nota": "prea puține lucrări pe platformă, folosesc intervalul standard"}
    n = len(preturi)
    return {"meserie": meserie, "lucrari": n, "median": preturi[n // 2],
            "interval_obisnuit": [preturi[n // 4], preturi[(3 * n) // 4]]}


def taxe_skillio(suma: float, urgent: bool = False) -> dict:
    """Cât plătește clientul în total pe SKILLIO pentru o ofertă (cu taxa de protecție și sporul de urgență).

    Args:
        suma: prețul ofertei meșterului, în lei.
        urgent: True dacă lucrarea e urgentă (+15%).
    """
    s = float(suma or 0) * (1.15 if urgent else 1)
    prot = round(s * config.TAXA_PROTECTIE)
    return {"oferta": round(s), "taxa_protectie": prot, "total_client": round(s) + prot,
            "deplasare_daca_refuzi": config.TAXA_DEPLASARE}


_CACHE_LIVE = {}


def pret_live_material(material: str) -> dict:
    """Prețul de AZI al unui material, căutat pe Google la magazinele de bricolaj din România (cu surse).

    Args:
        material: de ex. "gresie portelanata 60x60", "baterie lavoar", "vopsea lavabila alba 15 l".
    """
    k = (material or "").strip().lower()
    if k not in _CACHE_LIVE:
        from services import ai
        try:
            _CACHE_LIVE[k] = ai.cauta_pret_web(material)
        except Exception as e:  # noqa: BLE001
            return {"eroare": f"căutarea live nu a mers ({type(e).__name__}), folosește pret_materiale"}
    return dict(_CACHE_LIVE[k], material=material)


UNELTE = [tarif_manopera, pret_materiale, pret_live_material, preturi_platforma, taxe_skillio]
NUME = {"tarif_manopera": "Tarife manoperă", "pret_materiale": "Prețuri materiale",
        "preturi_platforma": "Prețuri reale SKILLIO",
        "pret_live_material": "Preț live (Google)", "taxe_skillio": "Taxe SKILLIO"}
