"""Baza de date și câteva funcții scurte pentru interogări.

Merge pe două motoare, ales automat din .env:
    - fără DATABASE_URL: SQLite, un fișier local (data/skillio.db). Bun pentru demo și lucru pe laptop.
    - cu DATABASE_URL=postgresql://...: PostgreSQL (de ex. Tiger Data). Bun pentru producție.
Codul aplicației scrie SQL o singură dată, cu semnul ? pentru parametri; aici se traduce pentru PostgreSQL.


    q(sql, params)   -> listă de dicționare
    q1(sql, params)  -> un dicționar sau None
    val(sql, params) -> o singură valoare
    ex(sql, params)  -> execută o modificare și întoarce id-ul rândului nou

Fiecare modificare crește un contor („versiune”). Aplicația se uită la el din
2 în 2 secunde și se reîmprospătează singură când se schimbă ceva, așa că
telefonul clientului și cel al meșterului rămân sincronizate.
"""
import atexit
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from decimal import Decimal

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS utilizatori (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telefon TEXT UNIQUE,
    nume TEXT,
    rol TEXT,                        -- client | mester | admin
    creat_la TEXT,
    poza TEXT,                       -- poza de profil (cale fișier)
    numar_verificat INTEGER DEFAULT 0,   -- Nokia Number Verification
    sim_ok INTEGER DEFAULT 1,            -- Nokia SIM Swap: 1 = SIM neschimbat recent
    sim_verificat_la TEXT,
    adresa TEXT DEFAULT '',
    cartier TEXT,
    lat REAL,
    lon REAL,
    ghid_vazut INTEGER DEFAULT 0,
    -- doar pentru meșteri
    despre TEXT DEFAULT '',
    meserii TEXT DEFAULT '',         -- chei separate prin virgulă
    experienta_ani INTEGER DEFAULT 0,
    tarif_ora INTEGER DEFAULT 0,     -- preț orientativ, lei/oră
    raza_km REAL DEFAULT 8,
    disponibil INTEGER DEFAULT 1,
    act_status TEXT DEFAULT 'lipsa', -- lipsa | in_asteptare | verificat
    act_poza TEXT,
    departe_demo INTEGER DEFAULT 0,  -- doar pentru prezentare: simulează că nu e la adresă
    email TEXT,                      -- din Auth0 (pentru notificări prin email)
    auth_sub TEXT,                   -- id-ul contului Auth0 („sub”)
    notif_extern INTEGER DEFAULT 1   -- vrea notificări prin email / SMS
);
CREATE TABLE IF NOT EXISTS sesiuni (
    token TEXT PRIMARY KEY, user_id INTEGER, creat_la TEXT, expira_la TEXT
);
CREATE TABLE IF NOT EXISTS portofoliu (
    id INTEGER PRIMARY KEY AUTOINCREMENT, mester_id INTEGER, poza TEXT, descriere TEXT, creat_la TEXT
);
CREATE TABLE IF NOT EXISTS lucrari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    titlu TEXT,
    descriere TEXT,
    adresa TEXT,
    cartier TEXT,
    lat REAL,
    lon REAL,
    poza TEXT,
    urgent INTEGER DEFAULT 0,
    buget INTEGER,
    meserie TEXT,
    diagnostic TEXT,                 -- JSON de la asistentul AI
    status TEXT,                     -- deschisa | acceptata | programata | sosit | gata | finalizata | disputa | anulata
    creat_la TEXT,
    mester_id INTEGER,
    oferta_id INTEGER,
    prog_propus TEXT,                -- ora propusă și încă neconfirmată de cealaltă parte
    prog_propus_de TEXT,             -- client | mester
    programat_la TEXT,               -- ora stabilită de ambele părți
    sosit_la TEXT,
    punctual INTEGER,
    sosire_mod TEXT,                 -- live | simulat
    gata_la TEXT,
    nota_mester TEXT,
    poza_dupa TEXT,
    confirmat_la TEXT,
    anulat_motiv TEXT
);
CREATE TABLE IF NOT EXISTS invitatii (
    lucrare_id INTEGER, mester_id INTEGER, loc INTEGER, status TEXT DEFAULT 'noua',  -- noua | refuzata
    PRIMARY KEY (lucrare_id, mester_id)
);
CREATE TABLE IF NOT EXISTS oferte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lucrare_id INTEGER, mester_id INTEGER,
    pret REAL,                       -- prețul cerut de meșter
    total REAL,                      -- ce plătește clientul (cu sporul de urgență)
    propus_la TEXT, mesaj TEXT,
    status TEXT,                     -- trimisa | acceptata | respinsa | retrasa
    creat_la TEXT
);
CREATE TABLE IF NOT EXISTS plati (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lucrare_id INTEGER, client_id INTEGER, mester_id INTEGER,
    suma REAL, comision REAL,
    tip TEXT,                        -- oferta | extra
    status TEXT,                     -- blocat | eliberat | returnat
    creat_la TEXT, rezolvat_la TEXT
);
CREATE TABLE IF NOT EXISTS extra (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lucrare_id INTEGER, suma REAL, motiv TEXT,
    status TEXT,                     -- trimisa | acceptata | respinsa
    creat_la TEXT
);
CREATE TABLE IF NOT EXISTS mesaje (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lucrare_id INTEGER, autor_id INTEGER,   -- autor_id NULL = mesaj de sistem
    text TEXT, poza TEXT, creat_la TEXT
);
CREATE TABLE IF NOT EXISTS citit (
    lucrare_id INTEGER, user_id INTEGER, ultimul_id INTEGER DEFAULT 0,
    PRIMARY KEY (lucrare_id, user_id)
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lucrare_id INTEGER, mester_id INTEGER, client_id INTEGER,
    etapa TEXT,                      -- final | zi1 | sapt1 | luna1
    scadent_la TEXT, raspuns_la TEXT,
    nota REAL,                       -- media criteriilor (doar la etapa „final”)
    criterii TEXT,                   -- JSON cu nota pe fiecare criteriu
    ok INTEGER,                      -- 1/0 la etapele zi1, sapt1, luna1
    comentariu TEXT
);
CREATE TABLE IF NOT EXISTS rapoarte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lucrare_id INTEGER, autor_id INTEGER, vizat_id INTEGER,
    motiv TEXT, detalii TEXT, disputa INTEGER DEFAULT 0,
    status TEXT,                     -- deschis | confirmat | respins
    creat_la TEXT, rezolvat_la TEXT, rezolutie TEXT
);
CREATE TABLE IF NOT EXISTS blocari (
    mester_id INTEGER, zi TEXT, ora INTEGER, PRIMARY KEY (mester_id, zi, ora)
);
CREATE TABLE IF NOT EXISTS notificari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, text TEXT, lucrare_id INTEGER, citit INTEGER DEFAULT 0, creat_la TEXT
);
CREATE TABLE IF NOT EXISTS setari (cheie TEXT PRIMARY KEY, valoare TEXT);
CREATE TABLE IF NOT EXISTS sondaj (              -- Living Labs: chestionarul din aplicație
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, rol TEXT,
    usor INTEGER, incredere INTEGER, recomanda INTEGER, ar_folosi TEXT, ce_lipseste TEXT, creat_la TEXT
);
CREATE INDEX IF NOT EXISTS i_lucrari_client ON lucrari(client_id);
CREATE INDEX IF NOT EXISTS i_lucrari_mester ON lucrari(mester_id);
CREATE INDEX IF NOT EXISTS i_feedback_mester ON feedback(mester_id);
CREATE INDEX IF NOT EXISTS i_mesaje_lucrare ON mesaje(lucrare_id);
"""



PG = bool(config.DATABASE_URL)
# tabelele care au coloană „id” (la INSERT întoarcem id-ul rândului nou)
_CU_ID = {"utilizatori", "portofoliu", "lucrari", "oferte", "plati", "extra", "mesaje", "feedback", "rapoarte",
          "notificari", "sondaj"}
# coloane adăugate după prima versiune: le adăugăm și în bazele vechi
_COLOANE_NOI = [("utilizatori", "email", "TEXT"), ("utilizatori", "auth_sub", "TEXT"),
                ("utilizatori", "notif_extern", "INTEGER DEFAULT 1"), ("sesiuni", "expira_la", "TEXT"),
                ("utilizatori", "sol_wallet", "TEXT"),             # adresa Solana a meșterului (opțional)
                ("plati", "lamports", "INTEGER"), ("plati", "tx_lock", "TEXT"), ("plati", "tx_final", "TEXT"),
                ("lucrari", "pasaport", "TEXT"), ("lucrari", "tx_pasaport", "TEXT")]


def _schema_pg():
    s = SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY").replace(" REAL", " DOUBLE PRECISION")
    return re.sub(r"--[^\n]*", "", s)


def _sql_pg(sql):
    """Traduce SQL-ul scris pentru SQLite în dialectul PostgreSQL."""
    sql = sql.replace("%", "%%").replace("?", "%s")
    if sql.lstrip().upper().startswith("INSERT OR IGNORE"):
        sql = re.sub(r"(?i)INSERT OR IGNORE", "INSERT", sql, count=1) + " ON CONFLICT DO NOTHING"
    sql = sql.replace("MAX(ultimul_id, excluded.ultimul_id)", "GREATEST(citit.ultimul_id, excluded.ultimul_id)")
    m = re.match(r"(?is)\s*INSERT INTO (\w+)", sql)
    if m and m.group(1) in _CU_ID and "RETURNING" not in sql.upper():
        sql += " RETURNING id"
    return sql


def _param(v):
    return int(v) if isinstance(v, bool) else v


def _rand(d):
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in d.items()}


class _Cursor:
    def __init__(self, cur, lastrowid=None):
        self._cur, self.lastrowid = cur, lastrowid

    def fetchall(self):
        return [_rand(dict(r)) for r in self._cur.fetchall()] if self._cur.description else []

    def fetchone(self):
        if not self._cur.description:
            return None
        r = self._cur.fetchone()
        return tuple(_rand(dict(r)).values()) if (PG and r is not None) else r


class _Conexiune:
    """Aceeași interfață (execute → cursor cu fetchall/fetchone/lastrowid) pentru ambele motoare."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, p=()):
        p = tuple(_param(x) for x in p)
        if not PG:
            cur = self.raw.execute(sql, p)
            return _Cursor(cur, cur.lastrowid)
        cur = self.raw.cursor()
        cur.execute(_sql_pg(sql), p)
        last = None
        if cur.description and cur.description[0].name == "id" and sql.lstrip().upper().startswith("INSERT"):
            r = cur.fetchone()
            last = r["id"] if r else None
        return _Cursor(cur, last)


