# SKILLIO: platforma în care clientul nu riscă nimic

**Find skills. Build trust.** Meșteri pentru casă în Timișoara, cu banii blocați până când clientul confirmă că
lucrarea e în regulă.

Proiect pentru **UniHack 2026** (LigaAC, Politehnica Timișoara), tema **The Bloom**, track **Connected Communities**.

---

## Problema

Când chemi un meșter acasă, tot riscul e la tine:

1. **Plătești și lucrarea rămâne neterminată.** Banii pleacă înainte să vezi rezultatul.
2. **Prețul crește la fața locului.** Meșterul ajunge, apa e deja oprită și nu mai poți spune nu.
3. **Numărul tău ajunge la oricine**, iar când apare o problemă nu te ajută nimeni.

Platformele din România (Meseriașul Meu, Daibau, OLX Servicii) te pun doar în legătură cu meșterul. De acolo ești
pe cont propriu, iar meșterul plătește pentru fiecare client primit.

## Soluția

SKILLIO face legătura **și** protejează ambele părți până la final:

| Ce face SKILLIO | De ce contează |
|---|---|
| **Banii stau blocați** (escrow) până confirmă amândoi, apoi încă 24 de ore | Plătești doar când ești mulțumit |
| **Prețul se reconfirmă la fața locului**, cu poză și motiv. Gemini spune dacă e rezonabil, dar decide clientul | Dacă refuzi, primești banii înapoi și plătești doar 40 lei deplasarea |
| **Numerele de telefon rămân private** în ambele sensuri; chatul ascunde automat telefoane, emailuri, WhatsApp | Totul rămâne în aplicație, unde ești protejat |
| **Disputele le decide un om** (mediator SKILLIO), nu un AI. Și meșterul poate deschide o dispută | Încredere: un om ascultă ambele părți |
| **SOS 45 lei**: un meșter real te ghidează video să închizi apa sau curentul | Ajutor în câteva minute la o urgență |
| **Agentul AI** transformă o propoziție într-o renovare planificată, cu echipă programată | Clientul nu trebuie să știe ce meserii îi trebuie și în ce ordine |
| **Meșterul nu plătește pentru clienți** | Plătește doar 10% dintr-o lucrare finalizată |

Fiecare piesă există separat undeva în lume (de exemplu, Urban Company în India are taxă de inspecție cu drept de
refuz, iar TaskRabbit în SUA ascunde numerele). Din ce am verificat noi, nimeni nu le pune împreună și nimeni nu
reconfirmă prețul la fața locului, cu verificare AI și drept de refuz.

**Legătura cu tema The Bloom:** încrederea crește cartier cu cartier. Pornim cu un singur cartier (Elisabetin) și 2-3
meserii, iar fiecare lucrare bine făcută crește Trust Score-ul meșterului.

---

## Cum funcționează

```
Client: descrie problema (text, poză, video sau voce)
   │   Gemini: meseria potrivită, cauza probabilă, prețul estimat
   ▼
Meșterii din zonă trimit oferte  ──►  clientul alege după preț, Trust Score și recenzii
   ▼
Clientul plătește oferta + 5% taxă de protecție  ──►  BANII SE BLOCHEAZĂ (Solana devnet în demo)
   ▼
Meșterul ajunge și RECONFIRMĂ PREȚUL cu poză + motiv  ──►  Gemini: „rezonabil / de discutat / ridicat”
   ├── clientul refuză: primește banii înapoi, meșterul păstrează 40 lei deplasarea
   └── clientul acceptă: lucrarea începe (bani în plus doar cu acordul clientului)
   ▼
Meșterul marchează „gata”, clientul confirmă  ──►  banii mai stau blocați 24 de ore
   ├── oricine deschide o dispută: un mediator uman decide pe baza pozelor, chatului și cronologiei
   └── fără dispută: banii pleacă la meșter (minus 10% comision)
   ▼
Feedback după 1 zi, 1 săptămână și 1 lună  ──►  Trust Score (0-100)
```

Stările unei lucrări: `deschisa → acceptata → de_plata → programata → sosit → reconfirmare → in_lucru → gata →
confirmata (24 h) → finalizata`, plus `disputa` și `anulata`.

### Roluri

