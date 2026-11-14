"""Regulile aplicației: conturi, solicitări, oferte, programări, plăți, recenzii, rapoarte.

Ecranele (views/) doar afișează și apelează funcțiile de aici. Dacă vreți să
schimbați o regulă (ex. comisionul), o schimbați într-un singur loc.

Viața unei lucrări:
    deschisa    clientul a trimis solicitarea, meșterii trimit oferte
    acceptata   clientul a ales o ofertă, se stabilește ora
    de_plata    ora e stabilită de amândoi, clientul plătește
    programata  plătit, banii sunt blocați până la final
    sosit       meșterul e la adresă și trebuie să reconfirme prețul (poză + motiv)
    reconfirmare  clientul acceptă prețul reconfirmat sau refuză (plătește doar deplasarea)
    in_lucru    meșterul lucrează
    gata        meșterul a terminat, așteaptă confirmarea clientului
    confirmata  ambii au confirmat; banii mai stau blocați 24 de ore, oricine poate deschide dispută
    finalizata  banii au ajuns la meșter
    disputa     o parte a deschis o dispută, decide un mediator uman
    anulata
"""
import json
import re
import secrets
from datetime import datetime, timedelta

from services import geo, mesaje_externe, solana, stocare

from . import config, db, timp, trust

STATUS = {
    "deschisa": ("Așteaptă oferte", "neutru"),
    "acceptata": ("Stabiliți ora", "neutru"),
    "de_plata": ("De plătit", "escrow"),
    "programata": ("Programată", "ok"),
    "sosit": ("Meșterul e la tine", "ok"),
    "reconfirmare": ("Confirmă prețul", "escrow"),
    "in_lucru": ("În lucru", "ok"),
    "gata": ("Confirmă lucrarea", "escrow"),
    "confirmata": ("Plata pleacă în 24 h", "escrow"),
    "finalizata": ("Finalizată", "ok"),
    "disputa": ("La mediator", "danger"),
    "anulata": ("Anulată", "neutru"),
}
ACTIVE = ("deschisa", "acceptata", "de_plata", "programata", "sosit", "reconfirmare", "in_lucru", "gata",
          "confirmata", "disputa")
IN_CURS = ("sosit", "reconfirmare", "in_lucru", "gata", "confirmata")   # aici se poate deschide o dispută


class Eroare(Exception):
    """O acțiune care nu e permisă, cu un mesaj pentru utilizator."""


# ---------------------------------------------------------------------------
# Conturi și sesiuni
# ---------------------------------------------------------------------------
def normalizeaza_telefon(t: str) -> str:
    cifre = "".join(ch for ch in t if ch.isdigit() or ch == "+")
    if cifre.startswith("00"):
        cifre = "+" + cifre[2:]
    if cifre.startswith("07") and len(cifre) == 10:
        cifre = "+4" + cifre
    return cifre


def user(uid):
    return db.q1("SELECT * FROM utilizatori WHERE id = ?", (uid,)) if uid else None


def user_dupa_telefon(tel):
    return db.q1("SELECT * FROM utilizatori WHERE telefon = ?", (tel,))


def creeaza_cont(telefon, nume, rol, cartier, adresa="", meserii=(), email=None, auth_sub=None):
    telefon = normalizeaza_telefon(telefon)
    if len(telefon) < 10:
        raise Eroare("Numărul de telefon pare incomplet. Scrie-l cu prefix, de ex. 0722 123 456.")
    if user_dupa_telefon(telefon):
        raise Eroare("Există deja un cont cu acest număr. Folosește „Intră în cont”.")
    if not nume.strip():
        raise Eroare("Scrie-ți numele.")
    if rol == "mester" and not meserii:
        raise Eroare("Alege cel puțin o meserie.")
    verificat, schimbat = True, False
    lat, lon = config.CARTIERE.get(cartier, config.CENTRU_ORAS)
    uid = db.ex(
        "INSERT INTO utilizatori(telefon, nume, rol, creat_la, numar_verificat, sim_ok, sim_verificat_la, adresa, "
        "cartier, lat, lon, meserii, email, auth_sub) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (telefon, nume.strip(), rol, timp.iso(timp.acum()), int(verificat), int(not schimbat),
         timp.iso(timp.acum()), adresa.strip(), cartier, lat, lon, ",".join(meserii), email, auth_sub))
    return uid


def user_dupa_auth(sub, email=None):
    """Găsește contul legat de un login Auth0. Dacă emailul există deja, leagă contul de Auth0."""
    u = db.q1("SELECT * FROM utilizatori WHERE auth_sub = ?", (sub,)) if sub else None
    if not u and email:
        u = db.q1("SELECT * FROM utilizatori WHERE lower(email) = ? AND auth_sub IS NULL", (email.lower(),))
        if u:
            db.ex("UPDATE utilizatori SET auth_sub = ? WHERE id = ?", (sub, u["id"]))
    if u and email and (email.lower() in config.ADMIN_EMAILS) and u["rol"] != "admin":
        db.ex("UPDATE utilizatori SET rol = 'admin' WHERE id = ?", (u["id"],))
        u = user(u["id"])
    return u


def intra(telefon):
    """Intrare demo cu numărul de telefon (în producție: Auth0, cod prin SMS sau email)."""
    telefon = normalizeaza_telefon(telefon)
    u = user_dupa_telefon(telefon)
    if not u:
        raise Eroare("Nu găsim un cont cu acest număr. Creează unul în câteva secunde.")
    return u["id"], "demo", False


def sesiune_noua(uid) -> str:
    """Sesiune pentru intrarea demo (telefon). Expiră după SESIUNE_ZILE zile (ora reală, nu ceasul demo)."""
    token = secrets.token_urlsafe(24)
    acum = datetime.now()
    db.ex("INSERT INTO sesiuni(token, user_id, creat_la, expira_la) VALUES(?,?,?,?)",
          (token, uid, timp.iso(acum), timp.iso(acum + timedelta(days=config.SESIUNE_ZILE))))
    return token


def user_din_sesiune(token):
    if not token:
        return None
    r = db.q1("SELECT user_id, expira_la FROM sesiuni WHERE token = ?", (token,))
    if not r or (r["expira_la"] and r["expira_la"] < timp.iso(datetime.now())):
        return None
    return user(r["user_id"])


def sterge_sesiune(token):
    db.ex("DELETE FROM sesiuni WHERE token = ?", (token,))


def actualizeaza_profil(uid, **campuri):
    permise = {"sol_wallet", "nume", "adresa", "cartier", "despre", "meserii", "experienta_ani", "tarif_ora", "raza_km",
               "disponibil", "poza", "ghid_vazut", "act_status", "act_poza", "departe_demo", "lat", "lon"}
    campuri = {k: v for k, v in campuri.items() if k in permise}
    if "cartier" in campuri and "lat" not in campuri:
        campuri["lat"], campuri["lon"] = config.CARTIERE.get(campuri["cartier"], config.CENTRU_ORAS)
    if not campuri:
        return
    sets = ", ".join(f"{k} = ?" for k in campuri)
    db.ex(f"UPDATE utilizatori SET {sets} WHERE id = ?", (*campuri.values(), uid))


def adauga_portofoliu(mester_id, poza, descriere):
    db.ex("INSERT INTO portofoliu(mester_id, poza, descriere, creat_la) VALUES(?,?,?,?)",
          (mester_id, poza, descriere, timp.iso(timp.acum())))


def portofoliu(mester_id):
    return db.q("SELECT * FROM portofoliu WHERE mester_id = ? ORDER BY id DESC", (mester_id,))


def salveaza_poza(fisier, prefix="img") -> str | None:
    """Salvează o poză încărcată (în cloud sau local, vezi services/stocare.py) și întoarce referința."""
    if fisier is None:
        return None
    ext = (fisier.name.rsplit(".", 1)[-1] if "." in fisier.name else "jpg").lower()[:5]
    nume = f"{prefix}_{secrets.token_hex(6)}.{ext}"
    return stocare.salveaza(fisier.getvalue(), nume)


# ---------------------------------------------------------------------------
# Meșteri: căutare și potrivire
# ---------------------------------------------------------------------------
def meserii_lista(u):
    return [m for m in (u.get("meserii") or "").split(",") if m]


