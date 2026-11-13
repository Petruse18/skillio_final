# Ghidul codului SKILLIO (pentru începători)

Ghidul ăsta te duce de la „nu știu nimic despre cod” la „pot schimba singur aplicația”.
Citește-l o dată de sus până jos (20 de minute), apoi fă exercițiile de la final, cu VS Code deschis.

> Sfat: în VS Code, `Ctrl+P` deschide repede orice fișier după nume, iar `Ctrl+Shift+F` caută un text în tot proiectul.
> Ca să găsești locurile din exerciții, caută textul dat, nu numărul liniei, pentru că numerele se schimbă.

---

## 1. Pe scurt: cum e construită aplicația

SKILLIO are trei bucăți:

| Bucată | Ce e | Unde |
|---|---|---|
| **Interfața** (ce vezi pe telefon) | Python cu biblioteca **Streamlit**. Fiecare buton, câmp sau card e o linie de Python. | `app.py`, `views/`, `ui/` |
| **Logica** (regulile aplicației) | Funcții Python obișnuite: „creează o solicitare”, „trimite ofertă”, „plătește”, „eliberează banii”. | `core/` |
| **Datele** | O bază de date **SQLite**: un singur fișier pe disc. | `data/skillio.db` |

În plus, `services/` vorbește cu lumea de afară: Gemini (AI), Nokia (rețeaua) și harta.

Regula de aur: **ecranele nu umblă direct în baza de date.** Un ecran cheamă o funcție din `core/logica.py`,
iar funcția aceea citește sau scrie în bază. Așa, dacă vrei să schimbi o regulă (de exemplu comisionul),
o schimbi într-un singur loc.

```
 telefon (browser)
      │  click pe un buton
      ▼
 views/*.py   ── cheamă ──▶  core/logica.py  ── scrie/citește ──▶  data/skillio.db
      ▲                          │
      │                          └── cheamă ──▶ services/ (Gemini, Nokia, hartă)
      └── afișează rezultatul
```

---

## 2. Cum funcționează Streamlit (cel mai important lucru de înțeles)

Streamlit e diferit de un site obișnuit. Ideea e una singură:

**La fiecare click, Streamlit rulează din nou tot scriptul `app.py`, de sus până jos.**

Un exemplu minuscul:

```python
import streamlit as st

nume = st.text_input("Cum te cheamă?")
if st.button("Salută"):
    st.write(f"Salut, {nume}!")
```

- `st.text_input(...)` desenează un câmp **și** îți dă înapoi ce a scris omul în el.
- `st.button(...)` desenează un buton **și** întoarce `True` doar în rularea de imediat după click.
- Când apeși butonul, scriptul rulează iar de la zero. De data asta `st.button` întoarce `True`, deci intră în `if`.

Ce trebuie să mai știi:

- **`st.session_state`** e un dicționar care **supraviețuiește** între rulări. Acolo ținem lucruri temporare,
  de exemplu diagnosticul AI cât timp clientul completează formularul (`st.session_state["sol_diag"]`).
- **`key="..."`**: fiecare buton sau câmp are o cheie unică. Dacă două butoane au aceeași cheie, Streamlit dă eroare.
  Noi folosim cheia și pentru stil: un container cu cheie care începe cu `card` arată ca un card
  (regulile sunt în `ui/streamlit.css`).
- **Adresa paginii** ține minte unde ești: `?s=...&p=lucrare&id=12` înseamnă „sesiunea utilizatorului”,
  „pagina lucrare”, „lucrarea numărul 12”. Funcția `c.go("lucrare", 12)` din `ui/comp.py` schimbă adresa,
  iar `app.py` alege ecranul potrivit.
- **`st.rerun()`** forțează o rulare nouă imediat, de exemplu după ce am salvat ceva și vrem să se vadă.

### Cum se sincronizează cele două telefoane

Fiecare telefon din modul de prezentare e o fereastră separată. Când cineva schimbă ceva în bază,
`core/db.py` (funcția `ex`) crește un număr numit `versiune`. În `app.py`, funcția `_urmareste` verifică numărul
la fiecare 2 secunde, iar dacă s-a schimbat, reîncarcă ecranul. De-asta, ce face Ana apare la Ionel în 1-2 secunde.

---

## 3. Harta fișierelor

