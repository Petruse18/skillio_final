# SKILLIO

**Find skills. Build trust.** Aplicație de telefon care leagă clienții de meșteri verificați din Timișoara.
Proiect UniHack 2026, track Connected Communities (Nokia).

Clientul descrie problema (text + poză), asistentul AI (Gemini) spune ce meșter trebuie și cât ar costa,
meșterii din zonă trimit oferte, clientul alege una, se stabilește ora, clientul plătește, iar banii stau
blocați în SKILLIO până când clientul confirmă că lucrarea e în regulă. Rețeaua Nokia verifică numărul,
SIM-ul și sosirea meșterului la adresă. Feedback-ul după o zi, o săptămână și o lună construiește Trust Score-ul.

## Pornire rapidă (Windows)

Ai nevoie de Python 3.10 sau mai nou.

Varianta simplă: dublu-click pe `porneste.bat`. Prima dată instalează pachetele (durează 1-2 minute),
apoi pornește aplicația și deschide modul de prezentare în browser.

Varianta manuală, din terminalul VS Code:

```bash
python -m venv .venv
.venv\Scripts\activate          # pe Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Apoi deschide:

| Adresa | Ce vezi |
|---|---|
| http://localhost:8501 | aplicația, cu ecranul de intrare |
| http://localhost:8501/?mod=prezentare | **modul de prezentare**: două telefoane unul lângă altul (Ana, client, și Ionel, meșter) plus scenariul demo și butoanele de timp |

La prima pornire aplicația creează baza de date `data/skillio.db` cu date demo (durează câteva secunde).

## Producție (login securizat, PostgreSQL, poze în cloud, server cu HTTPS, notificări)

Totul e descris pas cu pas în [PRODUCTIE.md](PRODUCTIE.md). Fiecare parte pornește doar când îi pui cheile,
așa că fără ele aplicația rămâne exact ca în demo.

## Conturi demo

Pe ecranul de intrare sunt butoane pentru fiecare. Nu există parole: intrarea se face cu numărul de telefon,
verificat de rețea.

| Cont | Telefon | Rol |
|---|---|---|
| Ana Popescu | +40722000001 | client, Elisabetin |
| Ionel Mureșan | +40722000101 | instalator și centrale, Fabric |
| Admin | +40700000000 | panou intern: dispute, rapoarte, statistici, controale demo |

## Cheile API

Copiază `.env.example` ca `.env` și completează cheile. Fișierul `.env` nu se urcă pe GitHub.

- `GEMINI_API_KEY`: din Google AI Studio. Fără cheie, diagnosticul merge pe reguli simple (cuvinte cheie).
- `NOKIA_API_KEY` și `NOKIA_RAPIDAPI_HOST`: din consola Nokia Network as Code.
- `SOLANA_SECRET_KEY`: portofelul platformei pe Solana devnet (`python -m scripts.solana_portofel`). Fără ea, plata e simulată.
- `ELEVENLABS_API_KEY`: vocea pentru butonul „Ascultă”. Fără ea, citește vocea browserului.
- `NOKIA_NUMAR_TEST`: în sandbox merg doar numerele de test (ex. `+99999991000`). Dacă e completat, toate
  apelurile către rețea folosesc acest număr.

Fără chei aplicația merge complet, cu rezultate simulate. Pe ecran scrie mereu „live” sau „simulat”, ca să fie
clar de unde vine fiecare verificare. După ce schimbi `.env`, repornește `streamlit run app.py`.

## Scenariul demo (în modul de prezentare)

1. Ana apasă **Cere**, descrie „Curge apă de sub chiuvetă” și adaugă o poză. AI-ul alege instalatorul.
2. Bifează **Urgent (+15%)**. Pe telefonul lui Ionel solicitarea apare prima, portocalie.
3. Ionel deschide solicitarea și trimite o ofertă cu preț și oră din calendarul lui.
4. Ana compară ofertele (Trust Score, insigne Nokia, preț) și acceptă.
5. Ana confirmă ora și plătește. Banii apar „blocați” în SKILLIO.
6. Ionel apasă **Am ajuns**. Rețeaua Nokia confirmă că e la adresă (cu „Ionel e departe de adresă” vezi cazul de eșec).
7. Ionel marchează lucrarea gata, Ana bifează că totul e în regulă și banii ajung la Ionel, minus 10% comision.
   Cu Solana pornit, cardul **Plată verificabilă pe blockchain** arată tranzacțiile pe Solana Explorer.
8. Ana lasă recenzia pe 5 criterii. Cu butoanele **+1 zi / +6 zile / +23 zile** apar întrebările de durabilitate.

Ce faci pe un telefon apare pe celălalt în 1-2 secunde. **Resetează demo** readuce datele la starea inițială.

## Pe telefon

- În Chrome pe laptop: F12, apoi iconița de telefon (Toggle device toolbar), alege un model de telefon.
- Pe un telefon real din aceeași rețea Wi-Fi: deschide adresa „Network URL” afișată în terminal.

## Notă

Hărțile (folium) și fontul se încarcă de pe internet, deci la prezentare ai nevoie de conexiune.
Dacă nu e internet, restul aplicației merge, doar hărțile rămân goale.

Ești la început cu codul? Citește [GHID.md](GHID.md): explicații pas cu pas și exerciții.

## Structura

```
app.py              intrarea în aplicație, navigarea de jos, sincronizarea între telefoane
core/config.py      reguli de business (comision, spor urgent, sloturi), meserii, cartiere
core/db.py          baza de date SQLite
core/logica.py      tot fluxul: solicitări, oferte, programare, plată blocată, sosire, confirmare, recenzii, rapoarte, chat
core/trust.py       calculul Trust Score (0-100) din 7 factori
core/seed.py        datele demo
core/timp.py        ceasul aplicației (se poate da înainte pentru demo)
services/ai.py      Gemini: diagnostic din text și poză
services/nokia.py   Nokia Network as Code: număr, SIM swap, locație
services/geo.py     distanțe și coordonate
services/autentificare.py   login Auth0
services/stocare.py         poze în cloud (S3 / Vultr) sau local
services/mesaje_externe.py  notificări pe email și SMS
services/solana.py          plata blocată pe Solana devnet (blocare, 90/10, returnare, pașaport)
services/voce.py            ElevenLabs: butonul „Ascultă”
scripts/            migrare în PostgreSQL, backup, urcarea pozelor în cloud
Dockerfile, docker-compose.yml, Caddyfile   serverul, cu HTTPS automat
ui/                 componente, hărți, stiluri
views/              ecranele: client, meșter, lucrare, comun (intrare, ghid, chat, profil), admin, prezentare,
                    comunitate (chestionar Living Labs și „Ce e nou”)
pitch/              deck, scriptul demo, textul de înscriere, articolul DEV, chestionarul
```

## Trust Score

| Factor | Puncte |
|---|---|
| Evaluarea medie | 25 |
| Lucrarea mai ține (feedback la 1 zi, 1 săptămână, 1 lună) | 20 |
| Programări respectate | 15 |
| Punctualitate (sosire confirmată de rețea) | 10 |
| Lucrări finalizate | 10 |
| Verificare Nokia (număr + SIM stabil) | 10 |
| Fără reclamații confirmate | 10 |

Un factor fără date primește jumătate din puncte. Niveluri: 90+ Excelent, 75+ Foarte bun, 60+ Bun, altfel În creștere.
