# SKILLIO: the platform where the client risks nothing

**Find skills. Build trust.** Home repair professionals in Timișoara, with the money held in escrow until the client
confirms the job is done right.

Project for **UniHack 2026** (LigaAC, Politehnica University of Timișoara), theme **The Bloom**, track
**Connected Communities**.

---

## The problem

When you call a tradesperson to your home, all the risk is on you:

1. **You pay and the job is left unfinished.** The money is gone before you see the result.
2. **The price goes up on site.** The tradesperson arrives, the water is already shut off, and you can no longer say no.
3. **Your phone number ends up with anyone**, and when something goes wrong, nobody helps you.

Platforms in Romania (Meseriașul Meu, Daibau, OLX Servicii) only connect you with the tradesperson. From there you
are on your own, and the tradesperson pays for every client they receive.

## The solution

SKILLIO makes the connection **and** protects both sides until the very end:

| What SKILLIO does | Why it matters |
|---|---|
| **The money is held in escrow** until both sides confirm, then for another 24 hours | You only pay when you are satisfied |
| **The price is reconfirmed on site**, with a photo and a reason. Gemini says whether it is reasonable, but the client decides | If you refuse, you get your money back and pay only the 40 lei call-out fee |
| **Phone numbers stay private** both ways; the chat automatically hides phone numbers, emails and WhatsApp | Everything stays in the app, where you are protected |
| **Disputes are decided by a human** (a SKILLIO mediator), not by an AI. The tradesperson can open a dispute too | Trust: a person listens to both sides |
| **SOS for 45 lei**: a real tradesperson guides you over video to shut off the water or the power | Help within minutes in an emergency |
| **The AI agent** turns a single sentence into a planned renovation, with a scheduled team | The client does not need to know which trades are needed or in what order |
| **Tradespeople do not pay for leads** | They pay only 10% of a completed job |

Each piece exists separately somewhere in the world (for example, Urban Company in India charges an inspection fee
with the right to refuse, and TaskRabbit in the US hides phone numbers). As far as we could check, nobody puts them
together, and nobody reconfirms the price on site with AI verification and the right to refuse.

**Link to The Bloom theme:** trust grows neighbourhood by neighbourhood. We start with a single neighbourhood
(Elisabetin) and 2-3 trades, and every job done well raises the tradesperson's Trust Score.

---

## How it works

```
Client: describes the problem (text, photo, video or voice)
   │   Gemini: the right trade, the likely cause, the estimated price
   ▼
Nearby tradespeople send offers  ──►  the client chooses by price, Trust Score and reviews
   ▼
The client pays the offer + 5% protection fee  ──►  THE MONEY IS LOCKED (Solana devnet in the demo)
   ▼
The tradesperson arrives and RECONFIRMS THE PRICE with a photo + reason  ──►  Gemini: "reasonable / debatable / high"
   ├── the client refuses: gets the money back, the tradesperson keeps the 40 lei call-out fee
   └── the client accepts: work begins (extra money only with the client's consent)
   ▼
The tradesperson marks the job "done", the client confirms  ──►  the money stays locked for another 24 hours
   ├── either side opens a dispute: a human mediator decides based on photos, chat and timeline
   └── no dispute: the money goes to the tradesperson (minus 10% commission)
   ▼
Feedback after 1 day, 1 week and 1 month  ──►  Trust Score (0-100)
```

Job states: `deschisa → acceptata → de_plata → programata → sosit → reconfirmare → in_lucru → gata →
confirmata (24 h) → finalizata`, plus `disputa` and `anulata`
(open → accepted → awaiting payment → scheduled → arrived → reconfirmation → in progress → done →
confirmed → completed, plus dispute and cancelled).

### Roles

- **Client**: Home (the "You risk nothing" promise), AI Agent, New request, Chat, Profile, SOS.
- **Tradesperson**: Incoming requests (urgent ones first), offers, calendar, price reconfirmation, materials list
  with prices per store, SOS calls.
- **Admin / mediator**: the **Mediation** panel with disputes (jobs and SOS), evidence, timeline, decision; statistics.

---

## Gemini: how we use AI

Gemini **helps and explains**, but never decides on behalf of people: the client accepts the price, and disputes are
decided by a human mediator. If Gemini does not respond, the app carries on using its own rules.

| Feature | What it does | Gemini technique |
|---|---|---|
| **Diagnosis** | From text, a photo, **video** or a **voice message**: the trade, the likely cause, the price, the materials | Multimodal (image, video, audio), JSON |
| **Client agent** | Explains the problem, calculates the cost and splits large jobs into stages, in the correct order | **Function calling** with 5 tools |
| **"How we calculated"** | Shows every calculation made by the agent, with sources | Tool call log |
| **One sentence, a whole team** | "Bathroom renovated by 20 December, budget 9000 lei": the agent understands the deadline and budget, picks the tradesperson for each stage (Trust Score + first free day), schedules them in order and checks the budget and deadline | Structured extraction + platform logic |
| **Live prices** | Today's material prices at Dedeman, Hornbach and Leroy Merlin, with links | **Google Search grounding** |
| **Tradesperson's list** | Which materials the job needs and where the cheapest basket is | Google Search grounding |
| **Price opinion** | During on-site reconfirmation: normal range and verdict, from the tradesperson's photo | Multimodal, JSON |
| **Chat translation** | The client or tradesperson read messages in their own language (EN, UK, HU, DE, IT) | Batch translation |