```
skillio/
├── GHID.md              ← ghidul ăsta
├── app.py               ← PUNCTUL DE PORNIRE. Alege ecranul, desenează bara de jos, sincronizarea.
├── porneste.bat         ← dublu-click: instalează și pornește totul
├── requirements.txt     ← lista bibliotecilor Python
├── .env                 ← cheile API (NU se urcă pe GitHub). Model: .env.example
├── .streamlit/config.toml  ← setări Streamlit (culoarea de bază, portul etc.)
│
├── core/                ← „creierul”, fără nimic vizual
│   ├── config.py        ← REGULILE ȘI LISTELE: comision, spor urgent, ore, meserii, cartiere. Începe de aici!
│   ├── logica.py        ← toate acțiunile: creează solicitare, ofertă, plată, sosire, confirmare, recenzie, chat...
│   ├── db.py            ← baza de date: tabelele (SCHEMA) și funcțiile q / q1 / ex
│   ├── trust.py         ← calculul Trust Score (0-100)
│   ├── timp.py          ← ceasul aplicației (se poate „da înainte” pentru demo) și formatarea datelor în română
│   └── seed.py          ← datele demo (Ana, Ionel, ceilalți meșteri, lucrări vechi)
│
├── services/            ← legătura cu lumea de afară
│   ├── ai.py            ← Gemini: din text + poză → meserie, preț, urgență. Fără cheie, folosește cuvinte cheie.
│   ├── nokia.py         ← Nokia: număr verificat, SIM schimbat, e meșterul la adresă? Fără cheie: simulat.
│   ├── geo.py           ← distanțe în km și coordonatele unei adrese
│   ├── autentificare.py ← login securizat prin Auth0
│   ├── stocare.py       ← unde stau pozele: cloud (Vultr / S3) sau local
│   ├── mesaje_externe.py ← notificări pe email și SMS
│   ├── solana.py        ← plata blocată pe blockchain (Solana devnet). Fără cheie: simulat.
│   └── voce.py          ← ElevenLabs: butonul „Ascultă”. Fără cheie: vocea browserului.
│
├── scripts/             ← unelte: migrare în PostgreSQL, backup, poze în cloud, portofelul Solana
│
├── ui/                  ← piese vizuale refolosite
│   ├── comp.py          ← „cărămizi”: avatar, stele, insigne, carduri, navigare (go, inapoi)
│   ├── harta.py         ← hărțile (folium)
│   ├── tokens.css       ← CULORILE, fonturile, colțurile rotunjite
│   ├── components.css   ← stilul claselor sk-* (carduri, insigne...)
│   └── streamlit.css    ← adaptează Streamlit să arate ca un telefon
│
└── views/               ← ECRANELE
    ├── client.py        ← Acasă client, Caută, Cere (solicitare nouă), Lucrările mele
    ├── mester.py        ← Acasă meșter, Solicitări pe hartă, Calendar
    ├── lucrare.py       ← ecranul unei lucrări, cu toți pașii (ofertă → plată → sosire → confirmare → recenzie)
    ├── comun.py         ← ce au amândoi: intrare, ghid, chat, notificări, profil meșter, cont
    ├── admin.py         ← panoul intern: dispute, rapoarte, statistici, controale demo
    ├── comunitate.py    ← Living Labs: chestionarul „Spune-ne părerea” și pagina „Ce e nou”
    └── prezentare.py    ← modul cu două telefoane (?mod=prezentare)
```

**Unde caut când vreau să schimb...**

| Vreau să schimb | Deschid |
|---|---|
| un text de pe un ecran | fișierul ecranului din `views/` (caută textul cu `Ctrl+Shift+F`) |
| o culoare | `ui/tokens.css` |
| comisionul, sporul de urgență, orele din calendar | `core/config.py` |
| lista de meserii sau de cartiere | `core/config.py` |
| ce se întâmplă când apeși un buton | butonul e în `views/`, acțiunea e o funcție din `core/logica.py` |
| cum se calculează scorul | `core/trust.py` |
| ce îi cerem lui Gemini | `services/ai.py` (variabila `PROMPT`) |
| o versiune nouă în „Ce e nou” | `views/comunitate.py` (lista `NOUTATI`) |
| cât SOL înseamnă un leu | `.env` → `SOL_PER_LEU` |

---

## 4. Drumul unei solicitări prin cod

