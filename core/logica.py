"""Regulile aplicației: conturi, solicitări, oferte, programări, plăți, recenzii, rapoarte.

Ecranele (views/) doar afișează și apelează funcțiile de aici. Dacă vreți să
schimbați o regulă (ex. comisionul), o schimbați într-un singur loc.

Viața unei lucrări:
    deschisa    clientul a trimis solicitarea, meșterii trimit oferte
    acceptata   clientul a ales o ofertă, se stabilește ora
    de_plata    ora e stabilită de amândoi, clientul plătește
    programata  plătit, banii sunt blocați până la final
    sosit       rețeaua a confirmat că meșterul e la adresă
    gata        meșterul a terminat, așteaptă confirmarea clientului
    finalizata  clientul a confirmat, banii au ajuns la meșter
    disputa     clientul a raportat o problemă, decide un admin
    anulata
"""
import json
import secrets
from datetime import datetime, timedelta

from services import geo, mesaje_externe, nokia, solana, stocare

from . import config, db, timp, trust

STATUS = {
    "deschisa": ("Așteaptă oferte", "neutru"),
    "acceptata": ("Stabiliți ora", "neutru"),
    "de_plata": ("De plătit", "escrow"),
    "programata": ("Programată", "ok"),
    "sosit": ("Meșterul e la tine", "ok"),
    "gata": ("Confirmă lucrarea", "escrow"),
    "finalizata": ("Finalizată", "ok"),
    "disputa": ("În verificare", "danger"),
    "anulata": ("Anulată", "neutru"),
}
ACTIVE = ("deschisa", "acceptata", "de_plata", "programata", "sosit", "gata", "disputa")


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
    verificat, _ = nokia.verifica_numar(telefon)
    schimbat, _ = nokia.sim_schimbat_recent(telefon)
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
    """Login fără parolă: numărul e verificat de rețea (Nokia), apoi verificăm SIM swap."""
    telefon = normalizeaza_telefon(telefon)
    u = user_dupa_telefon(telefon)
    if not u:
        raise Eroare("Nu găsim un cont cu acest număr. Creează unul în câteva secunde.")
    verificat, mod = nokia.verifica_numar(telefon)
    if not verificat:
        raise Eroare("Rețeaua nu confirmă că numărul e pe acest telefon. Încearcă de pe telefonul cu acest SIM.")
    schimbat, _ = nokia.sim_schimbat_recent(telefon)
    db.ex("UPDATE utilizatori SET numar_verificat = 1, sim_ok = ?, sim_verificat_la = ? WHERE id = ?",
          (int(not schimbat), timp.iso(timp.acum()), u["id"]))
    return u["id"], mod, schimbat


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
    if l["status"] in ("finalizata", "anulata", "sosit", "gata", "disputa"):
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
    _blocheaza_onchain(pid, lid, o["total"])
    db.ex("UPDATE lucrari SET status = 'programata' WHERE id = ?", (lid,))
    mesaj_sistem(lid, f"{timp.lei(o['total'])} plătiți și blocați în SKILLIO până la finalul lucrării.")
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
    la_adresa, mod = nokia.e_la_adresa(m["telefon"], l["lat"], l["lon"], config.RAZA_SOSIRE_M,
                                       bool(m["departe_demo"]))
    if not la_adresa:
        raise Eroare("Rețeaua te localizează departe de adresa clientului. Apasă din nou când ajungi.")
    acum = timp.acum()
    prog = timp.din_iso(l["programat_la"])
    punctual = int(acum <= prog + timedelta(minutes=config.TOLERANTA_PUNCTUAL_MIN))
    db.ex("UPDATE lucrari SET status = 'sosit', sosit_la = ?, sosire_mod = ?, punctual = ? WHERE id = ?",
          (timp.iso(acum), mod, punctual, lid))
    text = "Sosire confirmată de rețeaua Nokia" if mod == "live" else "Sosire confirmată (simulare rețea)"
    mesaj_sistem(lid, f"{text}: {m['nume']} e la adresă, ora {acum:%H:%M}" + ("." if punctual else " (cu întârziere)."))
    notifica(l["client_id"], f"{m['nume']} a ajuns. Sosirea e confirmată de rețea.", lid)
    return mod, punctual