- **Client**: Acasă (promisiunea „Tu nu riști nimic”), Agent AI, Cerere nouă, Chat, Profil, SOS.
- **Meșter**: Cereri primite (urgentele primele), oferte, calendar, reconfirmarea prețului, lista de materiale
  cu prețuri pe magazine, apeluri SOS.
- **Admin / mediator**: panoul **Mediere** cu dispute (lucrări și SOS), dovezi, cronologie, decizie; statistici.

---

## Gemini: cum folosim AI-ul

Gemini **ajută și explică**, dar nu decide niciodată în locul oamenilor: prețul îl acceptă clientul, disputele le
decide un mediator uman. Dacă Gemini nu răspunde, aplicația merge mai departe pe reguli proprii.

| Funcție | Ce face | Tehnică Gemini |
|---|---|---|
| **Diagnostic** | Din text, poză, **video** sau **mesaj vocal**: meseria, cauza probabilă, prețul, materialele | Multimodal (imagine, video, audio), JSON |
| **Agentul clientului** | Explică problema, calculează costul și împarte lucrările mari în etape, în ordinea corectă | **Function calling** cu 5 unelte |
| **„Cum am calculat”** | Arată fiecare calcul făcut de agent, cu sursele | Jurnalul apelurilor de unelte |
| **O propoziție, o echipă întreagă** | „Baia renovată până pe 20 decembrie, buget 9000 lei”: agentul înțelege termenul și bugetul, alege meșterul pentru fiecare etapă (Trust Score + prima zi liberă), îi programează în ordine și verifică bugetul și termenul | Extragere structurată + logica platformei |
| **Prețuri live** | Prețul de azi al materialelor la Dedeman, Hornbach și Leroy Merlin, cu linkuri | **Google Search grounding** |
| **Lista meșterului** | Ce materiale îi trebuie pentru lucrare și unde e coșul cel mai ieftin | Google Search grounding |
| **Părere despre preț** | La reconfirmarea de la fața locului: interval normal și verdict, din poza meșterului | Multimodal, JSON |
| **Traducere în chat** | Clientul sau meșterul citesc mesajele în limba lor (EN, UK, HU, DE, IT) | Traducere în lot |

Uneltele agentului (în `services/unelte.py`):

1. `tarif_manopera`: tarife de manoperă pe mp, bucată sau circuit (22 de lucrări, Timișoara 2026).
2. `pret_materiale`: prețuri de materiale în variantele economic, mediu și premium, cu 10% pierderi la suprafețe.
3. `pret_live_material`: prețul de azi, căutat pe Google, cu surse.
4. `preturi_platforma`: mediana prețurilor acceptate efectiv pe SKILLIO pentru acea meserie.
5. `taxe_skillio`: totalul clientului cu taxa de protecție, urgența și deplasarea.

Modelul se alege din `.env` (`GEMINI_MODEL`). Dacă un model nu există sau e aglomerat, aplicația încearcă
automat următorul (`gemini-3.5-flash-lite`, `gemini-3.5-flash`, `gemini-flash-latest` etc.).

---

## Side quests

| Side quest | Ce am făcut | Stare |
|---|---|---|
| **Gemini** | Tot ce e descris mai sus: multimodal, function calling, Google Search grounding, agent | Folosit în demo |
| **Solana** | Plata blocată (escrow) pe **devnet**: blocare, eliberare 90/10, returnare; tranzacțiile apar pe Solana Explorer (`services/solana.py`) | Folosit în demo |
| **Auth0** | Login securizat cu `st.login` (`services/autentificare.py`, `.streamlit/secrets.toml`) | Implementat, opțional |
| **ElevenLabs** | Butonul „Ascultă”: agentul citește explicația cu voce (`services/voce.py`) | Implementat, opțional |
| **Tiger Data** | PostgreSQL în cloud prin `DATABASE_URL`, cu migrare din SQLite (`scripts/migreaza_in_postgres.py`) | Implementat; în demo folosim SQLite local, fiindcă e mai rapid |
| **Vultr** | Docker + Caddy (HTTPS automat) și ghid pas cu pas în [PRODUCTIE.md](PRODUCTIE.md); poze în Vultr Object Storage (`services/stocare.py`) | Pregătit, **nepublicat** (vezi mai jos) |
| **Living Labs** | Chestionar în aplicație și pagina „Ce e nou” (`views/comunitate.py`) | Implementat |

