"""Setările aplicației: căi, constante, meserii, cartiere.

Tot ce se schimbă des (comision, spor de urgență, lista de meserii) stă aici,
ca să nu căutați prin cod.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

NUME_APP = "SKILLIO"
SLOGAN = "Find skills. Build trust."

# --- fișiere ---------------------------------------------------------------
DATA_DIR = ROOT / "data"
UPLOADS = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "skillio.db"

# --- reguli de business ------------------------------------------------------
COMISION = 0.10            # platforma reține 10% din partea meșterului
TAXA_PROTECTIE = 0.05      # clientul plătește 5% în plus: finanțează mediatorii umani (ca o asigurare)
TAXA_DEPLASARE = 40        # lei din ofertă garantați meșterului dacă clientul refuză prețul la fața locului
FEREASTRA_DISPUTA_ORE = 24 # după confirmare, banii mai stau blocați atâtea ore (oricine poate deschide dispută)
SOS_PRET = 45              # apel video de urgență cu un meșter
SOS_MESTER = 35            # din care merg la meșter
SPOR_URGENT = 0.15         # lucrările urgente costă cu 15% mai mult
SLOTURI = [8, 10, 12, 14, 16]   # ora de început a fiecărui interval de 2 ore
DURATA_SLOT = 2
ZILE_CALENDAR = 7          # câte zile în față se pot face programări
RAZA_SOSIRE_M = 200        # cât de aproape de adresă trebuie să fie meșterul
TOLERANTA_PUNCTUAL_MIN = 15
MAX_INVITATI = 6           # câți meșteri primesc o solicitare
# procentele ca text, pentru ecrane (ex. „15%”). Se calculează singure din valorile de mai sus.
PCT_URGENT = f"{round(SPOR_URGENT * 100)}%"
PCT_COMISION = f"{round(COMISION * 100)}%"
PCT_PROTECTIE = f"{round(TAXA_PROTECTIE * 100)}%"

# --- chei API (din fișierul .env) -------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip()
NOKIA_API_KEY = os.getenv("NOKIA_API_KEY", "").strip()
NOKIA_RAPIDAPI_HOST = os.getenv("NOKIA_RAPIDAPI_HOST", "").strip()
# În sandbox-ul Nokia merg doar numere de test (ex. +99999991000). Dacă e setat,
# toate apelurile către rețea folosesc acest număr în locul celui din cont.
NOKIA_NUMAR_TEST = os.getenv("NOKIA_NUMAR_TEST", "").strip()
GEOCODARE = os.getenv("GEOCODARE", "1").strip() == "1"
MOD_PREZENTARE = os.getenv("MOD_PREZENTARE", "1").strip() == "1"


def _env(nume, implicit=""):
    return os.getenv(nume, implicit).strip()


# --- producție (fiecare parte e opțională: fără cheie, aplicația merge ca înainte) ---------------
# 1. Login: Auth0 se configurează în .streamlit/secrets.toml (vezi secrets.toml.example).
#    DEMO_LOGIN=1 lasă și intrarea demo cu numărul de telefon (pentru prezentare). În producție: 0.
DEMO_LOGIN = _env("DEMO_LOGIN", "1") == "1"
ADMIN_EMAILS = {e.strip().lower() for e in _env("ADMIN_EMAILS").split(",") if e.strip()}
SESIUNE_ZILE = int(_env("SESIUNE_ZILE", "30") or 30)
# 2. Baza de date: gol = SQLite local; altfel PostgreSQL (Tiger Data), ex. postgresql://user:parola@host:port/db
DATABASE_URL = _env("DATABASE_URL")
DATE_DEMO = _env("DATE_DEMO", "1") == "1"      # la o bază goală, pune datele demo
# 3. Poze în cloud (Vultr Object Storage sau orice S3)
S3_ENDPOINT = _env("S3_ENDPOINT")              # ex. https://ams1.vultrobjects.com
S3_BUCKET = _env("S3_BUCKET")
S3_ACCESS_KEY = _env("S3_ACCESS_KEY")
S3_SECRET_KEY = _env("S3_SECRET_KEY")
S3_REGION = _env("S3_REGION", "us-east-1")
# 4. Notificări externe
SMTP_HOST = _env("SMTP_HOST")                  # ex. smtp.gmail.com
SMTP_PORT = int(_env("SMTP_PORT", "587") or 587)
SMTP_USER = _env("SMTP_USER")
SMTP_PAROLA = _env("SMTP_PAROLA")
SMTP_FROM = _env("SMTP_FROM") or SMTP_USER
TWILIO_SID = _env("TWILIO_SID")
TWILIO_TOKEN = _env("TWILIO_TOKEN")
TWILIO_FROM = _env("TWILIO_FROM")              # numărul Twilio, ex. +1555...
URL_APP = _env("URL_APP", "http://localhost:8501")
# 5. Solana (devnet): plata blocată on-chain. Gol = plată simulată.
SOLANA_SECRET_KEY = _env("SOLANA_SECRET_KEY")  # cheia privată a portofelului platformei (base58 sau [..] JSON)
SOLANA_RPC = _env("SOLANA_RPC", "https://api.devnet.solana.com")
SOLANA_CLUSTER = _env("SOLANA_CLUSTER", "devnet")
SOL_PER_LEU = float(_env("SOL_PER_LEU", "0.0001") or 0.0001)
# 6. ElevenLabs: citește cu voce diagnosticul și ofertele. Gol = vocea browserului.
ELEVENLABS_API_KEY = _env("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = _env("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_MODEL = _env("ELEVENLABS_MODEL", "eleven_multilingual_v2")   # adresa publică, pusă în linkurile din email/SMS

# --- meserii -----------------------------------------------------------------
# pret = interval orientativ (lei), folosit când Gemini nu e disponibil
MESERII = {
    "instalator": {
        "scurt": "Instalator", "nume": "Instalator", "icon": "plumbing", "emoji": "", "pret": (120, 300), "durata": 60,
        "cuvinte": ["apă", "apa", "țeav", "teav", "chiuvet", "robinet", "curge", "wc", "toalet",
                    "scurger", "sifon", "infundat", "înfundat", "baterie", "duș", "dus", "cadă", "cada", "inunda"],
        "materiale": ["racord flexibil", "garnituri", "bandă teflon"],
        "sfat": "Închide robinetul de sub chiuvetă sau robinetul general și pune un prosop.",
    },
    "electrician": {
        "scurt": "Electrician", "nume": "Electrician", "icon": "bolt", "emoji": "", "pret": (100, 350), "durata": 60,
        "cuvinte": ["priz", "siguranț", "sigurant", "curent", "lumin", "bec", "tablou", "întrerup", "intrerup",
                    "scântei", "scantei", "cablu", "electric", "lustr"],
        "materiale": ["priză / întrerupător", "siguranță automată", "cablu"],
        "sfat": "Oprește siguranța circuitului respectiv din tablou și nu atinge priza.",
    },
    "termice": {
        "scurt": "Centrale", "nume": "Centrale și calorifere", "icon": "mode_heat", "emoji": "", "pret": (150, 450), "durata": 90,
        "cuvinte": ["central", "calorifer", "căldur", "caldur", "încălzire", "incalzire", "boiler", "termostat", "presiune"],
        "materiale": ["robinet calorifer", "aerisitor", "vas de expansiune"],
        "sfat": "Verifică presiunea de pe manometru și nu demonta nimic la centrală.",
    },
    "tamplar": {
        "scurt": "Tâmplar", "nume": "Tâmplar", "icon": "carpenter", "emoji": "", "pret": (100, 400), "durata": 90,
        "cuvinte": ["ușă", "usa", "usă", "fereastr", "geam", "dulap", "balama", "sertar", "mobil", "parchet", "raft", "pervaz"],
        "materiale": ["balamale", "șuruburi", "adeziv lemn"],
        "sfat": "Nu forța piesa blocată, ca să nu se rupă balamalele.",
    },
    "zugrav": {
        "scurt": "Zugrav", "nume": "Zugrav", "icon": "format_paint", "emoji": "", "pret": (200, 900), "durata": 240,
        "cuvinte": ["zugrăv", "zugrav", "vopsea", "vopsit", "perete", "pereți", "tavan", "mucegai", "glet", "fisur", "tencuial", "igrasie"],
        "materiale": ["vopsea lavabilă", "glet", "amorsă"],
        "sfat": "Aerisește camera; dacă e mucegai, nu-l freca pe uscat.",
    },
    "lacatus": {
        "scurt": "Lăcătuș", "nume": "Lăcătuș", "icon": "key", "emoji": "", "pret": (100, 350), "durata": 45,
        "cuvinte": ["yal", "ial", "încuietoare", "incuietoare", "cheie", "cheia", "blocat afar", "butuc", "lacăt", "lacat", "broasc"],
        "materiale": ["butuc yală", "broască"],
        "sfat": "Nu forța cheia în yală, se poate rupe înăuntru.",
    },
    "electrocasnice": {
        "scurt": "Aparate", "nume": "Reparații electrocasnice", "icon": "kitchen", "emoji": "", "pret": (120, 400), "durata": 75,
        "cuvinte": ["mașină de spălat", "masina de spalat", "frigider", "cuptor", "aragaz", "hotă", "hota",
                    "mașina de vase", "masina de vase", "uscător", "uscator", "microunde", "congelator"],
        "materiale": ["furtun evacuare", "garnitură ușă", "pompă"],
        "sfat": "Scoate aparatul din priză și închide robinetul de apă al aparatului.",
    },
    "universal": {
        "scurt": "Diverse", "nume": "Meșter universal", "icon": "handyman", "emoji": "", "pret": (80, 300), "durata": 60,
        "cuvinte": ["montaj", "montat", "montez", "tablou", "poliț", "polit", "galerie", "televizor", "suport", "asambl"],
        "materiale": ["dibluri", "șuruburi"],
        "sfat": "Pregătește locul de lucru și eliberează accesul.",
    },
}

# --- cartiere din Timișoara (centru aproximativ) -----------------------------
ORAS = "Timișoara"
CENTRU_ORAS = (45.7537, 21.2257)
CARTIERE = {
    "Cetate (Centru)": (45.7576, 21.2290),
    "Fabric": (45.7605, 21.2520),
    "Iosefin": (45.7455, 21.2130),
    "Elisabetin": (45.7440, 21.2260),
    "Complexul Studențesc": (45.7475, 21.2400),
    "Circumvalațiunii": (45.7660, 21.2110),
    "Mehala": (45.7650, 21.1950),
    "Blașcovici": (45.7625, 21.2030),
    "Aradului": (45.7800, 21.2250),
    "Lipovei": (45.7760, 21.2420),
    "Torontalului": (45.7790, 21.2060),
    "Dâmbovița": (45.7400, 21.1950),
    "Calea Șagului": (45.7270, 21.2050),
    "Girocului": (45.7300, 21.2400),
    "Soarelui": (45.7290, 21.2500),
    "Freidorf": (45.7280, 21.1770),
    "Plopi": (45.7500, 21.2700),
    "Ghiroda Nouă": (45.7640, 21.2740),
}

MOTIVE_RAPORT_CLIENT = [
    "Meșterul nu a venit",
    "Lucrare de proastă calitate",
    "A cerut bani în afara aplicației",
    "Comportament nepotrivit",
    "Altceva",
]
MOTIVE_RAPORT_MESTER = [
    "Clientul nu a fost acasă",
    "Refuză să confirme lucrarea fără motiv",
    "Solicitare falsă sau poză înșelătoare",
    "Comportament nepotrivit",
    "Altceva",
]

CRITERII_RECENZIE = [
    ("calitate", "Calitatea lucrării"),
    ("punctualitate", "Punctualitate"),
    ("comunicare", "Comunicare"),
    ("pret", "Respectarea prețului"),
    ("profesionalism", "Profesionalism"),
]
