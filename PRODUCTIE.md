# SKILLIO în producție: pas cu pas

Codul pentru toți pașii e gata. Fiecare parte pornește doar când pui cheile ei. **Fără chei, aplicația merge
exact ca acum (demo pe laptop)**, deci prezentarea nu se strică dacă ceva nu e gata.

| Pas | Ce îți trebuie | Unde pui datele | Cost |
|---|---|---|---|
| 1. Login securizat | cont **Auth0** | `.streamlit/secrets.toml` | gratuit |
| 2. Bază de date de producție | cont **Tiger Data** (PostgreSQL) | `.env` → `DATABASE_URL` | perioadă de probă gratuită |
| 3. Poze în cloud | **Vultr Object Storage** | `.env` → `S3_...` | aprox. 6 $/lună |
| 4. Server cu domeniu și HTTPS | server **Vultr** + un domeniu (sau DuckDNS, gratuit) | `.env` → `DOMENIU` | aprox. 5-10 $/lună |
| 5. Notificări | **Gmail** (email) și/sau **Twilio** (SMS) | `.env` → `SMTP_...`, `TWILIO_...` | gratuit / credit de probă |
| 6. Plăți pe blockchain | portofel **Solana devnet** (Phantom sau scriptul nostru) | `.env` → `SOLANA_SECRET_KEY` | gratuit (SOL de test) |
| 7. Voce | cont **ElevenLabs** | `.env` → `ELEVENLABS_API_KEY` | gratuit (10.000 caractere/lună) |
| AI | cheie **Gemini** (Google AI Studio) | `.env` → `GEMINI_API_KEY` | gratuit |

Ordinea recomandată: Gemini, 6 și 7 (cele mai rapide, câte 5 minute, și se văd direct în demo), apoi 1 → 2 → 3 → 5 pe laptop (verifici că merge), apoi 4 (urci totul pe server).

> **Fișierele secrete nu se urcă niciodată pe GitHub:** `.env` și `.streamlit/secrets.toml` sunt deja în `.gitignore`.
> Nu le trimite pe chat. Pe server le creezi direct acolo.

După ce schimbi `.env` sau `secrets.toml`, repornește aplicația (închide fereastra neagră și rulează iar `porneste.bat`).
Ca să vezi ce e conectat: intră ca **Admin** → **Integrări și producție**. Acolo apare fiecare parte, cu „conectat” sau „oprit”.

---

## 1. Login securizat cu Auth0

**De ce:** acum oricine poate intra cu orice număr. Cu Auth0, omul intră cu un cod primit pe email (sau SMS, sau contul Google),
iar noi nu ținem nicio parolă. Aplicația folosește login-ul integrat din Streamlit (`st.login`).

1. Intră pe **auth0.com** → *Sign up* (gratuit). La creare alege regiunea **EU**.
2. În meniul din stânga: **Applications → Applications → Create Application**.
   Nume: `SKILLIO`, tip: **Regular Web Applications** → *Create*.
3. Deschide tab-ul **Settings** al aplicației. Copiază de acolo **Domain**, **Client ID** și **Client Secret**.
4. Tot în *Settings*, mai jos, completează și apasă **Save**:
   - **Allowed Callback URLs:** `http://localhost:8501/oauth2callback` (mai târziu adaugi, după virgulă, `https://DOMENIUL-TAU/oauth2callback`)
   - **Allowed Logout URLs:** `http://localhost:8501` (mai târziu și `https://DOMENIUL-TAU`)
5. Cod pe email, fără parolă: **Authentication → Passwordless → Email** → pornește-l. Apoi, în aplicația SKILLIO,
   tab-ul **Connections**: bifează `email` (și `google-oauth2`, dacă vrei intrare cu Google).
   *Cod prin SMS:* tot în Passwordless → **SMS**. Auth0 cere un cont Twilio (vezi pasul 5).
6. În folderul proiectului, copiază `.streamlit/secrets.toml.example` ca `.streamlit/secrets.toml` și completează:
   - `client_id`, `client_secret` din pasul 3;
   - în `server_metadata_url`, înlocuiește `DOMENIUL-TAU` cu *Domain* (ex. `dev-abc123.eu.auth0.com`);
   - `cookie_secret`: un șir lung, aleatoriu. Îl generezi cu `python -c "import secrets; print(secrets.token_hex(32))"`.