def mesteri(meserie=None, lat=None, lon=None, max_km=None, doar_disponibili=False, scor_minim=0,
            pret_max=None, exp_min=0, rating_min=0, text="", sortare="potrivire"):
    rows = db.q("SELECT * FROM utilizatori WHERE rol = 'mester'")
    rez = []
    text = text.strip().lower()
    for m in rows:
        ms = meserii_lista(m)
        if meserie and meserie not in ms:
            continue
        if doar_disponibili and not m["disponibil"]:
            continue
        if pret_max and m["tarif_ora"] and m["tarif_ora"] > pret_max:
            continue
        if exp_min and (m["experienta_ani"] or 0) < exp_min:
            continue
        if text:
            fan = " ".join([m["nume"], m["despre"] or "", m["cartier"] or ""] +
                           [config.MESERII[x]["nume"] for x in ms if x in config.MESERII]).lower()
            if text not in fan:
                continue
        t = trust.calculeaza(m["id"])
        if t["scor"] < scor_minim:
            continue
        if rating_min and (t["medie"] or 0) < rating_min:
            continue
        d = geo.distanta_km(lat, lon, m["lat"], m["lon"]) if lat is not None else None
        if max_km and d is not None and d > max_km:
            continue
        m = dict(m, trust=t, dist=d, meserii_l=ms)
        rez.append(m)
    chei = {
        "potrivire": lambda m: -(m["trust"]["scor"] - (m["dist"] or 0) * 2 + (8 if m["disponibil"] else 0)),
        "distanta": lambda m: m["dist"] if m["dist"] is not None else 99,
        "trust": lambda m: -m["trust"]["scor"],
        "rating": lambda m: -(m["trust"]["medie"] or 0),
        "pret": lambda m: m["tarif_ora"] or 999,
        "experienta": lambda m: -(m["experienta_ani"] or 0),
    }
    rez.sort(key=chei.get(sortare, chei["potrivire"]))
    return rez


# ---------------------------------------------------------------------------
# Solicitări (lucrări)
# ---------------------------------------------------------------------------
def lucrare(lid):
    return db.q1("SELECT * FROM lucrari WHERE id = ?", (lid,))


def diagnostic(l):
    try:
        return json.loads(l.get("diagnostic") or "{}")
    except (TypeError, ValueError):
        return {}


def creeaza_lucrare(client_id, titlu, descriere, adresa, cartier, meserie, urgent, buget, poza, diag,
                    mester_tinta=None):
    if not descriere.strip():
        raise Eroare("Descrie pe scurt problema.")
    if not adresa.strip():
        raise Eroare("Scrie adresa unde trebuie să vină meșterul.")
    lat, lon, _ = geo.coordonate(adresa, cartier)
    lid = db.ex(
        "INSERT INTO lucrari(client_id, titlu, descriere, adresa, cartier, lat, lon, poza, urgent, buget, meserie, "
        "diagnostic, status, creat_la) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (client_id, titlu.strip() or config.MESERII[meserie]["nume"], descriere.strip(), adresa.strip(), cartier,
         lat, lon, poza, int(bool(urgent)), buget or None, meserie, json.dumps(diag, ensure_ascii=False),
         "deschisa", timp.iso(timp.acum())))
    invitati = []
    if mester_tinta:
        invitati.append(mester_tinta)
    for m in mesteri(meserie=meserie, lat=lat, lon=lon, doar_disponibili=True):
        if len(invitati) >= config.MAX_INVITATI:
            break
        if m["id"] in invitati or m["id"] == client_id:
            continue
        if m["dist"] is not None and m["dist"] > (m["raza_km"] or 8) + 1:
            continue
        invitati.append(m["id"])
    for loc, mid in enumerate(invitati):
        db.ex("INSERT OR IGNORE INTO invitatii(lucrare_id, mester_id, loc) VALUES(?,?,?)", (lid, mid, loc))
        notifica(mid, ("URGENT: " if urgent else "") + f"Solicitare nouă lângă tine: {titlu or descriere[:40]}", lid, extern=True)
    mesaj_sistem(lid, "Solicitarea a fost trimisă la " + (f"{len(invitati)} meșteri potriviți." if invitati
                                                          else "meșterii din zonă."))
    return lid, len(invitati)


def lucrari_client(client_id):
    return db.q("SELECT * FROM lucrari WHERE client_id = ? ORDER BY "
                "CASE WHEN status IN ('finalizata','anulata') THEN 1 ELSE 0 END, id DESC", (client_id,))


def lucrari_mester(mester_id):
    return db.q("SELECT * FROM lucrari WHERE mester_id = ? ORDER BY "
                "CASE WHEN status IN ('finalizata','anulata') THEN 1 ELSE 0 END, programat_la", (mester_id,))


def solicitari_pentru_mester(mester_id):
    """Solicitări deschise care se potrivesc meșterului. Urgentele sunt primele."""
    m = user(mester_id)
    ms = meserii_lista(m)
    rows = db.q("SELECT l.*, i.status AS inv_status FROM lucrari l "
                "LEFT JOIN invitatii i ON i.lucrare_id = l.id AND i.mester_id = ? "
                "WHERE l.status = 'deschisa' AND l.client_id != ?", (mester_id, mester_id))
    rez = []
    for l in rows:
        if l["inv_status"] == "refuzata":
            continue
        d = geo.distanta_km(m["lat"], m["lon"], l["lat"], l["lon"])
        invitat = l["inv_status"] is not None
        if not invitat and (l["meserie"] not in ms or d > (m["raza_km"] or 8) + 1):
            continue
        of = db.q1("SELECT * FROM oferte WHERE lucrare_id = ? AND mester_id = ? AND status != 'retrasa'",
                   (l["id"], mester_id))
        nr_oferte = db.val("SELECT COUNT(*) FROM oferte WHERE lucrare_id = ? AND status = 'trimisa'", (l["id"],), 0)
        rez.append(dict(l, dist=d, oferta_mea=of, nr_oferte=nr_oferte, invitat=invitat))
    rez.sort(key=lambda l: (not l["urgent"], l["oferta_mea"] is not None, l["dist"]))
    return rez


def refuza_solicitare(lid, mester_id):
    db.ex("INSERT INTO invitatii(lucrare_id, mester_id, loc, status) VALUES(?,?,99,'refuzata') "
          "ON CONFLICT(lucrare_id, mester_id) DO UPDATE SET status = 'refuzata'", (lid, mester_id))


def anuleaza_lucrare(lid, de_cine, motiv="Anulată de client"):
    l = lucrare(lid)
    if l["status"] in ("finalizata", "anulata", "disputa") + IN_CURS:
        raise Eroare("Lucrarea nu mai poate fi anulată în acest moment.")
    platite = db.q("SELECT * FROM plati WHERE lucrare_id = ? AND status = 'blocat'", (lid,))
    for p in platite:
        db.ex("UPDATE plati SET status = 'returnat', rezolvat_la = ? WHERE id = ?", (timp.iso(timp.acum()), p["id"]))
    _returneaza_onchain(lid, platite)
    db.ex("UPDATE lucrari SET status = 'anulata', anulat_motiv = ? WHERE id = ?", (motiv, lid))
    db.ex("UPDATE oferte SET status = 'respinsa' WHERE lucrare_id = ? AND status = 'trimisa'", (lid,))
    total = sum(p["suma"] for p in platite)
    mesaj_sistem(lid, f"Lucrarea a fost anulată ({motiv.lower()})." +
                 (f" {timp.lei(total)} s-au întors la client." if total else ""))
    tinta = l["mester_id"] if de_cine == l["client_id"] else l["client_id"]
    if tinta:
        notifica(tinta, f"Lucrarea „{l['titlu']}” a fost anulată.", lid)


# ---------------------------------------------------------------------------
# Oferte și programare
# ---------------------------------------------------------------------------
def taxa_protectie(suma):
    return round(suma * config.TAXA_PROTECTIE, 2)


def total_cu_urgenta(pret, urgent):
    return round(pret * (1 + config.SPOR_URGENT)) if urgent else round(pret)