The agent's tools (in `services/unelte.py`):

1. `tarif_manopera`: labour rates per sqm, per piece or per circuit (22 job types, Timișoara 2026).
2. `pret_materiale`: material prices in budget, mid-range and premium variants, with 10% waste on surfaces.
3. `pret_live_material`: today's price, searched on Google, with sources.
4. `preturi_platforma`: the median of prices actually accepted on SKILLIO for that trade.
5. `taxe_skillio`: the client's total including the protection fee, urgency surcharge and call-out fee.

The model is set in `.env` (`GEMINI_MODEL`). If a model does not exist or is overloaded, the app automatically tries
the next one (`gemini-3.5-flash-lite`, `gemini-3.5-flash`, `gemini-flash-latest`, etc.).

---

## Side quests

| Side quest | What we did | Status |
|---|---|---|
| **Gemini** | Everything described above: multimodal, function calling, Google Search grounding, agent | Used in the demo |
| **Solana** | Escrow payment on **devnet**: lock, 90/10 release, refund; transactions show up on Solana Explorer (`services/solana.py`) | Used in the demo |
| **Auth0** | Secure login with `st.login` (`services/autentificare.py`, `.streamlit/secrets.toml`) | Implemented, optional |
| **ElevenLabs** | The "Listen" button: the agent reads its explanation aloud (`services/voce.py`) | Implemented, optional |
| **Tiger Data** | Cloud PostgreSQL via `DATABASE_URL`, with migration from SQLite (`scripts/migreaza_in_postgres.py`) | Implemented; the demo uses local SQLite because it is faster |
| **Vultr** | Docker + Caddy (automatic HTTPS) and a step-by-step guide in [PRODUCTIE.md](PRODUCTIE.md); photos in Vultr Object Storage (`services/stocare.py`) | Ready, **not deployed** (see below) |
| **Living Labs** | In-app survey and a "What's new" page (`views/comunitate.py`) | Implemented |

### About the Vultr deployment