7. În `.env`: `ADMIN_EMAILS=emailul.tau@gmail.com`. Cine intră cu acest email devine admin.
8. Repornește aplicația. Pe ecranul de intrare apare butonul **Intră în cont**. La prima intrare îți cere numele,
   telefonul și dacă ești client sau meșter.

**Pentru prezentare:** cu `DEMO_LOGIN=1` (în `.env`) rămân și butoanele demo (Ana, Ionel, Admin) și modul cu două telefoane.
**Pe serverul public:** pune `DEMO_LOGIN=0`. Atunci se intră doar prin Auth0, iar modul demo e oprit.

---

## 2. Bază de date de producție: Tiger Data (PostgreSQL)

**De ce:** SQLite e un fișier pe laptop. Tiger Data e un PostgreSQL în cloud, cu backup automat.

1. Intră pe **tigerdata.com** → *Get started / Sign up*.
2. **Create service** → alege **PostgreSQL**, regiunea **Europe (Frankfurt)**, cea mai mică mărime → *Create*.
3. La final îți arată **connection string**-ul, de forma
   `postgres://tsdbadmin:PAROLA@xxxx.tsdb.cloud.timescale.com:PORT/tsdb?sslmode=require`.
   **Salvează-l acum.** Parola nu se mai afișează (poți descărca și fișierul cu datele de conectare).
4. În `.env`: `DATABASE_URL=` + string-ul de mai sus.
5. Alege una dintre variante:
   - **Bază nouă, cu date demo:** pornește aplicația. Creează singură tabelele și pune datele demo (`DATE_DEMO=1`).
   - **Muți ce ai acum în SQLite:** din terminalul VS Code, în folderul proiectului:
     ```
     .venv\Scripts\python -m scripts.migreaza_in_postgres
     ```

**Backup:** Tiger Data face backup automat. În plus, poți face oricând un backup propriu:
- din aplicație: Admin → *Integrări și producție* → **Pregătește un backup** → descarci un fișier JSON;
- din terminal: `.venv\Scripts\python -m scripts.backup` (se salvează în `backups/`);
- restaurare: `.venv\Scripts\python -m scripts.backup --restaureaza backups\FISIER.json`.

Merge și pe orice alt PostgreSQL (Neon, Supabase, Vultr Managed Database): pui doar alt `DATABASE_URL`.

---

## 3. Poze în cloud: Vultr Object Storage

**De ce:** pozele (probleme, portofolii, acte) nu mai stau pe laptop sau pe server, ci într-un „bucket” în cloud.
Bucket-ul rămâne privat; aplicația dă linkuri semnate, valabile o oră.

1. Intră pe **vultr.com** → cont nou (cere un card; vezi dacă hackathonul oferă credit Vultr).
2. **Products → Cloud Storage → Object Storage → Add Object Storage**. Alege o regiune în Europa (ex. Amsterdam) → *Add*.
3. Deschide-l când e gata. Tab-ul **Overview / S3 Credentials** îți arată:
   **Hostname** (ex. `ams1.vultrobjects.com`), **Access Key**, **Secret Key**.
4. Tab-ul **Buckets → Create Bucket**: nume `skillio-poze` (doar litere mici și cratime).
5. În `.env`:
   ```
   S3_ENDPOINT=https://ams1.vultrobjects.com
   S3_BUCKET=skillio-poze
   S3_ACCESS_KEY=...
   S3_SECRET_KEY=...
   ```
6. Repornește. Pozele noi merg direct în cloud. Ca să urci și pozele vechi:
   `.venv\Scripts\python -m scripts.urca_poze_in_cloud`.

Dacă cloud-ul nu răspunde, aplicația salvează poza local, ca să nu se piardă.

---

## 5. Notificări prin email și SMS

Se trimit automat la: solicitare nouă (meșterilor), ofertă nouă, ofertă acceptată, oră propusă, programare confirmată,
plată, lucrare gata, bani încasați. Restul notificărilor rămân doar în clopoțelul din aplicație.