Urmează povestea din demo și vezi ce funcție lucrează la fiecare pas. Deschide fișierele în paralel și caută numele funcțiilor.

1. **Ana apasă „Cere”.** `app.py` vede `p=solicitare` și cheamă `client.solicitare(u)` din `views/client.py`.
2. **Ana scrie problema și apasă „Analizează”.** Ecranul cheamă `ai.diagnosticheaza(text, poza)` din `services/ai.py`.
   Răspunsul (meserie, preț, urgență) se ține în `st.session_state["sol_diag"]`.
3. **Ana completează detaliile și apasă „Trimite solicitarea”.** Se cheamă `logica.creeaza_lucrare(...)`. Funcția:
   - salvează lucrarea în tabelul `lucrari` cu statusul `deschisa`;
   - caută meșterii potriviți (`logica.mesteri(...)`), pe cei mai buni 6, și îi scrie în tabelul `invitatii`;
   - trimite notificări (`logica.notifica`).
4. **Ionel vede solicitarea.** `mester.acasa(u)` cheamă `logica.solicitari_pentru_mester(...)`, care le pune pe cele urgente primele.
5. **Ionel trimite oferta.** În `views/lucrare.py`, partea `_mester`, formularul cheamă `logica.trimite_oferta(...)`.
   Prețul total include +15% dacă e urgentă (`logica.total_cu_urgenta`).
6. **Ana acceptă.** `logica.accepta_oferta(...)` schimbă statusul în `acceptata`. Apoi `logica.confirma_ora(...)` îl trece în `de_plata`.
7. **Ana plătește.** `logica.plateste(...)` scrie o plată cu statusul `blocat` în tabelul `plati`. Lucrarea devine `programata`.
8. **Ionel apasă „Am ajuns”.** `logica.am_ajuns(...)` întreabă Nokia (`nokia.e_la_adresa`) dacă telefonul lui e lângă adresă. Statusul devine `sosit`.
9. **Ionel apasă „Lucrare gata”**, adică `logica.lucrare_gata(...)`, și statusul devine `gata`.
10. **Ana confirmă.** `logica.confirma_lucrare(...)` trece plățile din `blocat` în `eliberat`, scade comisionul
    (`config.COMISION`) și programează feedback-ul la 1 zi, 1 săptămână și 1 lună (`programeaza_feedback`).
11. **Recenzia** (`logica.da_recenzie`) și **feedback-ul în timp** (`logica.raspunde_durabilitate`) intră în
    `trust.calculeaza(...)`, care dă scorul nou al lui Ionel.

Statusurile, în ordine: `deschisa → acceptata → de_plata → programata → sosit → gata → finalizata`
(plus `disputa` și `anulata`). Le găsești în `core/logica.py`, în dicționarul `STATUS`.

---

## 5. Unde stau datele

Pe laptop, totul e în fișierul `data/skillio.db`, creat automat la prima pornire, cu date demo din `core/seed.py`.
Dacă în `.env` există `DATABASE_URL`, aceleași tabele stau în PostgreSQL (Tiger Data). Codul e același, vezi PRODUCTIE.md.

Tabelele principale (definite în `core/db.py`, în `SCHEMA`):

| Tabel | Ce ține |
|---|---|
| `utilizatori` | clienți, meșteri, admin: nume, telefon, cartier, meserii, tarif, disponibil... |
| `lucrari` | fiecare solicitare: titlu, descriere, adresă, urgent, status, meșterul ales, ora |
| `invitatii` | ce meșteri au primit fiecare solicitare |
| `oferte` | ofertele meșterilor: preț, total, ora propusă |
| `plati` | banii: `blocat`, `eliberat` sau `returnat`, plus comisionul |
| `mesaje` | chatul fiecărei lucrări |
| `feedback` | recenzia finală și întrebările de la 1 zi, 1 săptămână, 1 lună |
| `rapoarte` | reclamațiile, pe care adminul le confirmă sau le respinge |
| `notificari`, `blocari`, `portofoliu`, `setari` | restul |

Pentru citire și scriere folosim trei funcții din `core/db.py`:

```python
db.q("SELECT * FROM lucrari WHERE client_id = ?", (5,))   # o listă de rânduri
db.q1("SELECT * FROM utilizatori WHERE id = ?", (5,))     # un singur rând
db.ex("UPDATE lucrari SET status = 'gata' WHERE id = ?", (12,))  # scrie (și anunță telefoanele)
```