def trimite_oferta(lid, mester_id, pret, propus_la: datetime, mesaj=""):
    l = lucrare(lid)
    if l["status"] != "deschisa":
        raise Eroare("Clientul a ales deja o ofertă pentru această lucrare.")
    if pret <= 0:
        raise Eroare("Scrie un preț mai mare de 0.")
    if not slot_liber(mester_id, propus_la):
        raise Eroare("Ai deja ceva programat la ora aceea. Alege altă oră.")
    vechi = db.q1("SELECT id FROM oferte WHERE lucrare_id = ? AND mester_id = ? AND status = 'trimisa'",
                  (lid, mester_id))
    if vechi:
        db.ex("UPDATE oferte SET status = 'retrasa' WHERE id = ?", (vechi["id"],))
    oid = db.ex("INSERT INTO oferte(lucrare_id, mester_id, pret, total, propus_la, mesaj, status, creat_la) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (lid, mester_id, pret, total_cu_urgenta(pret, l["urgent"]), timp.iso(propus_la), mesaj.strip(),
                 "trimisa", timp.iso(timp.acum())))
    m = user(mester_id)
    notifica(l["client_id"], f"Ofertă nouă de la {m['nume']}: {timp.lei(total_cu_urgenta(pret, l['urgent']))}", lid, extern=True)
    return oid


def oferte(lid):
    rows = db.q("SELECT * FROM oferte WHERE lucrare_id = ? AND status IN ('trimisa','acceptata') ORDER BY total", (lid,))
    l = lucrare(lid)
    for o in rows:
        o["mester"] = user(o["mester_id"])
        o["trust"] = trust.calculeaza(o["mester_id"])
        o["dist"] = geo.distanta_km(l["lat"], l["lon"], o["mester"]["lat"], o["mester"]["lon"])
    return rows


def accepta_oferta(oid, client_id):
    o = db.q1("SELECT * FROM oferte WHERE id = ?", (oid,))
    l = lucrare(o["lucrare_id"])
    if l["client_id"] != client_id or l["status"] != "deschisa" or o["status"] != "trimisa":
        raise Eroare("Oferta nu mai este disponibilă.")
    db.ex("UPDATE oferte SET status = 'acceptata' WHERE id = ?", (oid,))
    db.ex("UPDATE oferte SET status = 'respinsa' WHERE lucrare_id = ? AND id != ? AND status = 'trimisa'",
          (l["id"], oid))
    db.ex("UPDATE lucrari SET status = 'acceptata', mester_id = ?, oferta_id = ?, prog_propus = ?, "
          "prog_propus_de = 'mester' WHERE id = ?", (o["mester_id"], oid, o["propus_la"], l["id"]))
    for alt in db.q("SELECT mester_id FROM oferte WHERE lucrare_id = ? AND status = 'respinsa'", (l["id"],)):
        notifica(alt["mester_id"], f"Clientul a ales altă ofertă pentru „{l['titlu']}”.", l["id"])
    mesaj_sistem(l["id"], f"{user(client_id)['nume']} a acceptat oferta de {timp.lei(o['total'])}. "
                          f"Mai rămâne de confirmat ora.")
    notifica(o["mester_id"], f"Oferta ta pentru „{l['titlu']}” a fost acceptată!", l["id"], extern=True)


def propune_ora(lid, uid, cand: datetime):
    l = lucrare(lid)
    if l["status"] not in ("acceptata",):
        raise Eroare("Ora nu mai poate fi schimbată.")
    if not slot_liber(l["mester_id"], cand, ignora_lucrare=lid):
        raise Eroare("Meșterul nu e liber la ora aceea.")
    rol = "client" if uid == l["client_id"] else "mester"
    db.ex("UPDATE lucrari SET prog_propus = ?, prog_propus_de = ? WHERE id = ?", (timp.iso(cand), rol, lid))
    mesaj_sistem(lid, f"{user(uid)['nume']} propune {timp.data_ora(cand)}.")
    notifica(l["mester_id"] if rol == "client" else l["client_id"], f"Oră nouă propusă: {timp.data_ora(cand)}", lid, extern=True)


def confirma_ora(lid, uid):
    l = lucrare(lid)
    rol = "client" if uid == l["client_id"] else "mester"
    if l["status"] != "acceptata" or not l["prog_propus"] or l["prog_propus_de"] == rol:
        raise Eroare("Nu există o oră de confirmat.")
    if not slot_liber(l["mester_id"], timp.din_iso(l["prog_propus"]), ignora_lucrare=lid):
        raise Eroare("Între timp, meșterul și-a ocupat ora aceea. Propune alta.")
    db.ex("UPDATE lucrari SET status = 'de_plata', programat_la = prog_propus, prog_propus = NULL WHERE id = ?", (lid,))
    mesaj_sistem(lid, f"Ora e stabilită: {timp.data_ora(l['prog_propus'])}. Clientul poate plăti.")
    notifica(l["client_id"] if rol == "mester" else l["mester_id"],
             f"Programare confirmată: {timp.data_ora(l['prog_propus'])}", lid, extern=True)


def plateste(lid, client_id):
    """Plată simulată: suma ofertei rămâne blocată în platformă până la confirmarea clientului."""
    l = lucrare(lid)
    if l["client_id"] != client_id or l["status"] != "de_plata":
        raise Eroare("Plata nu e posibilă acum.")
    o = db.q1("SELECT * FROM oferte WHERE id = ?", (l["oferta_id"],))
    pid = db.ex("INSERT INTO plati(lucrare_id, client_id, mester_id, suma, comision, tip, status, creat_la) "
                "VALUES(?,?,?,?,?,?,?,?)", (lid, client_id, l["mester_id"], o["total"], 0, "oferta", "blocat",
                                            timp.iso(timp.acum())))
    prot = taxa_protectie(o["total"])
    db.ex("INSERT INTO plati(lucrare_id, client_id, mester_id, suma, comision, tip, status, creat_la) "
          "VALUES(?,?,?,?,?,?,?,?)", (lid, client_id, l["mester_id"], prot, 0, "protectie", "blocat",
                                      timp.iso(timp.acum())))
    _blocheaza_onchain(pid, lid, o["total"])
    db.ex("UPDATE lucrari SET status = 'programata' WHERE id = ?", (lid,))
    mesaj_sistem(lid, f"{timp.lei(o['total'] + prot)} plătiți și blocați în SKILLIO până la finalul lucrării "
                      f"(include taxa de protecție de {config.PCT_PROTECTIE}).")
    notifica(l["mester_id"], f"Clientul a plătit {timp.lei(o['total'])} (blocați până la final). "
                             f"Te așteaptă {timp.data_ora(l['programat_la'])}.", lid, extern=True)


# --- plata pe blockchain (Solana devnet), opțională --------------------------------
def _blocheaza_onchain(pid, lid, suma):
    if not solana.activ():
        return

    def salveaza(rez):
        sig, lam = rez
        db.ex("UPDATE plati SET tx_lock = ?, lamports = ? WHERE id = ?", (sig, lam, pid))
        mesaj_sistem(lid, f"Plata de {timp.lei(suma)} e blocată și pe blockchain (Solana devnet).")
    solana.in_fundal("lock", lambda: solana.blocheaza(lid, suma), salveaza)


def _elibereaza_onchain(lid, plati):
    l = lucrare(lid)
    amprenta = solana.amprenta_lucrare(l, plati)
    db.ex("UPDATE lucrari SET pasaport = ? WHERE id = ?", (amprenta, lid))
    lam = sum(p["lamports"] or 0 for p in plati if p.get("tx_lock"))
    if not solana.activ() or not lam:
        return
    m = user(l["mester_id"])
    catre = solana.portofel_mester(m["id"], m.get("sol_wallet"))

    def salveaza(sig):
        for p in plati:
            if p.get("tx_lock"):
                db.ex("UPDATE plati SET tx_final = ? WHERE id = ?", (sig, p["id"]))
        db.ex("UPDATE lucrari SET tx_pasaport = ? WHERE id = ?", (sig, lid))
        mesaj_sistem(lid, "Banii au fost eliberați on-chain, iar pașaportul lucrării a fost scris pe Solana.")
    solana.in_fundal("release", lambda: solana.elibereaza(lid, lam, catre, amprenta), salveaza)