_pool = None
_pool_lock = threading.Lock()


def _pg_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
            _pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=10, open=True,
                                   kwargs={"row_factory": dict_row, "autocommit": False})
            atexit.register(_pool.close)
        return _pool


_local = threading.local()


@contextmanager
def o_tranzactie():
    """Tot ce rulează înăuntru folosește o singură conexiune și un singur commit.
    Datele demo (mii de rânduri) se scriu așa într-o clipă, chiar și pe o bază din cloud."""
    if getattr(_local, "c", None) is not None:
        yield _local.c
        return
    with conn() as c:
        _local.c = c
        try:
            yield c
        finally:
            _local.c = None
            _dupa_scriere()


@contextmanager
def conn():
    if getattr(_local, "c", None) is not None:      # deja într-o tranzacție: o refolosim
        yield _local.c
        return
    if PG:
        with _pg_pool().connection() as raw:   # face commit singur la final, sau rollback la eroare
            yield _Conexiune(raw)
        return
    c = sqlite3.connect(config.DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    try:
        yield _Conexiune(c)
        c.commit()
    finally:
        c.close()


# --- cache pentru citiri ----------------------------------------------------------
# Un ecran face zeci de citiri (de ex. Trust Score-ul fiecărui meșter). Pe o bază din cloud fiecare citire
# înseamnă un drum prin internet, așa că le ținem minte până la prima modificare (orice ex() golește cache-ul).
# Siguranță: o intrare expiră oricum după CACHE_SECUNDE, ca să prindem și scrierile făcute din alt proces.
CACHE_SECUNDE = 20
_cache: dict = {}
_cache_lock = threading.Lock()


def goleste_cache():
    with _cache_lock:
        _cache.clear()


def _citeste(cheie, calculeaza):
    if getattr(_local, "c", None) is not None:      # într-o tranzacție: citim direct
        return calculeaza()
    acum = time.monotonic()
    with _cache_lock:
        r = _cache.get(cheie)
    if r is not None and acum - r[0] < CACHE_SECUNDE:
        return r[1]
    gen = _generatie
    val_ = calculeaza()
    with _cache_lock:
        if gen == _generatie:                        # nicio scriere între timp
            if len(_cache) > 5000:
                _cache.clear()
            _cache[cheie] = (acum, val_)
    return val_


_generatie = 0


def _dupa_scriere():
    global _generatie
    with _cache_lock:
        _generatie += 1
        _cache.clear()


@contextmanager
def _conn_citire():
    """Pentru citiri pe PostgreSQL: fără BEGIN/COMMIT, deci un singur drum prin rețea pe cerere."""
    if not PG or getattr(_local, "c", None) is not None:
        with conn() as c:
            yield c
        return
    with _pg_pool().connection() as raw:
        raw.autocommit = True
        try:
            yield _Conexiune(raw)
        finally:
            raw.autocommit = False


def _q_direct(sql, p=()):
    with _conn_citire() as c:
        return [dict(r) for r in c.execute(sql, p).fetchall()]


def q(sql, p=()):
    rows = _citeste(("q", sql, tuple(p)), lambda: _q_direct(sql, p))
    return [dict(r) for r in rows]                   # copii, ca un ecran să nu strice cache-ul


def q1(sql, p=()):
    r = q(sql, p)
    return r[0] if r else None


def _val_direct(sql, p=()):
    with _conn_citire() as c:
        r = c.execute(sql, p).fetchone()
    return r[0] if r else None


def val(sql, p=(), implicit=None):
    r = _citeste(("v", sql, tuple(p)), lambda: _val_direct(sql, p))
    return r if r is not None else implicit


def ex(sql, p=()):
    try:
        with conn() as c:
            cur = c.execute(sql, p)
            c.execute("UPDATE setari SET valoare = CAST(CAST(valoare AS INTEGER) + 1 AS TEXT) WHERE cheie = 'versiune'")
            return cur.lastrowid
    finally:
        _dupa_scriere()


def versiune():
    """Citită mereu direct din bază (fără cache), ca telefoanele să afle de schimbările altora."""
    global _ultima_versiune
    v = _val_direct("SELECT valoare FROM setari WHERE cheie = 'versiune'")
    v = int(v) if v is not None else 0
    if v != _ultima_versiune:                        # a scris cineva (și din alt proces): golim cache-ul
        _ultima_versiune = v
        _dupa_scriere()
    return v


_ultima_versiune = None


def setare(cheie, implicit=None):
    return val("SELECT valoare FROM setari WHERE cheie = ?", (cheie,), implicit)


def pune_setare(cheie, valoare):
    ex("INSERT INTO setari(cheie, valoare) VALUES(?, ?) "
       "ON CONFLICT(cheie) DO UPDATE SET valoare = excluded.valoare", (cheie, str(valoare)))


def _coloane(c, tabel):
    if PG:
        rows = c.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_name = ?",
                         (tabel,)).fetchall()
        return {r["name"] for r in rows}
    return {r[1] for r in c.raw.execute(f"PRAGMA table_info({tabel})").fetchall()}