We wanted to publish the app on **Vultr** (Cloud Compute, Frankfurt, Docker image). Everything needed for that is in
the repo: `Dockerfile`, `docker-compose.yml`, `Caddyfile` (automatic HTTPS with Let's Encrypt) and the steps in
[PRODUCTIE.md](PRODUCTIE.md). **The Vultr account was not activated in time** during the hackathon, so we could not
start the server. For the demo we run the app locally on a laptop, and the phones connect over the same Wi-Fi
network. Once the account is activated, deployment takes three commands:

```bash
git clone https://github.com/Petruse18/skillio_final.git && cd skillio_final
nano .env                       # the keys + DOMENIU=skillio.example.com
docker compose up -d --build
```

---

## Business model

- **10%** commission from the tradesperson, only on completed jobs (no fees for leads received).
- **5%** protection fee paid by the client; it funds the human mediators (like insurance).
- On a 300 lei job: **45 lei** revenue, about 6 lei for payment processing. Even if 20% of jobs end up in mediation,
  about 27 lei per job remain.
- **SOS**: 45 lei, of which 35 lei go to the tradesperson.
- Comparison: Airtasker 10-20%, Urban Company 8.5-25%.
- **Launch**: one neighbourhood (Elisabetin), 2-3 trades, then expansion neighbourhood by neighbourhood.

## What changes for production

- **Payment**: escrow goes through a licensed payment processor (Stripe Connect, Mangopay or Lemonway) instead of
  Solana devnet, without needing our own payment institution licence.
- **SOS call**: in the demo, video via a public Jitsi server. In production, a WebRTC service with recording
  (Daily, Twilio Video), EU storage and automatic deletion after 30 days.
- **GDPR**: explicit consent for recordings, deletion after 30 days, data stored in the EU.
- **Still an open problem**: repeat jobs done outside the platform after the first meeting.

---

## Quick start

You need **Python 3.10+**.

```bash
python -m venv .venv
.venv\Scripts\activate            # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # then fill in the keys (Mac/Linux: cp)
streamlit run app.py
```

On Windows you can also use `porneste.bat`. On first launch, `data/skillio.db` is created with demo data.

| Address | What you see |
|---|---|
| http://localhost:8501 | the app, with the sign-in screen |
| http://localhost:8501/?mod=prezentare | **presentation mode**: the client and the tradesperson side by side, plus the time buttons (+1 day, etc.) |

**On two phones:** start with `streamlit run app.py --server.address 0.0.0.0`, then open the "Network URL" shown in
the terminal on the phones (same Wi-Fi network or hotspot). Without HTTPS, the browser microphone may be blocked on
phones; photo and video uploads still work.

### Demo accounts

| Account | Phone | Role |
|---|---|---|
| Ana Popescu | +40722000001 | client, Elisabetin |
| Ionel Mureșan | +40722000101 | plumber and boiler technician |
| Admin | +40700000000 | mediation, statistics, demo controls |

### Keys (in `.env`, which is never pushed to GitHub)

| Variable | Used for | Without it |
|---|---|---|
| `GEMINI_API_KEY`, `GEMINI_MODEL` | everything AI-related | built-in rules (keywords, price tables) |
| `SOLANA_SECRET_KEY` | escrow on devnet (`python -m scripts.solana_portofel`) | simulated payment |
| `ELEVENLABS_API_KEY` | the agent's voice | the browser's voice |
| `DATABASE_URL` | PostgreSQL (Tiger Data) | local SQLite (recommended for the demo) |
| `DEMO_LOGIN`, `MOD_PREZENTARE` | demo account buttons and presentation mode | – |
| `DOMENIU` | the domain for HTTPS on the server | – |

Auth0 is configured in `.streamlit/secrets.toml` (which also stays local only).

---

## Demo scenario (3 minutes)

1. **The agent**: Ana taps the example "Bathroom renovated by 20 December, budget 9000 lei". Four stages appear, the
   cost, "How we calculated" (with live prices) and the **scheduled team**: plumber, electrician, tiler, painter, on
   days in the correct order, with the budget check.
2. **Escrow payment**: Ionel sends an offer, Ana pays. The money is locked (+5% protection, shown on screen).
3. **Reconfirmation**: Ionel arrives, takes a photo and asks for 260 lei instead of 200. Gemini: "reasonable price".
   Ana can accept, or refuse and pay only 40 lei.
4. **Chat**: Ana types a phone number, and SKILLIO hides it.
5. **Confirmation + 24 h**: both confirm, the money stays locked for 24 h. If a dispute is opened, the admin decides
   in Mediation.
6. **SOS for 45 lei**: a video call with a real tradesperson, recorded with consent.

---

## Technologies

- **Python 3.11 + Streamlit 1.67**, a mobile-first interface (bottom navigation, cards, custom theme).
- **SQLite** (demo) or **PostgreSQL** (Tiger Data) with `psycopg_pool`.
- **Gemini** via `google-genai`: multimodal, function calling, Google Search grounding.
- **Solana devnet** (`solders`), **Auth0**, **ElevenLabs**.
- **Docker + Caddy** for the server, ready for Vultr.
- About **5,000 lines of actual Python** and 400 lines of CSS.

## Project structure

```
app.py                  entry point, bottom navigation, sync between phones
core/config.py          business rules (commission, fees, SOS, time slots), trades, neighbourhoods
core/db.py              database (SQLite or PostgreSQL)
core/logica.py          the whole flow: requests, offers, escrow, reconfirmation, disputes, SOS, the agent's team
core/trust.py           Trust Score
core/seed.py            demo data
core/timp.py            the app clock (can be moved forward for the demo)
services/ai.py          Gemini: diagnosis, agent, price opinion, live prices, translation
services/unelte.py      the tools (function calling) the agent uses to calculate costs
services/solana.py      escrow on Solana devnet
services/autentificare.py, voce.py, stocare.py, mesaje_externe.py, geo.py
views/                  screens: client, tradesperson, job, assistant (agent), materials, SOS, admin (mediation),
                        common (sign-in, chat, profile), community, presentation
ui/                     components and styles (tokens.css, modern.css, streamlit.css)
scripts/                PostgreSQL migration, backup, Solana wallet, uploading photos to the cloud
pitch/                  demo script, business model, registration text
Dockerfile, docker-compose.yml, Caddyfile, PRODUCTIE.md   server deployment (Vultr)
```

## Trust Score (0-100)

Calculated only from real activity in the app, not from popularity.

| Factor | Points |
|---|---|
| Client ratings | 25 |
| The work lasts (feedback after 1 day, 1 week, 1 month) | 20 |
| Appointments kept | 15 |
| Punctuality | 10 |
| Completed jobs | 10 |
| Verified identity | 10 |
| No confirmed complaints | 10 |

A factor with no data gets half of its points. Levels: 90+ Excellent, 75+ Very good, 60+ Good, otherwise Growing.

---

## Team

| Name | Role |
|---|---|
| Popa Sebastian Petru | Team leader |
| Petruse Rares Stelian | Member |
| Hariton Vlad Mihai | Member |
| Adascalului Sebastian | Member |

New to the code? [GHID.md](GHID.md) (in Romanian) explains the project step by step.