**Resetare:** butonul „Resetează demo” din modul de prezentare (sau din panoul de admin) readuce datele demo.
Dacă schimbi tabelele (`SCHEMA`), oprește aplicația, șterge folderul `data` și pornește din nou.

Vrei să te uiți în bază? Instalează în VS Code extensia **SQLite Viewer** și dă click pe `data/skillio.db`.

---

## 6. Cum lucrezi în fiecare zi

1. Pornește aplicația cu `porneste.bat` și lasă fereastra neagră deschisă.
2. Deschide folderul `skillio` în VS Code (File → Open Folder).
3. Schimbi ceva și salvezi cu `Ctrl+S`.
4. Te uiți în browser. Aplicația se reîncarcă singură la salvare (`runOnSave` e pornit). Dacă nu vezi schimbarea,
   apasă `R` pe pagină sau reîncarcă pagina (F5).
5. **Dacă ai schimbat `core/config.py`, `.env` sau baza de date**, oprește fereastra neagră (`Ctrl+C`, apoi închide-o)
   și pornește din nou `porneste.bat`. Uneori Streamlit nu reîncarcă singur aceste fișiere.
6. Când merge, salvezi pe GitHub: în VS Code, iconița **Source Control** (a treia din stânga), scrii un mesaj
   („Am schimbat culoarea”), **Commit**, apoi **Sync / Push**.

> Lucrați în echipă? Înainte să începi, apasă **Pull** (sau Sync) ca să iei ce au schimbat colegii.
> Doi oameni care schimbă aceleași rânduri în același timp creează conflicte, așa că împărțiți-vă pe fișiere.

---

## 7. Exerciții practice

Fă-le în ordine. Fiecare durează 5-10 minute. După fiecare, verifică în browser.

### Exercițiul 1: schimbă un text

**Scop:** să vezi legătura dintre cod și ecran.

1. `Ctrl+Shift+F` și caută `Ce reparăm azi?`. Îl găsești în `views/client.py`, în funcția `acasa`.
2. Înlocuiește-l cu `Cu ce te putem ajuta azi?`. Ai grijă să nu ștergi ghilimelele `"` din jurul textului.
3. Salvează (`Ctrl+S`) și uită-te pe telefonul Anei. Sub „Salut, Ana!” apare textul nou.

**Bonus:** în `core/config.py`, schimbă `SLOGAN` și repornește aplicația. Sloganul apare sus, în modul de prezentare.

### Exercițiul 2: schimbă culoarea principală

**Scop:** să înțelegi că toate culorile vin dintr-un singur loc.

1. Deschide `ui/tokens.css`. Sus de tot vezi:
   ```css
   --sk-primary:#127a4e;        /* butoane principale, selecție, „în regulă” */
   --sk-primary-press:#0d5f3c;  /* buton apăsat / hover */
   --sk-primary-soft:#e3f4ea;   /* butoane secundare, avatare, fundaluri ușoare */
   ```
2. Pune de exemplu un albastru: `#1f5fbf`, `#174a96` (apăsat) și `#e4edfa` (deschis).
3. Deschide `.streamlit/config.toml` și schimbă și acolo `primaryColor = "#1f5fbf"`, pentru comutatoare și bife.
4. Salvează și repornește aplicația. Toate butoanele verzi devin albastre.
5. Dacă nu-ți place, pune valorile vechi înapoi. Sau, în VS Code, Source Control → click dreapta pe fișier → **Discard Changes**.

> Culorile au roluri: portocaliu doar pentru Urgent, albastru doar pentru Nokia, galben-chihlimbar pentru banii blocați și stele.
> Dacă schimbi culoarea principală în albastru, se amestecă cu Nokia. De-asta e verde.

### Exercițiul 3: adaugă o meserie nouă (Grădinar)

**Scop:** să vezi cum o listă din `config.py` apare peste tot în aplicație.