### Despre deploy-ul pe Vultr

Am vrut să publicăm aplicația pe **Vultr** (Cloud Compute, Frankfurt, imagine Docker). Tot ce trebuie pentru asta
e în repo: `Dockerfile`, `docker-compose.yml`, `Caddyfile` (HTTPS automat cu Let's Encrypt) și pașii din
[PRODUCTIE.md](PRODUCTIE.md). **Contul de Vultr nu a fost activat la timp** în timpul hackathonului, așa că nu am
putut porni serverul. Pentru demo rulăm aplicația local, pe laptop, iar telefoanele se conectează prin aceeași
rețea Wi-Fi. Odată activat contul, deploy-ul înseamnă trei comenzi:

```bash
git clone https://github.com/Petruse18/skillio_final.git && cd skillio_final
nano .env                       # cheile + DOMENIU=skillio.exemplu.ro
docker compose up -d --build
```

---

## Model de business

- **10%** comision de la meșter, doar pe lucrări finalizate (fără taxe pe clienți primiți).
- **5%** taxă de protecție plătită de client; din ea plătim mediatorii umani (ca o asigurare).
- Pe o lucrare de 300 lei: **45 lei** venit, circa 6 lei procesarea plății. Chiar cu 20% dintre lucrări ajunse la
  mediere, rămân circa 27 lei pe lucrare.
- **SOS**: 45 lei, din care 35 lei merg la meșter.
- Comparație: Airtasker 10-20%, Urban Company 8,5-25%.
- **Lansare**: un cartier (Elisabetin), 2-3 meserii, apoi extindere cartier cu cartier.

## Ce schimbăm pentru producție

- **Plata**: escrow-ul trece printr-un procesator autorizat (Stripe Connect, Mangopay sau Lemonway), nu prin Solana
  devnet, fără licență proprie de instituție de plată.
- **Apelul SOS**: în demo, cameră video printr-un server Jitsi public. În producție, un serviciu WebRTC cu
  înregistrare (Daily, Twilio Video), stocare în UE și ștergere automată la 30 de zile.
- **GDPR**: consimțământ explicit pentru înregistrări, ștergere la 30 de zile, date stocate în UE.
- **Problemă încă deschisă**: lucrările repetate făcute în afara platformei după prima întâlnire.

---

## Pornire rapidă

Ai nevoie de **Python 3.10+**.

```bash
python -m venv .venv
.venv\Scripts\activate            # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # apoi completează cheile (Mac/Linux: cp)
streamlit run app.py
```

Pe Windows poți folosi și `porneste.bat`. La prima pornire se creează `data/skillio.db` cu date demo.

| Adresă | Ce vezi |
|---|---|
| http://localhost:8501 | aplicația, cu ecranul de intrare |
| http://localhost:8501/?mod=prezentare | **modul de prezentare**: clientul și meșterul unul lângă altul, plus butoanele de timp (+1 zi etc.) |

**Pe două telefoane:** pornește cu `streamlit run app.py --server.address 0.0.0.0`, apoi deschide pe telefoane
adresa „Network URL” din terminal (aceeași rețea Wi-Fi sau hotspot). Fără HTTPS, microfonul din browser poate fi
blocat pe telefon; încărcarea pozelor și a video-urilor merge.

### Conturi demo

| Cont | Telefon | Rol |
|---|---|---|
| Ana Popescu | +40722000001 | client, Elisabetin |
| Ionel Mureșan | +40722000101 | instalator și centrale |
| Admin | +40700000000 | mediere, statistici, controale demo |

### Chei (în `.env`, care nu se urcă niciodată pe GitHub)

| Variabilă | Pentru ce | Fără ea |
|---|---|---|
| `GEMINI_API_KEY`, `GEMINI_MODEL` | tot ce ține de AI | reguli proprii (cuvinte cheie, tabele de prețuri) |
| `SOLANA_SECRET_KEY` | escrow pe devnet (`python -m scripts.solana_portofel`) | plată simulată |
| `ELEVENLABS_API_KEY` | vocea agentului | vocea browserului |
| `DATABASE_URL` | PostgreSQL (Tiger Data) | SQLite local (recomandat pentru demo) |
| `DEMO_LOGIN`, `MOD_PREZENTARE` | butoanele de cont demo și modul de prezentare | – |
| `DOMENIU` | domeniul pentru HTTPS pe server | – |

Auth0 se configurează în `.streamlit/secrets.toml` (și acesta rămâne doar local).

---

## Scenariul demo (3 minute)

1. **Agentul**: Ana apasă exemplul „Baia renovată până pe 20 decembrie, buget 9000 lei”. Apar 4 etape, costul,
   „Cum am calculat” (cu prețuri live) și **echipa programată**: instalator, electrician, faianțar, zugrav, cu zile
   în ordinea corectă și verificarea bugetului.
2. **Plata blocată**: Ionel trimite oferta, Ana plătește. Banii se blochează (+5% protecție, vizibil).
3. **Reconfirmarea**: Ionel ajunge, face poză și cere 260 lei în loc de 200. Gemini: „preț rezonabil”. Ana poate
   accepta sau refuza și plăti doar 40 lei.
4. **Chat**: Ana scrie un număr de telefon, iar SKILLIO îl ascunde.
5. **Confirmare + 24 h**: ambii confirmă, banii mai stau 24 h. Cu o dispută deschisă, adminul decide la Mediere.
6. **SOS 45 lei**: apel video cu un meșter real, înregistrat cu acord.

---

## Tehnologii

- **Python 3.11 + Streamlit 1.67**, interfață gândită pentru telefon (navigare jos, carduri, temă proprie).
- **SQLite** (demo) sau **PostgreSQL** (Tiger Data) cu `psycopg_pool`.
- **Gemini** prin `google-genai`: multimodal, function calling, Google Search grounding.
- **Solana devnet** (`solders`), **Auth0**, **ElevenLabs**.
- **Docker + Caddy** pentru server, gata pentru Vultr.
- Aproximativ **5.000 de linii de Python** efectiv și 400 de linii de CSS.

## Structura proiectului

```
app.py                  intrarea, navigarea de jos, sincronizarea între telefoane
core/config.py          regulile de business (comision, taxe, SOS, sloturi), meserii, cartiere
core/db.py              baza de date (SQLite sau PostgreSQL)
core/logica.py          tot fluxul: cereri, oferte, plată blocată, reconfirmare, dispute, SOS, echipa agentului
core/trust.py           Trust Score
core/seed.py            datele demo
core/timp.py            ceasul aplicației (se poate da înainte pentru demo)
services/ai.py          Gemini: diagnostic, agent, părere despre preț, prețuri live, traducere
services/unelte.py      uneltele (function calling) cu care agentul calculează costurile
services/solana.py      escrow pe Solana devnet
services/autentificare.py, voce.py, stocare.py, mesaje_externe.py, geo.py
views/                  ecranele: client, meșter, lucrare, asistent (agent), materiale, sos, admin (mediere),
                        comun (intrare, chat, profil), comunitate, prezentare
ui/                     componente și stiluri (tokens.css, modern.css, streamlit.css)
scripts/                migrare în PostgreSQL, backup, portofel Solana, urcarea pozelor în cloud
pitch/                  scriptul demo, modelul de business, textul de înscriere
Dockerfile, docker-compose.yml, Caddyfile, PRODUCTIE.md   deploy pe server (Vultr)
```

## Trust Score (0-100)

Calculat doar din activitatea reală din aplicație, nu din popularitate.

| Factor | Puncte |
|---|---|
| Evaluarea clienților | 25 |
| Lucrarea ține (feedback la 1 zi, 1 săptămână, 1 lună) | 20 |
| Programări respectate | 15 |
| Punctualitate | 10 |
| Lucrări finalizate | 10 |
| Identitate verificată | 10 |
| Fără reclamații confirmate | 10 |

Un factor fără date primește jumătate din puncte. Niveluri: 90+ Excelent, 75+ Foarte bun, 60+ Bun, altfel În creștere.

---

## Echipa

*(completați numele membrilor echipei și rolurile)*

Ești la început cu codul? [GHID.md](GHID.md) explică proiectul pas cu pas.
