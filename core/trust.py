"""Trust Score: un scor de încredere 0-100, calculat doar din activitatea reală din aplicație.

Fiecare factor are un număr maxim de puncte. Când un meșter nou nu are încă
date pentru un factor, primește jumătate din puncte și scrie „fără date încă”,
ca scorul să fie corect și explicabil.

    Evaluarea clienților ............................. 25
    Lucrarea ține (feedback 1 zi / 1 săpt. / 1 lună) .. 20
    Programări respectate ............................ 15
    Punctualitate (sosire confirmată de rețea) ....... 10
    Lucrări finalizate ............................... 10
    Identitate verificată (Nokia: număr + SIM) ....... 10
    Fără reclamații confirmate ....................... 10
"""
from . import db

NIVELURI = [(90, "Excelent"), (75, "Foarte bun"), (60, "Bun"), (0, "În creștere")]


def nivel(scor: int) -> str:
    for prag, eticheta in NIVELURI:
        if scor >= prag:
            return eticheta
    return "În creștere"


def _incarca_toti() -> dict:
    """Datele pentru scorul TUTUROR meșterilor, în 6 cereri (nu 6 pentru fiecare meșter)."""
    def grup(rows, cheie="mester_id"):
        g = {}
        for r in rows:
            g.setdefault(r[cheie], []).append(r)
        return g
    return {
        "m": {r["id"]: r for r in db.q("SELECT id, numar_verificat, sim_ok FROM utilizatori WHERE rol = 'mester'")},
        "note": grup(db.q("SELECT mester_id, nota FROM feedback WHERE etapa = 'final' AND nota IS NOT NULL")),
        "durab": grup(db.q("SELECT mester_id, etapa, ok FROM feedback WHERE etapa IN ('zi1','sapt1','luna1') "
                           "AND ok IS NOT NULL")),
        "prog": grup(db.q("SELECT mester_id, status, sosit_la, punctual, anulat_motiv FROM lucrari "
                          "WHERE programat_la IS NOT NULL AND mester_id IS NOT NULL")),
        "fin": {r["mester_id"]: r["n"] for r in db.q("SELECT mester_id, COUNT(*) AS n FROM lucrari "
                                                      "WHERE status = 'finalizata' GROUP BY mester_id")},
        "recl": {r["vizat_id"]: r["n"] for r in db.q("SELECT vizat_id, COUNT(*) AS n FROM rapoarte "
                                                      "WHERE status = 'confirmat' GROUP BY vizat_id")},
    }


def calculeaza(mester_id: int) -> dict:
    d = db._citeste(("trust_toti",), _incarca_toti)   # ținut minte până la prima modificare din aplicație
    m = d["m"].get(mester_id) or {}

    note = d["note"].get(mester_id, [])
    durab = d["durab"].get(mester_id, [])
    programate = d["prog"].get(mester_id, [])
    finalizate = d["fin"].get(mester_id, 0) or 0
    reclamatii = d["recl"].get(mester_id, 0) or 0

    factori = []

    # 1. Evaluarea clienților (media pe 5 criterii, 1-5 stele)
    if note:
        medie = sum(n["nota"] for n in note) / len(note)
        factori.append(_f("rating", "Evaluarea clienților", 25, (medie - 1) / 4,
                          f"{medie:.1f}/5 din {len(note)} recenzii verificate".replace(".", ",", 1)))
    else:
        factori.append(_f("rating", "Evaluarea clienților", 25, None, "fără recenzii încă"))

    # 2. Lucrarea ține: la 1 lună contează dublu față de 1 zi
    if durab:
        greutate = {"zi1": 1, "sapt1": 1.5, "luna1": 2}
        tot = sum(greutate[d["etapa"]] for d in durab)
        bune = sum(greutate[d["etapa"]] for d in durab if d["ok"])
        procent = bune / tot
        factori.append(_f("durabilitate", "Lucrarea ține (1 zi / 1 săpt. / 1 lună)", 20, procent,
                          f"{procent:.0%} „totul e în regulă” din {len(durab)} răspunsuri"))
    else:
        factori.append(_f("durabilitate", "Lucrarea ține (1 zi / 1 săpt. / 1 lună)", 20, None, "fără răspunsuri încă"))

    # 3. Programări respectate: a ajuns la lucrare sau a anulat / nu a venit
    incheiate = [p for p in programate if p["sosit_la"] or p["status"] == "anulata"]
    if incheiate:
        respectate = sum(1 for p in incheiate if p["sosit_la"])
        procent = respectate / len(incheiate)
        factori.append(_f("programari", "Programări respectate", 15, procent,
                          f"{respectate} din {len(incheiate)} ({procent:.0%})"))
    else:
        factori.append(_f("programari", "Programări respectate", 15, None, "fără programări încă"))

    # 4. Punctualitate: sosirea e confirmată de rețeaua Nokia
    sosiri = [p for p in programate if p["sosit_la"] and p["punctual"] is not None]
    if sosiri:
        la_timp = sum(1 for p in sosiri if p["punctual"])
        procent = la_timp / len(sosiri)
        factori.append(_f("punctualitate", "Punctualitate (sosire confirmată de rețea)", 10, procent,
                          f"{la_timp} din {len(sosiri)} sosiri la timp"))
    else:
        factori.append(_f("punctualitate", "Punctualitate (sosire confirmată de rețea)", 10, None, "fără sosiri încă"))

    # 5. Lucrări finalizate: plafon la 30
    factori.append(_f("lucrari", "Lucrări finalizate", 10, min(finalizate / 30, 1), f"{finalizate} lucrări confirmate"))

    # 6. Identitate verificată prin rețea
    ver = (0.5 if m.get("numar_verificat") else 0) + (0.5 if m.get("sim_ok") else 0)
    detalii = []
    detalii.append("număr verificat" if m.get("numar_verificat") else "număr neverificat")
    detalii.append("SIM stabil" if m.get("sim_ok") else "SIM schimbat recent")
    factori.append(_f("verificare", "Identitate verificată (Nokia)", 10, ver, ", ".join(detalii)))

    # 7. Reclamații confirmate: -5 puncte fiecare
    factori.append(_f("reclamatii", "Fără reclamații confirmate", 10, max(0, 1 - reclamatii * 0.5),
                      "nicio reclamație confirmată" if reclamatii == 0 else f"{reclamatii} reclamații confirmate"))

    scor = int(round(sum(f["puncte"] for f in factori)))
    return {"scor": scor, "nivel": nivel(scor), "factori": factori, "finalizate": finalizate,
            "nr_recenzii": len(note), "medie": (sum(n["nota"] for n in note) / len(note)) if note else None}


def _f(cheie, eticheta, maxim, procent, detaliu):
    fara_date = procent is None
    p = 0.5 if fara_date else max(0.0, min(1.0, procent))
    return {"cheie": cheie, "eticheta": eticheta, "max": maxim, "puncte": round(p * maxim, 1),
            "detaliu": detaliu, "fara_date": fara_date}


def scor(mester_id: int) -> int:
    return calculeaza(mester_id)["scor"]