def _returneaza_onchain(lid, plati):
    cu_tx = [p for p in plati if p.get("tx_lock") and p.get("lamports")]
    if not solana.activ() or not cu_tx:
        return

    def salveaza(sig):
        for p in cu_tx:
            db.ex("UPDATE plati SET tx_final = ? WHERE id = ?", (sig, p["id"]))
    solana.in_fundal("refund", lambda: solana.returneaza(lid, sum(p["lamports"] for p in cu_tx)), salveaza)


def bani_lucrare(lid):
    rows = db.q("SELECT * FROM plati WHERE lucrare_id = ?", (lid,))
    return {
        "blocat": sum(p["suma"] for p in rows if p["status"] == "blocat"),
        "eliberat": sum(p["suma"] for p in rows if p["status"] == "eliberat"),
        "returnat": sum(p["suma"] for p in rows if p["status"] == "returnat"),
        "comision": sum(p["comision"] for p in rows if p["status"] == "eliberat"),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Ziua lucrării
# ---------------------------------------------------------------------------
def am_ajuns(lid, mester_id):
    l = lucrare(lid)
    if l["mester_id"] != mester_id or l["status"] != "programata":
        raise Eroare("Lucrarea nu e programată.")
    m = user(mester_id)
    acum = timp.acum()
    prog = timp.din_iso(l["programat_la"])
    punctual = int(acum <= prog + timedelta(minutes=config.TOLERANTA_PUNCTUAL_MIN))
    db.ex("UPDATE lucrari SET status = 'sosit', sosit_la = ?, sosire_mod = 'aplicatie', punctual = ? WHERE id = ?",
          (timp.iso(acum), punctual, lid))
    mesaj_sistem(lid, f"{m['nume']} a ajuns la {acum:%H:%M}" + ("." if punctual else " (cu întârziere).") +
                 " Urmează reconfirmarea prețului, cu poză.")
    notifica(l["client_id"], f"{m['nume']} a ajuns. Îți trimite acum prețul reconfirmat.", lid)
    return "aplicatie", punctual


def pret_curent(lid):
    """Cât plătește clientul pentru lucrare (ofertă + extra acceptate), fără taxa de protecție."""
    return sum(p["suma"] for p in db.q("SELECT suma FROM plati WHERE lucrare_id = ? AND status = 'blocat' "
                                       "AND tip IN ('oferta','extra')", (lid,)))


def reconfirma_pret(lid, mester_id, pret, motiv, poza=None, poza_bytes=None, mime="image/jpeg"):
    """La fața locului, meșterul reconfirmă prețul cu o poză și un motiv. AI-ul doar dă o părere."""
    l = lucrare(lid)
    if l["mester_id"] != mester_id or l["status"] != "sosit":
        raise Eroare("Prețul se reconfirmă după ce ai ajuns la adresă.")
    if pret <= 0 or not (motiv or "").strip():
        raise Eroare("Scrie prețul și motivul, ca să înțeleagă clientul.")
    if not poza:
        raise Eroare("Adaugă o poză cu problema văzută de aproape.")
    from services import ai
    vechi = pret_curent(lid)
    parere = ai.verifica_pret(l, vechi, pret, motiv, poza_bytes, mime)
    rec = {"pret": float(pret), "vechi": vechi, "motiv": motiv.strip(), "poza": poza, "ai": parere}
    db.ex("UPDATE lucrari SET status = 'reconfirmare', reconf = ? WHERE id = ?", (json.dumps(rec, ensure_ascii=False), lid))
    dif = pret - vechi
    mesaj_sistem(lid, f"Preț reconfirmat la fața locului: {timp.lei(pret)}" +
                 (f" ({'+' if dif > 0 else '−'}{timp.lei(abs(dif))} față de ofertă)" if dif else " (la fel ca oferta)") +
                 f". Motiv: {motiv.strip()}")
    notifica(l["client_id"], f"Meșterul a reconfirmat prețul: {timp.lei(pret)}. Acceptă sau refuză.", lid)


def reconfirmare(l):
    try:
        return json.loads(l.get("reconf") or "{}")
    except (TypeError, ValueError):
        return {}


def raspunde_reconfirmare(lid, client_id, accept: bool):
    l = lucrare(lid)
    if l["client_id"] != client_id or l["status"] != "reconfirmare":
        raise Eroare("Nu există un preț de confirmat.")
    r = reconfirmare(l)
    acum = timp.iso(timp.acum())
    oferta = db.q1("SELECT * FROM plati WHERE lucrare_id = ? AND tip = 'oferta' AND status = 'blocat'", (lid,))
    if accept:
        dif = round(r["pret"] - r["vechi"], 2)
        if dif > 0:
            pid = db.ex("INSERT INTO plati(lucrare_id, client_id, mester_id, suma, comision, tip, status, creat_la) "
                        "VALUES(?,?,?,?,?,?,?,?)", (lid, client_id, l["mester_id"], dif, 0, "extra", "blocat", acum))
            db.ex("INSERT INTO plati(lucrare_id, client_id, mester_id, suma, comision, tip, status, creat_la) "
                  "VALUES(?,?,?,?,?,?,?,?)", (lid, client_id, l["mester_id"], taxa_protectie(dif), 0, "protectie",
                                              "blocat", acum))
            _blocheaza_onchain(pid, lid, dif)
        elif dif < 0 and oferta:
            db.ex("UPDATE plati SET suma = suma - ? WHERE id = ?", (-dif, oferta["id"]))
            db.ex("INSERT INTO plati(lucrare_id, client_id, mester_id, suma, comision, tip, status, creat_la, "
                  "rezolvat_la) VALUES(?,?,?,?,?,?,?,?,?)", (lid, client_id, l["mester_id"], -dif, 0, "oferta",
                                                             "returnat", acum, acum))
        db.ex("UPDATE lucrari SET status = 'in_lucru' WHERE id = ?", (lid,))
        mesaj_sistem(lid, f"Clientul a acceptat prețul de {timp.lei(r['pret'])}. Meșterul poate începe.")
        notifica(l["mester_id"], "Clientul a acceptat prețul. Poți începe lucrarea.", lid)
        return
    # refuz: clientul plătește doar deplasarea, restul se întoarce
    taxa = min(config.TAXA_DEPLASARE, oferta["suma"] if oferta else 0)
    blocate = db.q("SELECT * FROM plati WHERE lucrare_id = ? AND status = 'blocat'", (lid,))
    for p in blocate:
        db.ex("UPDATE plati SET status = 'returnat', rezolvat_la = ? WHERE id = ?", (acum, p["id"]))
    if taxa:
        db.ex("INSERT INTO plati(lucrare_id, client_id, mester_id, suma, comision, tip, status, creat_la, rezolvat_la) "
              "VALUES(?,?,?,?,?,?,?,?,?)", (lid, client_id, l["mester_id"], taxa, round(taxa * config.COMISION, 2),
                                            "deplasare", "eliberat", acum, acum))
        if oferta:
            db.ex("UPDATE plati SET suma = suma - ? WHERE id = ?", (taxa, oferta["id"]))
    _returneaza_onchain(lid, blocate)
    db.ex("UPDATE lucrari SET status = 'anulata', anulat_motiv = 'Clientul a refuzat prețul de la fața locului' "
          "WHERE id = ?", (lid,))
    mesaj_sistem(lid, f"Clientul a refuzat prețul. A plătit doar deplasarea ({timp.lei(taxa)}), restul s-a întors.")
    notifica(l["mester_id"], f"Clientul a refuzat prețul. Primești taxa de deplasare: {timp.lei(taxa)}.", lid)


def cere_extra(lid, mester_id, suma, motiv):
    l = lucrare(lid)
    if l["mester_id"] != mester_id or l["status"] != "in_lucru":
        raise Eroare("Poți cere o lucrare în plus doar în timpul lucrului.")
    if suma <= 0 or not motiv.strip():
        raise Eroare("Scrie suma și ce lucrare în plus e nevoie.")
    db.ex("INSERT INTO extra(lucrare_id, suma, motiv, status, creat_la) VALUES(?,?,?,?,?)",
          (lid, suma, motiv.strip(), "trimisa", timp.iso(timp.acum())))
    mesaj_sistem(lid, f"Ofertă pentru lucrare în plus: {timp.lei(suma)} – {motiv.strip()}")
    notifica(l["client_id"], f"Ofertă pentru lucrare în plus: {timp.lei(suma)}", lid)


def raspunde_extra(eid, client_id, accept: bool):
    e = db.q1("SELECT * FROM extra WHERE id = ?", (eid,))
    l = lucrare(e["lucrare_id"])
    if l["client_id"] != client_id or e["status"] != "trimisa":
        raise Eroare("Oferta nu mai este valabilă.")
    db.ex("UPDATE extra SET status = ? WHERE id = ?", ("acceptata" if accept else "respinsa", eid))
    if accept:
        acum = timp.iso(timp.acum())
        pid = db.ex("INSERT INTO plati(lucrare_id, client_id, mester_id, suma, comision, tip, status, creat_la) "
                    "VALUES(?,?,?,?,?,?,?,?)", (l["id"], client_id, l["mester_id"], e["suma"], 0, "extra", "blocat", acum))
        db.ex("INSERT INTO plati(lucrare_id, client_id, mester_id, suma, comision, tip, status, creat_la) "
              "VALUES(?,?,?,?,?,?,?,?)", (l["id"], client_id, l["mester_id"], taxa_protectie(e["suma"]), 0,
                                          "protectie", "blocat", acum))
        _blocheaza_onchain(pid, l["id"], e["suma"])
        mesaj_sistem(l["id"], f"Lucrarea în plus a fost acceptată: {timp.lei(e['suma'])} plătiți și blocați.")
    else:
        mesaj_sistem(l["id"], "Clientul a refuzat lucrarea în plus.")
    notifica(l["mester_id"], "Clientul a " + ("acceptat" if accept else "refuzat") + " lucrarea în plus.", l["id"])


def extra_lucrare(lid):
    return db.q("SELECT * FROM extra WHERE lucrare_id = ? ORDER BY id", (lid,))


def lucrare_gata(lid, mester_id, nota="", poza=None):
    l = lucrare(lid)
    if l["mester_id"] != mester_id or l["status"] != "in_lucru":
        raise Eroare("Lucrarea nu e în lucru.")
    db.ex("UPDATE lucrari SET status = 'gata', gata_la = ?, nota_mester = ?, poza_dupa = ? WHERE id = ?",
          (timp.iso(timp.acum()), nota.strip(), poza, lid))
    mesaj_sistem(lid, "Meșterul a marcat lucrarea ca gata." + (f" Notă: {nota.strip()}" if nota.strip() else ""))
    notifica(l["client_id"], "Lucrarea e gata. Verifică și confirmă.", lid, extern=True)


def confirma_lucrare(lid, client_id):
    """Clientul confirmă. Banii mai stau blocați 24 de ore: în acest timp oricare parte poate deschide o dispută."""
    l = lucrare(lid)
    if l["client_id"] != client_id or l["status"] != "gata":
        raise Eroare("Lucrarea nu așteaptă confirmare.")
    acum = timp.acum()
    db.ex("UPDATE lucrari SET status = 'confirmata', confirmat_la = ? WHERE id = ?", (timp.iso(acum), lid))
    programeaza_feedback(lid, acum)
    pana = acum + timedelta(hours=config.FEREASTRA_DISPUTA_ORE)
    mesaj_sistem(lid, f"Ambele părți au confirmat. Banii pleacă la meșter pe {timp.data_ora(pana)}, dacă nimeni "
                      f"nu deschide o dispută până atunci.")
    notifica(l["mester_id"], f"Clientul a confirmat. Primești banii pe {timp.data_ora(pana)}.", lid, extern=True)


def elibereaza_plata(lid):
    """Banii blocați ajung la meșter (minus comisionul); taxa de protecție rămâne la SKILLIO."""
    l = lucrare(lid)
    acum = timp.iso(timp.acum())
    blocate = db.q("SELECT * FROM plati WHERE lucrare_id = ? AND status = 'blocat'", (lid,))
    net = 0
    for p in blocate:
        com = p["suma"] if p["tip"] == "protectie" else round(p["suma"] * config.COMISION, 2)
        db.ex("UPDATE plati SET status = 'eliberat', comision = ?, rezolvat_la = ? WHERE id = ?", (com, acum, p["id"]))
        net += p["suma"] - com
    db.ex("UPDATE lucrari SET status = 'finalizata' WHERE id = ?", (lid,))
    if not l["confirmat_la"]:
        db.ex("UPDATE lucrari SET confirmat_la = ? WHERE id = ?", (acum, lid))
        programeaza_feedback(lid, timp.acum())
    _elibereaza_onchain(lid, [p for p in blocate if p["tip"] != "protectie"])
    mesaj_sistem(lid, f"{timp.lei(net)} au ajuns la meșter (comision SKILLIO {config.PCT_COMISION}).")
    notifica(l["mester_id"], f"Ai încasat {timp.lei(net)} pentru „{l['titlu']}”.", lid, extern=True)


def elibereaza_scadente():
    """Rulează la fiecare încărcare: plătește lucrările și apelurile SOS al căror termen de dispută a trecut."""
    prag = timp.iso(timp.acum() - timedelta(hours=config.FEREASTRA_DISPUTA_ORE))
    for l in db.q("SELECT id FROM lucrari WHERE status = 'confirmata' AND confirmat_la <= ?", (prag,)):
        elibereaza_plata(l["id"])
    for s_ in db.q("SELECT id FROM sos WHERE status = 'incheiat' AND incheiat_la <= ?", (prag,)):
        _plateste_sos(s_["id"])


def nu_a_venit(lid, client_id):
    """Dacă meșterul nu a ajuns în ziua programată, clientul primește banii înapoi."""
    l = lucrare(lid)
    if l["client_id"] != client_id or l["status"] != "programata":
        raise Eroare("Acțiunea nu e disponibilă.")
    if timp.acum() < timp.din_iso(l["programat_la"]) + timedelta(hours=1):
        raise Eroare("Poți semnala că meșterul nu a venit la o oră după ora programată.")
    db.ex("INSERT INTO rapoarte(lucrare_id, autor_id, vizat_id, motiv, detalii, disputa, status, creat_la, "
          "rezolvat_la, rezolutie) VALUES(?,?,?,?,?,?,?,?,?,?)",
          (lid, client_id, l["mester_id"], "Meșterul nu a venit", "Nicio sosire confirmată de rețea.", 0,
           "confirmat", timp.iso(timp.acum()), timp.iso(timp.acum()), "Confirmat automat: rețeaua nu a "
           "înregistrat sosirea."))
    anuleaza_lucrare(lid, client_id, "Meșterul nu a venit")


# ---------------------------------------------------------------------------
# Recenzii și feedback în timp
# ---------------------------------------------------------------------------
ETAPE = {"final": ("Recenzie", 0), "zi1": ("După o zi", 1), "sapt1": ("După o săptămână", 7),
         "luna1": ("După o lună", 30)}
INTREBARI = {
    "zi1": "Lucrarea funcționează bine după o zi?",
    "sapt1": "Totul e încă în regulă după o săptămână?",
    "luna1": "A trecut o lună. Lucrarea ține în continuare?",
}


def programeaza_feedback(lid, de_la):
    l = lucrare(lid)
    for etapa, (_, zile) in ETAPE.items():
        db.ex("INSERT INTO feedback(lucrare_id, mester_id, client_id, etapa, scadent_la) VALUES(?,?,?,?,?)",
              (lid, l["mester_id"], l["client_id"], etapa, timp.iso(de_la + timedelta(days=zile))))


def feedback_de_dat(client_id):
    rows = db.q("SELECT f.*, l.titlu FROM feedback f JOIN lucrari l ON l.id = f.lucrare_id "
                "WHERE f.client_id = ? AND f.raspuns_la IS NULL AND f.scadent_la <= ? ORDER BY f.scadent_la",
                (client_id, timp.iso(timp.acum())))
    return rows


def feedback_lucrare(lid):
    return db.q("SELECT f.*, l.titlu FROM feedback f JOIN lucrari l ON l.id = f.lucrare_id "
                "WHERE f.lucrare_id = ? ORDER BY f.scadent_la", (lid,))


def da_recenzie(fid, client_id, criterii: dict, comentariu=""):
    f = db.q1("SELECT * FROM feedback WHERE id = ?", (fid,))
    if not f or f["client_id"] != client_id or f["etapa"] != "final" or f["raspuns_la"]:
        raise Eroare("Recenzia a fost deja trimisă.")
    if any(v is None for v in criterii.values()):
        raise Eroare("Dă o notă pentru fiecare criteriu.")
    nota = sum(criterii.values()) / len(criterii)
    db.ex("UPDATE feedback SET nota = ?, criterii = ?, comentariu = ?, raspuns_la = ? WHERE id = ?",
          (nota, json.dumps(criterii), comentariu.strip(), timp.iso(timp.acum()), fid))
    notifica(f["mester_id"], f"Recenzie nouă: {nota:.1f} din 5".replace(".", ","), f["lucrare_id"])


def raspunde_durabilitate(fid, client_id, ok: bool, comentariu=""):
    f = db.q1("SELECT * FROM feedback WHERE id = ?", (fid,))
    if not f or f["client_id"] != client_id or f["raspuns_la"]:
        raise Eroare("Ai răspuns deja.")
    db.ex("UPDATE feedback SET ok = ?, comentariu = ?, raspuns_la = ? WHERE id = ?",
          (int(ok), comentariu.strip(), timp.iso(timp.acum()), fid))
    if not ok:
        l = lucrare(f["lucrare_id"])
        notifica(f["mester_id"], f"Clientul spune că lucrarea „{l['titlu']}” are probleme "
                                 f"({ETAPE[f['etapa']][0].lower()}). Scrie-i în chat.", l["id"])
        mesaj_sistem(l["id"], f"{ETAPE[f['etapa']][0]}: clientul a semnalat o problemă. " + comentariu.strip())


def recenzii_mester(mester_id, limita=20):
    rows = db.q("SELECT f.*, l.titlu, u.nume AS client_nume FROM feedback f JOIN lucrari l ON l.id = f.lucrare_id "
                "JOIN utilizatori u ON u.id = f.client_id WHERE f.mester_id = ? AND f.etapa = 'final' "
                "AND f.nota IS NOT NULL ORDER BY f.raspuns_la DESC LIMIT ?", (mester_id, limita))
    for r in rows:
        r["criterii_d"] = json.loads(r["criterii"] or "{}")
        tine = db.q("SELECT etapa, ok FROM feedback WHERE lucrare_id = ? AND ok IS NOT NULL", (r["lucrare_id"],))
        r["tine"] = {t["etapa"]: t["ok"] for t in tine}
    return rows


def medii_criterii(mester_id):
    rows = db.q("SELECT criterii FROM feedback WHERE mester_id = ? AND etapa = 'final' AND criterii IS NOT NULL",
                (mester_id,))
    sume = {}
    for r in rows:
        for k, v in json.loads(r["criterii"]).items():
            sume.setdefault(k, []).append(v)
    return {k: sum(v) / len(v) for k, v in sume.items()}


# ---------------------------------------------------------------------------
# Rapoarte și dispute
# ---------------------------------------------------------------------------
def raporteaza(lid, autor_id, vizat_id, motiv, detalii=""):
    """Un raport. Dacă lucrarea e în curs (sau în cele 24 de ore), devine dispută: banii rămân blocați
    și decide un mediator uman din echipa SKILLIO."""
    l = lucrare(lid) if lid else None
    disputa = 0
    if l and autor_id in (l["client_id"], l["mester_id"]) and l["status"] in IN_CURS:
        disputa = 1
        db.ex("UPDATE lucrari SET status = 'disputa', status_inainte = ? WHERE id = ?", (l["status"], lid))
        cine = "Clientul" if autor_id == l["client_id"] else "Meșterul"
        mesaj_sistem(lid, f"{cine} a deschis o dispută. Banii rămân blocați până decide un mediator SKILLIO.")
        notifica(vizat_id, f"{cine} a deschis o dispută. Un mediator te contactează. Banii rămân blocați.", lid)
    db.ex("INSERT INTO rapoarte(lucrare_id, autor_id, vizat_id, motiv, detalii, disputa, status, creat_la) "
          "VALUES(?,?,?,?,?,?,?,?)", (lid, autor_id, vizat_id, motiv, detalii.strip(), disputa, "deschis",
                                      timp.iso(timp.acum())))
    for a in db.q("SELECT id FROM utilizatori WHERE rol = 'admin'"):
        notifica(a["id"], ("Dispută nouă: " if disputa else "Raport nou: ") + motiv, lid)


def rapoarte(status=None):
    sql = ("SELECT r.*, a.nume AS autor, v.nume AS vizat, l.titlu FROM rapoarte r "
           "LEFT JOIN utilizatori a ON a.id = r.autor_id LEFT JOIN utilizatori v ON v.id = r.vizat_id "
           "LEFT JOIN lucrari l ON l.id = r.lucrare_id")
    if status:
        return db.q(sql + " WHERE r.status = ? ORDER BY r.id DESC", (status,))
    return db.q(sql + " ORDER BY r.id DESC")


def rezolva_raport(rid, castiga_clientul: bool, rezolutie=""):
    """Decizia mediatorului uman. castiga_clientul=True: banii se întorc (meșterul păstrează doar deplasarea,
    dacă a venit). False: banii ajung la meșter."""
    r = db.q1("SELECT * FROM rapoarte WHERE id = ?", (rid,))
    l = lucrare(r["lucrare_id"]) if r["lucrare_id"] else None
    # „confirmat” = raportul autorului e întemeiat
    autor_client = bool(l) and r["autor_id"] == l["client_id"]
    confirmat = (castiga_clientul == autor_client) if (l and r["disputa"]) else castiga_clientul
    db.ex("UPDATE rapoarte SET status = ?, rezolvat_la = ?, rezolutie = ? WHERE id = ?",
          ("confirmat" if confirmat else "respins", timp.iso(timp.acum()), rezolutie.strip(), rid))
    if r["disputa"] and l and l["status"] == "disputa":
        acum = timp.iso(timp.acum())
        if castiga_clientul:
            blocate = db.q("SELECT * FROM plati WHERE lucrare_id = ? AND status = 'blocat'", (l["id"],))
            for p in blocate:
                db.ex("UPDATE plati SET status = 'returnat', rezolvat_la = ? WHERE id = ?", (acum, p["id"]))
            taxa = 0
            if l["sosit_la"]:
                taxa = config.TAXA_DEPLASARE
                db.ex("INSERT INTO plati(lucrare_id, client_id, mester_id, suma, comision, tip, status, creat_la, "
                      "rezolvat_la) VALUES(?,?,?,?,?,?,?,?,?)", (l["id"], l["client_id"], l["mester_id"], taxa,
                                                                 round(taxa * config.COMISION, 2), "deplasare",
                                                                 "eliberat", acum, acum))
            _returneaza_onchain(l["id"], blocate)
            db.ex("UPDATE lucrari SET status = 'anulata', anulat_motiv = 'Mediatorul a dat dreptate clientului' "
                  "WHERE id = ?", (l["id"],))
            mesaj_sistem(l["id"], "Mediatorul SKILLIO a dat dreptate clientului. Banii s-au întors"
                         + (f" (meșterul păstrează deplasarea, {timp.lei(taxa)})." if taxa else ".")
                         + (f" Motiv: {rezolutie.strip()}" if rezolutie.strip() else ""))
        else:
            mesaj_sistem(l["id"], "Mediatorul SKILLIO a dat dreptate meșterului."
                         + (f" Motiv: {rezolutie.strip()}" if rezolutie.strip() else ""))
            elibereaza_plata(l["id"])
    for uid in (r["autor_id"], r["vizat_id"]):
        if uid:
            notifica(uid, f"Mediatorul a decis în cazul „{r['motiv']}”.", r["lucrare_id"])


# ---------------------------------------------------------------------------
# SOS: un meșter real te ghidează prin video, în câteva minute
# ---------------------------------------------------------------------------
def cere_sos(client_id, meserie, problema, consimtamant):
    if not consimtamant:
        raise Eroare("Pentru siguranța ta, apelul se înregistrează. Bifează acordul ca să continui.")
    if not (problema or "").strip():
        raise Eroare("Scrie în două cuvinte ce s-a întâmplat.")
    deschis = db.q1("SELECT id FROM sos WHERE client_id = ? AND status IN ('asteapta','in_apel')", (client_id,))
    if deschis:
        return deschis["id"]
    sid = db.ex("INSERT INTO sos(client_id, meserie, problema, status, suma, camera, creat_la) VALUES(?,?,?,?,?,?,?)",
                (client_id, meserie, problema.strip(), "asteapta", config.SOS_PRET,
                 "skillio-sos-" + secrets.token_hex(5), timp.iso(timp.acum())))
    for m in mesteri(meserie=meserie, doar_disponibili=True)[:10]:
        notifica(m["id"], f"SOS: {problema.strip()[:50]}. Răspunde acum și primești {timp.lei(config.SOS_MESTER)}.")
    return sid


def sos(sid):
    return db.q1("SELECT * FROM sos WHERE id = ?", (int(sid),))


def sos_client(client_id):
    return db.q("SELECT * FROM sos WHERE client_id = ? ORDER BY id DESC LIMIT 5", (client_id,))


def sos_deschise(mester_id):
    m = user(mester_id)
    mes = meserii_lista(m)
    rows = db.q("SELECT * FROM sos WHERE status = 'asteapta' OR (mester_id = ? AND status IN ('in_apel','incheiat',"
                "'disputa')) ORDER BY id DESC", (mester_id,))
    return [r for r in rows if r["mester_id"] == mester_id or r["meserie"] in mes]


def accepta_sos(sid, mester_id):
    s_ = sos(sid)
    if s_["status"] != "asteapta":
        raise Eroare("Alt meșter a preluat deja apelul.")
    db.ex("UPDATE sos SET status = 'in_apel', mester_id = ?, inceput_la = ? WHERE id = ?",
          (mester_id, timp.iso(timp.acum()), sid))
    notifica(s_["client_id"], f"{user(mester_id)['nume']} intră în apel video cu tine.")


def incheie_sos(sid, uid):
    s_ = sos(sid)
    if s_["status"] != "in_apel" or uid not in (s_["client_id"], s_["mester_id"]):
        raise Eroare("Apelul nu e în desfășurare.")
    db.ex("UPDATE sos SET status = 'incheiat', incheiat_la = ? WHERE id = ?", (timp.iso(timp.acum()), sid))
    notifica(s_["client_id"] if uid == s_["mester_id"] else s_["mester_id"],
             f"Apelul SOS s-a încheiat. Plata pleacă în {config.FEREASTRA_DISPUTA_ORE} de ore dacă nu e dispută.")


def _plateste_sos(sid):
    db.ex("UPDATE sos SET status = 'eliberat', rezolvat_la = ? WHERE id = ?", (timp.iso(timp.acum()), sid))
    s_ = sos(sid)
    notifica(s_["mester_id"], f"Ai primit {timp.lei(config.SOS_MESTER)} pentru apelul SOS.")


def confirma_sos(sid, client_id):
    s_ = sos(sid)
    if s_["client_id"] != client_id or s_["status"] != "incheiat":
        raise Eroare("Apelul nu așteaptă confirmare.")
    _plateste_sos(sid)


def disputa_sos(sid, uid, motiv):
    s_ = sos(sid)
    if uid not in (s_["client_id"], s_["mester_id"]) or s_["status"] not in ("in_apel", "incheiat"):
        raise Eroare("Nu mai poți deschide o dispută pentru acest apel.")
    db.ex("UPDATE sos SET status = 'disputa', motiv_disputa = ? WHERE id = ?", (motiv.strip() or "Nu m-a ajutat", sid))
    for a in db.q("SELECT id FROM utilizatori WHERE rol = 'admin'"):
        notifica(a["id"], f"Dispută SOS #{sid}: {motiv.strip() or 'Nu m-a ajutat'}")


def rezolva_sos(sid, castiga_clientul: bool, rezolutie=""):
    if castiga_clientul:
        db.ex("UPDATE sos SET status = 'returnat', rezolvat_la = ?, rezolutie = ? WHERE id = ?",
              (timp.iso(timp.acum()), rezolutie.strip(), sid))
        notifica(sos(sid)["client_id"], f"Mediatorul a decis: primești înapoi {timp.lei(config.SOS_PRET)}.")
    else:
        db.ex("UPDATE sos SET rezolutie = ? WHERE id = ?", (rezolutie.strip(), sid))
        _plateste_sos(sid)


# ---------------------------------------------------------------------------
# Agentul clientului: o lucrare mare devine etape, fiecare cu cererea ei
# ---------------------------------------------------------------------------
def creeaza_etape(u, plan):
    ids = []
    for e in plan.get("etape", []):
        diag = {"pret_min": e.get("pret_min"), "pret_max": e.get("pret_max"), "durata_min": e.get("durata_min", 120),
                "materiale": e.get("materiale", []), "descriere": e.get("descriere", ""), "sursa": plan.get("sursa")}
        lid, _ = creeaza_lucrare(u["id"], e["titlu"], e.get("descriere") or e["titlu"], u["adresa"] or u["cartier"],
                                 u["cartier"], e["meserie"], False, None, None, diag)
        ids.append(lid)
    return ids


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
def mesaj_sistem(lid, text):
    db.ex("INSERT INTO mesaje(lucrare_id, autor_id, text, creat_la) VALUES(?,?,?,?)",
          (lid, None, text, timp.iso(timp.acum())))


def trimite_mesaj(lid, autor_id, text, poza=None):
    if not (text or "").strip() and not poza:
        return
    text, ascuns = filtreaza_contact(text or "")
    mid = db.ex("INSERT INTO mesaje(lucrare_id, autor_id, text, poza, creat_la) VALUES(?,?,?,?,?)",
                (lid, autor_id, text.strip(), poza, timp.iso(timp.acum())))
    marcheaza_citit(lid, autor_id, mid)
    if ascuns:
        mesaj_sistem(lid, "SKILLIO a ascuns datele de contact din mesaj. Numerele rămân private în ambele sensuri: "
                          "plata blocată, garanția și medierea funcționează doar în aplicație.")


_RE_TEL = re.compile(r"(?:\+?4?0|\b0)[\s.\-/]*7(?:[\s.\-/]*\d){8}|\b\d(?:[\s.\-/]*\d){8,}")
_RE_MAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_RE_APP = re.compile(r"\b(whats\s*app|wa\.me|telegram|signal|viber|revolut|messenger)\b", re.I)


def filtreaza_contact(text):
    nou = _RE_TEL.sub("•••", text)
    nou = _RE_MAIL.sub("•••", nou)
    nou = _RE_APP.sub("•••", nou)
    return nou, nou != text


def mesaje(lid):
    return db.q("SELECT * FROM mesaje WHERE lucrare_id = ? ORDER BY id", (lid,))


def marcheaza_citit(lid, uid, pana_la=None):
    if pana_la is None:
        pana_la = db.val("SELECT MAX(id) FROM mesaje WHERE lucrare_id = ?", (lid,), 0)
    db.ex("INSERT INTO citit(lucrare_id, user_id, ultimul_id) VALUES(?,?,?) ON CONFLICT(lucrare_id, user_id) "
          "DO UPDATE SET ultimul_id = MAX(ultimul_id, excluded.ultimul_id)", (lid, uid, pana_la))


def necitite(lid, uid):
    ultim = db.val("SELECT ultimul_id FROM citit WHERE lucrare_id = ? AND user_id = ?", (lid, uid), 0)
    return db.val("SELECT COUNT(*) FROM mesaje WHERE lucrare_id = ? AND id > ? AND autor_id IS NOT NULL "
                  "AND autor_id != ?", (lid, ultim, uid), 0)


def conversatii(uid):
    """Lucrările care au chat: cele cu meșter ales sau la care meșterul a trimis ofertă.
    Ultimul mesaj și numărul de necitite vin din 2 cereri pentru toate lucrările (nu câte 3 pe lucrare)."""
    rows = db.q("SELECT * FROM lucrari WHERE (client_id = ? OR mester_id = ?) AND mester_id IS NOT NULL "
                "ORDER BY id DESC", (uid, uid))
    if not rows:
        return rows
    ids = [l["id"] for l in rows]
    semne = ",".join("?" * len(ids))
    ultimele = {m["lucrare_id"]: m for m in db.q(
        f"SELECT * FROM mesaje WHERE id IN (SELECT MAX(id) FROM mesaje WHERE lucrare_id IN ({semne}) "
        f"GROUP BY lucrare_id)", tuple(ids))}
    necit = {r["lucrare_id"]: r["n"] for r in db.q(
        f"SELECT m.lucrare_id, COUNT(*) AS n FROM mesaje m LEFT JOIN citit c "
        f"ON c.lucrare_id = m.lucrare_id AND c.user_id = ? "
        f"WHERE m.lucrare_id IN ({semne}) AND m.id > COALESCE(c.ultimul_id, 0) "
        f"AND m.autor_id IS NOT NULL AND m.autor_id != ? GROUP BY m.lucrare_id", (uid, *ids, uid))}
    for l in rows:
        l["ultimul"] = ultimele.get(l["id"])
        l["necitite"] = necit.get(l["id"], 0)
        l["celalalt"] = user(l["mester_id"] if uid == l["client_id"] else l["client_id"])
    rows.sort(key=lambda l: l["ultimul"]["id"] if l["ultimul"] else 0, reverse=True)
    return rows


def total_necitite(uid):
    return sum(c["necitite"] for c in conversatii(uid))


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------
def ocupate(mester_id, ignora_lucrare=None):
    """Orele ocupate: lucrări programate + ore propuse în oferte + zile blocate manual."""
    rez = set()
    for l in db.q("SELECT id, programat_la, prog_propus FROM lucrari WHERE mester_id = ? "
                  "AND status IN ('acceptata','de_plata','programata','sosit','gata')", (mester_id,)):
        if l["id"] == ignora_lucrare:
            continue
        for c in (l["programat_la"], l["prog_propus"]):
            if c:
                d = timp.din_iso(c)
                rez.add((d.date().isoformat(), d.hour))
    for b in db.q("SELECT zi, ora FROM blocari WHERE mester_id = ?", (mester_id,)):
        rez.add((b["zi"], b["ora"]))
    return rez


def slot_liber(mester_id, cand: datetime, ignora_lucrare=None) -> bool:
    ocup = ocupate(mester_id, ignora_lucrare)
    return (cand.date().isoformat(), cand.hour) not in ocup and (cand.date().isoformat(), -1) not in ocup


def sloturi_libere(mester_id, zile=config.ZILE_CALENDAR, ignora_lucrare=None):
    acum = timp.acum()
    ocup = ocupate(mester_id, ignora_lucrare)
    rez = []
    for z in range(zile):
        zi = (acum + timedelta(days=z)).date()
        if (zi.isoformat(), -1) in ocup:
            continue
        for h in config.SLOTURI:
            cand = datetime(zi.year, zi.month, zi.day, h)
            if cand <= acum + timedelta(minutes=30):
                continue
            if (zi.isoformat(), h) not in ocup:
                rez.append(cand)
    return rez


def comuta_blocare(mester_id, zi: str, ora: int):
    if db.q1("SELECT 1 FROM blocari WHERE mester_id = ? AND zi = ? AND ora = ?", (mester_id, zi, ora)):
        db.ex("DELETE FROM blocari WHERE mester_id = ? AND zi = ? AND ora = ?", (mester_id, zi, ora))
    else:
        db.ex("INSERT INTO blocari(mester_id, zi, ora) VALUES(?,?,?)", (mester_id, zi, ora))


def calendar_mester(mester_id, zile=config.ZILE_CALENDAR):
    acum = timp.acum()
    lucr = db.q("SELECT * FROM lucrari WHERE mester_id = ? AND status IN "
                "('acceptata','de_plata','programata','sosit','gata','finalizata')", (mester_id,))
    blocate = {(b["zi"], b["ora"]) for b in db.q("SELECT zi, ora FROM blocari WHERE mester_id = ?", (mester_id,))}
    zile_l = []
    for z in range(zile):
        zi = (acum + timedelta(days=z)).date()
        sloturi = []
        for h in config.SLOTURI:
            l = next((x for x in lucr if (x["programat_la"] or x["prog_propus"] or "").startswith(
                f"{zi.isoformat()}T{h:02d}")), None)
            sloturi.append({"ora": h, "lucrare": l, "blocat": (zi.isoformat(), h) in blocate or
                            (zi.isoformat(), -1) in blocate})
        zile_l.append({"zi": zi, "sloturi": sloturi})
    return zile_l


# ---------------------------------------------------------------------------
# Notificări
# ---------------------------------------------------------------------------
def notifica(uid, text, lid=None, extern=False):
    """Notificare în aplicație (clopoțelul). Cu extern=True pleacă și pe email / SMS, dacă sunt configurate."""
    db.ex("INSERT INTO notificari(user_id, text, lucrare_id, creat_la) VALUES(?,?,?,?)",
          (uid, text, lid, timp.iso(timp.acum())))
    if extern:
        mesaje_externe.anunta(user(uid), text)


def notificari(uid, limita=40):
    return db.q("SELECT * FROM notificari WHERE user_id = ? ORDER BY id DESC LIMIT ?", (uid, limita))


def notificari_necitite(uid):
    return db.val("SELECT COUNT(*) FROM notificari WHERE user_id = ? AND citit = 0", (uid,), 0)


def marcheaza_notificari(uid):
    db.ex("UPDATE notificari SET citit = 1 WHERE user_id = ? AND citit = 0", (uid,))


# ---------------------------------------------------------------------------
# Statistici
# ---------------------------------------------------------------------------
def statistici_mester(mid):
    acum = timp.acum()
    inceput_sapt = (acum - timedelta(days=acum.weekday())).replace(hour=0, minute=0, second=0)
    platite = db.q("SELECT * FROM plati WHERE mester_id = ?", (mid,))
    return {
        "incasat_total": sum(p["suma"] - p["comision"] for p in platite if p["status"] == "eliberat"),
        "incasat_sapt": sum(p["suma"] - p["comision"] for p in platite if p["status"] == "eliberat"
                            and p["rezolvat_la"] and p["rezolvat_la"] >= timp.iso(inceput_sapt)),
        "blocat": sum(p["suma"] for p in platite if p["status"] == "blocat"),
        "oferte_trimise": db.val("SELECT COUNT(*) FROM oferte WHERE mester_id = ?", (mid,), 0),
        "oferte_acceptate": db.val("SELECT COUNT(*) FROM oferte WHERE mester_id = ? AND status = 'acceptata'",
                                   (mid,), 0),
    }


def statistici_platforma():
    p = db.q("SELECT * FROM plati")
    return {
        "utilizatori": db.val("SELECT COUNT(*) FROM utilizatori WHERE rol = 'client'", implicit=0),
        "mesteri": db.val("SELECT COUNT(*) FROM utilizatori WHERE rol = 'mester'", implicit=0),
        "lucrari_active": db.val(f"SELECT COUNT(*) FROM lucrari WHERE status IN {ACTIVE}", implicit=0),
        "finalizate": db.val("SELECT COUNT(*) FROM lucrari WHERE status = 'finalizata'", implicit=0),
        "blocat": sum(x["suma"] for x in p if x["status"] == "blocat"),
        "volum": sum(x["suma"] for x in p if x["status"] == "eliberat"),
        "comision": sum(x["comision"] for x in p if x["status"] == "eliberat"),
        "rapoarte_deschise": db.val("SELECT COUNT(*) FROM rapoarte WHERE status = 'deschis'", implicit=0),
    }
