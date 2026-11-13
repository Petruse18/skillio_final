---
title: "We built an Uber for handymen in 36 hours, and made trust the product"
published: false
tags: hackathon, python, streamlit, solana
---

> Draft for dev.to. Replace the `[...]` parts, add 2-3 screenshots (Ctrl+Shift+S in Chrome on the presentation mode
> works well), then set `published: true`.

At UniHack 2026 in Timișoara we picked the **Connected Communities** track and asked a simple question: why is finding a
good plumber still a game of luck?

You call three numbers from a classifieds site. One doesn't answer, one can come next week, one wants cash up front. If
the pipe leaks again in a week, the money is gone. Meanwhile the *good* tradespeople have no way to prove it.

So we built **SKILLIO: Find skills. Build trust.**

## The flow in one paragraph

You describe the problem and add a photo. Gemini names the trade, the urgency and a fair price range, and a "Listen"
button reads it aloud with ElevenLabs. Nearby pros send fixed-price offers with a time slot from their calendar. You pick
one based on an explainable Trust Score, pay, and the money stays in escrow until you confirm the job. Then, after a day,
a week and a month, the app asks: *is it still holding?* That answer feeds the pro's score.

![presentation mode: client and handyman phones side by side]([screenshot])

## An explainable Trust Score

Star ratings are easy to inflate and say nothing about whether a repair lasts. Our score (0-100) is a sum of seven
visible factors:

| Factor | Points |
|---|---|
| Average rating | 25 |
| Work still holds (1 day / 1 week / 1 month follow-ups) | 20 |
| Appointments kept | 15 |
| Punctuality (arrival confirmed by location) | 10 |
| Completed jobs | 10 |
| Verified number + stable SIM | 10 |
| No confirmed complaints | 10 |

A factor with no data yet gets half its points, so new pros aren't punished for being new. Clients can open the score
and read every line, which turned out to matter more than the number itself.

## Escrow you can verify, without asking anyone to own a wallet

We wanted the "your money is held" promise to be checkable, but our users are not crypto users. The solution is a
custodial escrow on **Solana devnet**:

- the platform key (from `.env`) deterministically derives a *vault* keypair and one wallet per pro
  (`Keypair.from_seed(sha256(platform_key + label))`);
- **pay** → platform sends the (symbolic) amount to the vault, with a memo `SKILLIO lock #12`;
- **confirm** → the vault sends 90% to the pro and 10% to the platform in one transaction, and the memo carries a sha256
  "passport" of the job (trade, client, pro, scheduled, arrived and confirmed times, payments);
- **cancel / dispute won by the client** → the vault refunds.

Each step shows an explorer link in the app. We used `solders` to build and sign transactions and plain JSON-RPC
(`getLatestBlockhash`, `sendTransaction`, `getSignatureStatuses`) through `requests`, which kept the dependency list
short. Transactions are sent in a background thread so the UI never waits on the network.

```python
ix = [transfer(TransferParams(from_pubkey=vault.pubkey(), to_pubkey=pro, lamports=lam * 90 // 100)),
      transfer(TransferParams(from_pubkey=vault.pubkey(), to_pubkey=platform, lamports=lam - lam * 90 // 100)),
      memo(f"SKILLIO release #{job_id} passport {passport}")]
```

## Two phones, one laptop

The demo had to show a client and a handyman reacting to each other live. Our "presentation mode" puts two phone-sized
iframes of the same Streamlit app side by side. Every write bumps a version counter in the database, and an
`st.fragment(run_every=2)` on each phone reruns when the counter changes. Time controls (+1 day, +6 days, +23 days) move an
app clock so the 1-week and 1-month follow-ups can be shown in seconds.

## "Live" or "simulated", always on screen

Every integration (Gemini, Solana, ElevenLabs, Auth0, PostgreSQL, S3 photo storage, email/SMS, Nokia network checks) turns
on only when its key is present. Without keys, the app runs fully with simulated results, and every check is labelled
*live* or *simulated*. That made the demo robust to bad Wi-Fi and kept us honest with the judges.

## What people told us

[Living Labs results: N responses, the top worry, one quote, and one change we made because of it.]

## Stack

Python 3.11 · Streamlit 1.67 · SQLite / PostgreSQL (Tiger Data) · folium · Gemini · Solana devnet (solders) ·
ElevenLabs · Auth0 · Docker + Caddy on Vultr.

Repo: [link] · Demo video: [link]

Thanks to LigaAC and everyone who answered our survey at 1 AM.