**Email cu Gmail** (cel mai simplu):
1. Contul Google trebuie să aibă **verificare în doi pași** pornită (myaccount.google.com → Securitate).
2. **myaccount.google.com/apppasswords** → creează o parolă de aplicație cu numele „SKILLIO” → copiază cele 16 litere.
3. În `.env`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=adresa.ta@gmail.com
   SMTP_PAROLA=cele16litere
   ```
4. Emailul se trimite la adresa cu care omul a intrat prin Auth0. Conturile demo nu au email.

**SMS cu Twilio:**
1. **twilio.com** → *Sign up* (primești credit de probă) → *Get a phone number*.
2. Din **Console**: copiază **Account SID**, **Auth Token** și numărul primit.
3. În `.env`: `TWILIO_SID=...`, `TWILIO_TOKEN=...`, `TWILIO_FROM=+1...`.
4. În contul de probă, Twilio trimite doar către numerele verificate de tine (Console → *Verified Caller IDs*). Pentru demo e suficient.

**Test:** Admin → *Integrări și producție* → scrie un email sau un număr → **Trimite test**.

---

## 4. Server Vultr cu domeniu și HTTPS

Aplicația rulează în Docker, iar **Caddy** (inclus) ia singur certificatul HTTPS de la Let's Encrypt.

### a) Serverul
1. Pe vultr.com: **Deploy → Cloud Compute → Shared CPU**, regiune Frankfurt sau Amsterdam.
2. Imagine: **Marketplace Apps → Docker** (Ubuntu, cu Docker instalat). Mărime: 1 vCPU / 2 GB RAM.
3. *Deploy*. Peste un minut primești **IP**-ul și parola de **root** (în pagina serverului).

### b) Domeniul
- **Ai domeniu:** în panoul domeniului, adaugă o înregistrare **A**: `skillio` (sau `@`) → IP-ul serverului.
- **Gratuit:** pe **duckdns.org** intri cu Google, alegi un nume (ex. `skillio-tm`), pui IP-ul serverului → *update ip*.
  Domeniul tău e `skillio-tm.duckdns.org`.

### c) Pornirea
Din PowerShell pe laptop: `ssh root@IP-UL-SERVERULUI` (parola din pagina serverului), apoi:
```bash
git clone https://github.com/CONTUL-TAU/skillio.git
cd skillio
cp .env.example .env
nano .env
```
În `.env` pune toate cheile de mai sus, plus:
```
DOMENIU=skillio-tm.duckdns.org
URL_APP=https://skillio-tm.duckdns.org
DEMO_LOGIN=0
```
(În `nano`: salvezi cu `Ctrl+O`, Enter, ieși cu `Ctrl+X`.)

Fișierul Auth0:
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
nano .streamlit/secrets.toml
```
Aici `redirect_uri = "https://skillio-tm.duckdns.org/oauth2callback"`. Adaug-o și în Auth0, la *Allowed Callback URLs*.
Fără Auth0 pe server, creează măcar fișierul gol: `touch .streamlit/secrets.toml`.

Pornire:
```bash
ufw allow 80,443/tcp
docker compose up -d --build
```
Peste 1-2 minute aplicația e pe `https://skillio-tm.duckdns.org`.

### d) Întreținere
- **Actualizare după un push pe GitHub:** `cd skillio && git pull && docker compose up -d --build`
- **Jurnal (erori):** `docker compose logs -f app`
- **Backup zilnic la 3 noaptea:** `crontab -e`, apoi adaugă rândul
  `0 3 * * * cd /root/skillio && docker compose exec -T app python -m scripts.backup`
- **Repo privat:** la `git clone` GitHub îți cere utilizatorul și un *token*
  (github.com → Settings → Developer settings → Personal access tokens), nu parola.

---

## 6. Plăți verificabile pe Solana (devnet)

Ce face: când clientul plătește, suma (simbolică, 1 leu = 0,0001 SOL) trece din portofelul platformei într-un „seif”.
La confirmare, din seif pleacă 90% la meșter și 10% la platformă, iar memo-ul tranzacției conține amprenta lucrării
(„pașaportul”). La anulare banii se întorc. Pe ecranul lucrării apare cardul **Plată verificabilă pe blockchain** cu link spre
Solana Explorer pentru fiecare tranzacție. Devnet e rețeaua de test: SOL-ul e gratuit și nu are valoare.