def cere_extra(lid, mester_id, suma, motiv):
    l = lucrare(lid)
    if l["mester_id"] != mester_id or l["status"] not in ("sosit", "programata"):
        raise Eroare("Poți cere o lucrare în plus doar la lucrările în curs.")
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
        pid = db.ex("INSERT INTO plati(lucrare_id, client_id, mester_id, suma, comision, tip, status, creat_la) "
                    "VALUES(?,?,?,?,?,?,?,?)", (l["id"], client_id, l["mester_id"], e["suma"], 0, "extra", "blocat",
                                                timp.iso(timp.acum())))
        _blocheaza_onchain(pid, l["id"], e["suma"])
        mesaj_sistem(l["id"], f"Lucrarea în plus a fost acceptată: {timp.lei(e['suma'])} plătiți și blocați.")
    else:
        mesaj_sistem(l["id"], "Clientul a refuzat lucrarea în plus.")
    notifica(l["mester_id"], "Clientul a " + ("acceptat" if accept else "refuzat") + " lucrarea în plus.", l["id"])


def extra_lucrare(lid):
    return db.q("SELECT * FROM extra WHERE lucrare_id = ? ORDER BY id", (lid,))


def lucrare_gata(lid, mester_id, nota="", poza=None):
    l = lucrare(lid)
    if l["mester_id"] != mester_id or l["status"] != "sosit":
        raise Eroare("Apasă întâi „Am ajuns”, ca rețeaua să confirme sosirea.")
    db.ex("UPDATE lucrari SET status = 'gata', gata_la = ?, nota_mester = ?, poza_dupa = ? WHERE id = ?",
          (timp.iso(timp.acum()), nota.strip(), poza, lid))
    mesaj_sistem(lid, "Meșterul a marcat lucrarea ca gata." + (f" Notă: {nota.strip()}" if nota.strip() else ""))
    notifica(l["client_id"], "Lucrarea e gata. Verifică și confirmă ca să plătești meșterul.", lid, extern=True)


def confirma_lucrare(lid, client_id):
    """Clientul bifează că totul e în regulă: banii blocați ajung la meșter, minus comisionul."""
    l = lucrare(lid)
    if l["client_id"] != client_id or l["status"] != "gata":
        raise Eroare("Lucrarea nu așteaptă confirmare.")
    acum = timp.acum()
    total = 0
    blocate = db.q("SELECT * FROM plati WHERE lucrare_id = ? AND status = 'blocat'", (lid,))
    for p in blocate:
        com = round(p["suma"] * config.COMISION, 2)
        db.ex("UPDATE plati SET status = 'eliberat', comision = ?, rezolvat_la = ? WHERE id = ?",
              (com, timp.iso(acum), p["id"]))
        total += p["suma"]
    db.ex("UPDATE lucrari SET status = 'finalizata', confirmat_la = ? WHERE id = ?", (timp.iso(acum), lid))
    _elibereaza_onchain(lid, blocate)
    programeaza_feedback(lid, acum)
    net = total * (1 - config.COMISION)
    mesaj_sistem(lid, f"Clientul a confirmat lucrarea. {timp.lei(net)} au ajuns la meșter "
                      f"(din {timp.lei(total)}, comision SKILLIO {config.COMISION:.0%}).")
    notifica(l["mester_id"], f"Ai încasat {timp.lei(net)} pentru „{l['titlu']}”.", lid, extern=True)


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
    l = lucrare(lid) if lid else None
    disputa = 0
    if l and autor_id == l["client_id"] and l["status"] in ("sosit", "gata"):
        disputa = 1
        db.ex("UPDATE lucrari SET status = 'disputa' WHERE id = ?", (lid,))
        mesaj_sistem(lid, "Clientul a raportat o problemă. Banii rămân blocați până decide echipa SKILLIO.")
        notifica(l["mester_id"], "Clientul a raportat o problemă la lucrare. Banii rămân blocați până la verificare.",
                 lid)
    db.ex("INSERT INTO rapoarte(lucrare_id, autor_id, vizat_id, motiv, detalii, disputa, status, creat_la) "
          "VALUES(?,?,?,?,?,?,?,?)", (lid, autor_id, vizat_id, motiv, detalii.strip(), disputa, "deschis",
                                      timp.iso(timp.acum())))
    for a in db.q("SELECT id FROM utilizatori WHERE rol = 'admin'"):
        notifica(a["id"], f"Raport nou: {motiv}", lid)