def init():
    """Creează folderele și tabelele. La prima pornire pune și datele demo."""
    config.UPLOADS.mkdir(parents=True, exist_ok=True)
    with conn() as c:
        if PG:
            c.raw.execute(_schema_pg())
        else:
            c.raw.execute("PRAGMA journal_mode=WAL")
            c.raw.executescript(SCHEMA)
        for tabel, col, tip in _COLOANE_NOI:
            if col not in _coloane(c, tabel):
                c.execute(f"ALTER TABLE {tabel} ADD COLUMN {col} {tip}")
        c.execute("INSERT OR IGNORE INTO setari(cheie, valoare) VALUES('versiune', '0')")
        c.execute("INSERT OR IGNORE INTO setari(cheie, valoare) VALUES('decalaj_zile', '0')")
    if val("SELECT COUNT(*) FROM utilizatori", implicit=0) == 0 and config.DATE_DEMO:
        from . import seed
        with o_tranzactie():
            seed.populeaza()


TABELE = ("utilizatori", "sesiuni", "portofoliu", "lucrari", "invitatii", "oferte", "plati", "extra",
          "mesaje", "citit", "feedback", "rapoarte", "blocari", "notificari", "sondaj", "setari")


def reseteaza():
    """Șterge tot și pune la loc datele demo (buton în panoul de admin)."""
    with conn() as c:
        for t in TABELE:
            if t not in ("setari", "sondaj"):     # răspunsurile oamenilor rămân și după resetarea demo-ului
                c.execute(f"DELETE FROM {t}")
        c.execute("UPDATE setari SET valoare = '0' WHERE cheie = 'decalaj_zile'")
    _dupa_scriere()
    from . import seed
    with o_tranzactie():
        seed.populeaza()
    ex("UPDATE setari SET valoare = valoare WHERE cheie = 'decalaj_zile'")