Varianta cea mai simplă (fără Phantom):

1. În terminalul VS Code (cu `.venv` activat): `pip install -r requirements.txt`, apoi `python -m scripts.solana_portofel`.
2. Scriptul îți afișează un rând `SOLANA_SECRET_KEY=...`. Copiază-l în `.env`. **Nu-l pune pe chat sau pe GitHub.**
3. Rulează iar `python -m scripts.solana_portofel`. Îți arată adresa platformei și cere singur 1 SOL de test.
   Dacă spune că a fost refuzat (limită), intră pe https://faucet.solana.com, alege **Devnet**, lipește adresa și cere 5 SOL.
4. Repornește aplicația. În Admin → **Integrări și producție** scrie „Solana: conectat”, cu butonul **Verifică soldul**.

Varianta cu Phantom (arată bine la juriu):

1. Instalează extensia **Phantom** în Chrome, creează un portofel.
2. Setări → Developer Settings → **Testnet Mode** pornit, rețeaua **Solana Devnet**.
3. Setări → contul tău → **Show Private Key** → copiază cheia în `.env` la `SOLANA_SECRET_KEY=`.
4. Cere SOL de test pe https://faucet.solana.com (Devnet) pentru adresa din Phantom.
5. Opțional: meșterul își poate pune adresa lui Phantom în **Profil → Portofel Solana**; altfel platforma îi creează una.

La prezentare: după ce Ana confirmă lucrarea, deschide cardul **Plată verificabilă pe blockchain** și apasă pe linkul tranzacției.
Juriul vede pe Solana Explorer transferul 90/10 și memo-ul cu pașaportul. Dacă internetul cade, plata rămâne simulată.

---

## 7. Voce cu ElevenLabs

Ce face: butonul **Ascultă** citește diagnosticul AI și ofertele primite, cu o voce naturală în română.
Fără cheie, citește vocea browserului (mai robotică, dar merge).

1. Cont pe https://elevenlabs.io (gratuit).
2. Profil (stânga jos) → **API Keys** → **Create API key**. Bifează permisiunea **Text to Speech**.
3. În `.env`: `ELEVENLABS_API_KEY=...`. Vocea implicită merge; dacă vrei alta, ia „Voice ID” din Voice Library și pune-l la `ELEVENLABS_VOICE_ID`.
4. Repornește aplicația și apasă **Ascultă** după un diagnostic.

---

## Gemini (diagnosticul AI)

1. https://aistudio.google.com → **Get API key** → **Create API key**.
2. În `.env`: `GEMINI_API_KEY=...`. Repornește. Sub diagnostic scrie „Gemini” în loc de „reguli simple”.

---

## Ce face fiecare fișier nou

| Fișier | Rol |
|---|---|
| `services/autentificare.py` | login Auth0 (st.login), legătura cu contul SKILLIO, admin după email |
| `core/db.py` | aceeași aplicație pe SQLite sau PostgreSQL, ales după `DATABASE_URL` |
| `services/stocare.py` | poze în S3 / Vultr sau local, linkuri semnate |
| `services/mesaje_externe.py` | email (SMTP) și SMS (Twilio), trimise în fundal |
| `scripts/migreaza_in_postgres.py` | mută datele din SQLite în PostgreSQL |
| `scripts/backup.py` | backup și restaurare (JSON) |
| `scripts/urca_poze_in_cloud.py` | urcă pozele locale în cloud |
| `Dockerfile`, `docker-compose.yml`, `Caddyfile` | serverul: aplicația + HTTPS automat |
| `.streamlit/secrets.toml.example` | model pentru datele Auth0 |
| `services/solana.py` | plata blocată pe Solana devnet: blocare, eliberare 90/10, returnare, pașaport |
| `scripts/solana_portofel.py` | creează portofelul platformei, arată soldul, cere SOL de test |
| `services/voce.py` | ElevenLabs: transformă textul în voce |
| `views/comunitate.py` | Living Labs: chestionarul din aplicație și pagina „Ce e nou” |