def rapoarte(status=None):
    sql = ("SELECT r.*, a.nume AS autor, v.nume AS vizat, l.titlu FROM rapoarte r "
           "LEFT JOIN utilizatori a ON a.id = r.autor_id LEFT JOIN utilizatori v ON v.id = r.vizat_id "
           "LEFT JOIN lucrari l ON l.id = r.lucrare_id")
    if status:
        return db.q(sql + " WHERE r.status = ? ORDER BY r.id DESC", (status,))
    return db.q(sql + " ORDER BY r.id DESC")


def rezolva_raport(rid, confirmat: bool, rezolutie=""):
    r = db.q1("SELECT * FROM rapoarte WHERE id = ?", (rid,))
    db.ex("UPDATE rapoarte SET status = ?, rezolvat_la = ?, rezolutie = ? WHERE id = ?",
          ("confirmat" if confirmat else "respins", timp.iso(timp.acum()), rezolutie.strip(), rid))
    if r["disputa"] and r["lucrare_id"]:
        l = lucrare(r["lucrare_id"])
        if l["status"] == "disputa":
            if confirmat:  # clientul are dreptate: banii se întorc
                platite = db.q("SELECT * FROM plati WHERE lucrare_id = ? AND status = 'blocat'", (l["id"],))
                for p in platite:
                    db.ex("UPDATE plati SET status = 'returnat', rezolvat_la = ? WHERE id = ?",
                          (timp.iso(timp.acum()), p["id"]))
                _returneaza_onchain(l["id"], platite)
                db.ex("UPDATE lucrari SET status = 'anulata', anulat_motiv = 'Dispută câștigată de client' "
                      "WHERE id = ?", (l["id"],))
                mesaj_sistem(l["id"], "Echipa SKILLIO a dat dreptate clientului. Banii s-au întors la client.")
            else:  # meșterul are dreptate: lucrarea e confirmată
                db.ex("UPDATE lucrari SET status = 'gata' WHERE id = ?", (l["id"],))
                confirma_lucrare(l["id"], l["client_id"])
                mesaj_sistem(l["id"], "Echipa SKILLIO a verificat lucrarea și a confirmat-o.")
    for uid in (r["autor_id"], r["vizat_id"]):
        if uid:
            notifica(uid, f"Raportul „{r['motiv']}” a fost {'confirmat' if confirmat else 'respins'}.", r["lucrare_id"])


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
def mesaj_sistem(lid, text):
    db.ex("INSERT INTO mesaje(lucrare_id, autor_id, text, creat_la) VALUES(?,?,?,?)",
          (lid, None, text, timp.iso(timp.acum())))


def trimite_mesaj(lid, autor_id, text, poza=None):
    if not (text or "").strip() and not poza:
        return
    l = lucrare(lid)
    mid = db.ex("INSERT INTO mesaje(lucrare_id, autor_id, text, poza, creat_la) VALUES(?,?,?,?,?)",
                (lid, autor_id, (text or "").strip(), poza, timp.iso(timp.acum())))
    marcheaza_citit(lid, autor_id, mid)


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
