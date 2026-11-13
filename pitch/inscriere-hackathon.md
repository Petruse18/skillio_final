# Textul de înscriere (UniHack 2026)

> **Înainte să trimiți:** la „Side quests” lasă doar ce ai **pornit cu cheie reală** și ai văzut mergând (Admin →
> Integrări și producție arată „conectat”). Un side quest trecut fără să fie pornit te poate costa credibilitate.
> Nokia rămâne la „simulat”, scris cinstit. Completează `[...]` cu linkurile tale.

---

## English (for the submission form)

**Name:** SKILLIO

**Tagline:** Find skills. Build trust. Verified local handymen, with your money held until the job holds.

**Track:** Connected Communities

**The problem.** In Timișoara, finding a good plumber or electrician still runs on word of mouth. People call strangers
from classifieds, pay up front, and have no recourse when the repair fails a week later. Good tradespeople have no way to
prove they are good, so they compete on price and lose work to whoever answers the phone first.

**What SKILLIO does.**

1. **Describe it, snap a photo.** Gemini reads the photo and the description, names the trade you need, how urgent it is
   and a fair price range. A "Listen" button reads the diagnosis and the offers aloud (ElevenLabs), for people who struggle
   with small text.
2. **Get offers from nearby pros.** Tradespeople in your area see the request on a map and send a fixed price plus a slot
   from their calendar. Urgent requests cost +15% and go to the top.
3. **Choose on trust, not on stars.** Every pro has an explainable **Trust Score (0-100)** built from 7 factors: average
   rating, *whether the work still holds after 1 day, 1 week and 1 month*, appointments kept, punctuality, completed jobs,
   verified phone number and SIM, and confirmed complaints. You can open the score and see every factor.
4. **Pay safely.** The payment is held in escrow until the client confirms the job. Each lock, release (90% pro / 10%
   platform) and refund is a public **Solana devnet** transaction with an explorer link, and the final release carries the
   job's sha256 "passport" in its memo.
5. **Arrival you can trust.** "I've arrived" is checked against the pro's location (Nokia Network as Code location,
   SIM-swap and number verification; simulated in this build).
6. **Trust that grows over time.** Follow-up questions after a day, a week and a month feed the score, so durable work
   wins. Both sides can report problems; an admin panel resolves disputes.

**Living Labs.** We built SKILLIO with people from Timișoara: an in-app survey plus a public form reached [N] people
([X] clients, [Y] tradespeople). Average ease of ordering: [a]/5, trust in escrow payment: [b]/5. A "What's new" page in
the app shows each version and why we made it.

**Business model.** 10% commission on completed jobs, taken only when the client confirms. +15% urgent surcharge.
Pros get guaranteed payment and a portable reputation; clients get protection and transparency.

**How we built it.** Python + Streamlit (mobile-first UI), SQLite locally / PostgreSQL in production, folium maps.
Gemini (google-genai) for photo diagnosis; Solana (solders + JSON-RPC) for on-chain escrow; ElevenLabs for speech;
Auth0 for login; Tiger Data (PostgreSQL) for the database; Vultr for the server (Docker + Caddy HTTPS) and object storage
for photos; email/SMS notifications. Every integration is optional and the UI always labels a check as "live" or
"simulated", so the demo never pretends.

**Challenges.** Keeping two phones in sync live for the demo (a DB version counter + 2-second fragments); one codebase
that runs on SQLite and PostgreSQL; making escrow verifiable without asking non-crypto users to own a wallet (custodial
vault derived from the platform key, pros can optionally add their own address).

**What's next.** Pilot in one neighbourhood (Elisabetin/Fabric) with 10-15 recruited pros; real RON payments through a
payment processor with Solana kept as the public proof layer; live Nokia network checks.

**Side quests:** *(keep only the ones that are live)* Gemini · Solana · ElevenLabs · Auth0 · Tiger Data · Vultr ·
Living Labs · DEV (article: [link])

**Links:** Demo video [link] · Repo [link] · Live app [link]

---

## Română (dacă formularul e în română)

**SKILLIO: Find skills. Build trust.** Aplicația care te leagă de meșteri verificați din cartierul tău, cu banii
blocați până confirmi că lucrarea e bună.

Descrii problema și pui o poză; Gemini îți spune ce meșter îți trebuie și cât ar costa (și ți-o citește cu voce, prin
ElevenLabs). Meșterii din zonă trimit oferte cu preț fix și oră din calendar. Alegi după **Trust Score** (0-100, 7 factori
pe care îi vezi pe rând, inclusiv dacă lucrările mai țin după o lună). Plătești, dar banii stau blocați; blocarea și
eliberarea (90% meșter, 10% SKILLIO) sunt tranzacții publice pe **Solana devnet**, cu pașaportul lucrării în memo.
Sosirea meșterului e verificată după locație (Nokia, simulat în această versiune). Feedback-ul după o zi, o săptămână și
o lună construiește scorul. Am testat-o cu [N] oameni din Timișoara, iar pagina „Ce e nou” arată ce am schimbat după ei.

Model: 10% comision la lucrările confirmate, +15% la urgențe. Stack: Python, Streamlit, PostgreSQL (Tiger Data), Gemini,
Solana, ElevenLabs, Auth0, Vultr.