1. Deschide `core/config.py` și găsește `MESERII = {`.
2. Înainte de ultima acoladă `}` a dicționarului (după blocul `"universal": {...},`), adaugă:
   ```python
       "gradinar": {
           "scurt": "Grădinar", "nume": "Grădinar", "icon": "yard", "emoji": "🌿", "pret": (100, 400), "durata": 120,
           "cuvinte": ["grădin", "gradin", "gazon", "iarb", "tuns", "gard viu", "copac", "pom", "irigat"],
           "materiale": ["saci de gunoi", "îngrășământ"],
           "sfat": "Strânge jucăriile și obiectele de pe gazon înainte să vină grădinarul.",
       },
   ```
   Fiecare linie spune ceva: `scurt` e numele de pe buton, `emoji` iconița, `pret` intervalul orientativ în lei,
   `cuvinte` sunt cuvintele după care asistentul (fără Gemini) recunoaște meseria.
3. Repornește aplicația. Pe ecranul Anei apare a noua categorie, **Grădinar**.
4. Încearcă asistentul: **Cere** → scrie `Trebuie tuns gazonul și gardul viu` → Analizează. Ar trebui să aleagă Grădinar.
5. Nu are încă niciun meșter. Intră ca Ionel → **Cont** → la „Meserii” adaugă și Grădinar → salvează.
   Acum solicitările de grădinărit ajung și la el.

### Exercițiul 4: adaugă un câmp nou în formular (Etaj și interfon)

**Scop:** să adaugi un câmp și să-i folosești valoarea.

1. Deschide `views/client.py` și caută `adresa = st.text_input("Adresa"`.
2. Sub linia aceea adaugă:
   ```python
       etaj = st.text_input("Etaj și interfon (opțional)", placeholder="ex. et. 3, ap. 12, interfon 12", key="sol_etaj")
   ```
   Ai grijă la spațiile de la începutul rândului: trebuie să fie exact ca la rândul de deasupra.
   În Python, spațiile arată ce e în interiorul funcției.
3. Acum folosim valoarea: o lipim la descriere când se trimite solicitarea. Caută `lid, n = logica.creeaza_lucrare(`
   și, chiar **deasupra** acelui rând, adaugă (aliniat cu `lid`):
   ```python
                   if etaj.strip():
                       descriere = descriere + f"\n\nEtaj / interfon: {etaj.strip()}"
   ```
4. Salvează. Fă o solicitare nouă ca Ana, cu câmpul completat. Apoi intră ca Ionel și deschide solicitarea:
   la descriere apare și etajul.

**Bonus (mai greu):** ca să salvezi etajul separat în bază, ai nevoie de o coloană nouă `etaj` în tabelul `lucrari`
(`core/db.py`, în `SCHEMA`), de un parametru nou în `logica.creeaza_lucrare` și de ștergerea folderului `data`.
Încearcă după ce te simți sigur pe primele patru.

### Exercițiul 5 (rapid): schimbă o regulă de business

În `core/config.py`, schimbă `COMISION = 0.10` în `COMISION = 0.08` și `SPOR_URGENT = 0.15` în `0.20`.
Repornește și refă demo-ul: ofertele urgente cresc cu 20%, iar la confirmare meșterul primește 92%.
Textele de pe ecran se actualizează singure, pentru că citesc valorile din `config`. Pune valorile înapoi după.

---

## 8. Când ceva se strică

| Ce vezi | Ce înseamnă | Ce faci |
|---|---|---|
| `localhost refused to connect` | serverul nu rulează | pornește `porneste.bat` și lasă fereastra deschisă |
| Un dreptunghi roșu cu `SyntaxError` | ai greșit scrierea: o paranteză, o ghilimea sau o virgulă lipsă | uită-te la rândul indicat. VS Code subliniază cu roșu greșeala |
| `IndentationError` | spațiile de la început nu se potrivesc | aliniază rândul cu cele de deasupra |
| `NameError: name 'x' is not defined` | folosești o variabilă scrisă greșit sau nedefinită | verifică numele (contează literele mari și mici) |
| `DuplicateWidgetID` / `key already exists` | două butoane au aceeași `key` | schimbă `key="..."` la unul dintre ele |
| `KeyError: 'gradinar'` | un cuvânt cheie lipsește dintr-un dicționar | verifică că ai scris peste tot exact la fel |
| `no such column` | ai schimbat tabelele, dar baza e veche | oprește aplicația, șterge `data`, pornește din nou |
| Am stricat tot și nu mai știu ce-am schimbat | – | Source Control → vezi fișierele modificate → **Discard Changes** pe ele |

Când nu știi ce înseamnă o eroare, copiază textul roșu întreg și trimite-l. E cel mai rapid mod de a o rezolva.
