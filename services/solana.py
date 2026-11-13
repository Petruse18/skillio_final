"""Plata blocată (escrow) pe blockchain-ul Solana, rețeaua de test „devnet”.

Cum funcționează (custodial, ca la orice marketplace):
    - platforma are un portofel (SOLANA_SECRET_KEY) și un „seif” (escrow) derivat din el;
    - clientul plătește → mutăm suma din portofelul platformei în seif   (tranzacția „lock”);
    - clientul confirmă lucrarea → din seif, 90% merg la meșter și 10% la platformă (tranzacția „release”);
    - anulare / dispută câștigată de client → suma se întoarce din seif (tranzacția „refund”).
Fiecare tranzacție are un memo („SKILLIO lock #12 230 lei”) și un link public pe Solana Explorer.
La eliberare, memo-ul conține și amprenta lucrării (sha256), adică „pașaportul” ei on-chain.

Sumele sunt simbolice: 1 leu = SOL_PER_LEU SOL (implicit 0,0001), pe devnet, unde SOL-ul nu are valoare.
Fără SOLANA_SECRET_KEY în .env (sau fără internet), plata rămâne simulată, ca înainte.
"""
import base64
import hashlib
import json
import logging
import threading
import time

import requests

from core import config

log = logging.getLogger("skillio.solana")
LAMPORTS = 1_000_000_000
MEMO_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
REZERVA_SEIF = 1_000_000          # 0,001 SOL ținuți în seif ca să nu scadă sub minimul de „rent”
ULTIMELE: list[dict] = []


_OK: bool | None = None


def activ() -> bool:
    """Pornit doar dacă există cheia, pachetul solders e instalat și cheia se poate citi."""
    global _OK
    if not config.SOLANA_SECRET_KEY:
        return False
    if _OK is None:
        try:
            _platforma()
            _OK = True
        except Exception as e:                      # lipsește solders sau cheia e greșită
            log.warning("Solana oprit: %s", e)
            _OK = False
    return _OK


def link_tx(sig: str) -> str:
    return f"https://explorer.solana.com/tx/{sig}?cluster={config.SOLANA_CLUSTER}"


def link_adresa(adr: str) -> str:
    return f"https://explorer.solana.com/address/{adr}?cluster={config.SOLANA_CLUSTER}"


def lamports(suma_lei: float) -> int:
    return int(round(suma_lei * config.SOL_PER_LEU * LAMPORTS))


# --- chei -------------------------------------------------------------------
def _platforma():
    from solders.keypair import Keypair
    k = config.SOLANA_SECRET_KEY.strip()
    if k.startswith("["):                          # format JSON (solana-keygen / Phantom export)
        return Keypair.from_bytes(bytes(json.loads(k)))
    return Keypair.from_base58_string(k)


def _derivat(eticheta: str):
    from solders.keypair import Keypair
    return Keypair.from_seed(hashlib.sha256(bytes(_platforma()) + eticheta.encode()).digest())


def seif():
    return _derivat("skillio-escrow")


def portofel_mester(mester_id: int, adresa_proprie: str | None = None) -> str:
    """Adresa unde primește meșterul: a lui, dacă a pus-o în profil, altfel una creată de platformă."""
    if adresa_proprie:
        return adresa_proprie.strip()
    return str(_derivat(f"skillio-mester-{mester_id}").pubkey())


def adresa_platforma() -> str:
    return str(_platforma().pubkey()) if activ() else ""


# --- RPC ----------------------------------------------------------------------
def _rpc(metoda, params):
    r = requests.post(config.SOLANA_RPC, json={"jsonrpc": "2.0", "id": 1, "method": metoda, "params": params},
                      timeout=20)
    r.raise_for_status()
    d = r.json()
    if "error" in d:
        raise RuntimeError(d["error"].get("message", str(d["error"])))
    return d["result"]


def sold(adresa: str) -> float:
    return _rpc("getBalance", [adresa, {"commitment": "confirmed"}])["value"] / LAMPORTS


def cere_airdrop(adresa: str, sol: float = 1.0) -> str:
    return _rpc("requestAirdrop", [adresa, int(sol * LAMPORTS)])


def _memo(text):
    from solders.instruction import Instruction
    from solders.pubkey import Pubkey
    return Instruction(Pubkey.from_string(MEMO_ID), text.encode("utf-8")[:500], [])


def _transfer(de, catre: str, lam: int):
    from solders.pubkey import Pubkey
    from solders.system_program import TransferParams, transfer
    return transfer(TransferParams(from_pubkey=de, to_pubkey=Pubkey.from_string(catre), lamports=lam))


def construieste(instructiuni, semnatari, blockhash: str) -> bytes:
    """Tranzacția semnată, gata de trimis (primul semnatar plătește taxa)."""
    from solders.hash import Hash
    from solders.message import Message
    from solders.transaction import Transaction
    h = Hash.from_string(blockhash)
    msg = Message.new_with_blockhash(instructiuni, semnatari[0].pubkey(), h)
    return bytes(Transaction(semnatari, msg, h))


def _trimite(instructiuni, semnatari) -> str:
    bh = _rpc("getLatestBlockhash", [{"commitment": "finalized"}])["value"]["blockhash"]
    tx = construieste(instructiuni, semnatari, bh)
    sig = _rpc("sendTransaction", [base64.b64encode(tx).decode(), {"encoding": "base64",
                                                                    "preflightCommitment": "confirmed"}])
    for _ in range(30):                              # așteptăm confirmarea (max ~15 s)
        st = _rpc("getSignatureStatuses", [[sig]])["value"][0]
        if st and st.get("err"):
            raise RuntimeError(f"Tranzacția a eșuat: {st['err']}")
        if st and st.get("confirmationStatus") in ("confirmed", "finalized"):
            return sig
        time.sleep(0.5)
    return sig


def _jurnal(tip, ok, detaliu):
    ULTIMELE.insert(0, {"tip": tip, "ok": ok, "detaliu": str(detaliu)[:200], "la": time.strftime("%H:%M:%S")})
    del ULTIMELE[30:]


# --- operațiile de escrow ----------------------------------------------------
def blocheaza(lid: int, suma_lei: float) -> tuple[str, int]:
    """Platforma → seif. Întoarce (semnătura, lamports)."""
    p, s = _platforma(), seif()
    lam = lamports(suma_lei)
    ix = [_transfer(p.pubkey(), str(s.pubkey()), lam)]
    if sold(str(s.pubkey())) * LAMPORTS < REZERVA_SEIF:
        ix.append(_transfer(p.pubkey(), str(s.pubkey()), REZERVA_SEIF))
    ix.append(_memo(f"SKILLIO lock #{lid} {suma_lei:.0f} lei"))
    sig = _trimite(ix, [p])
    _jurnal("lock", True, sig)
    return sig, lam


def elibereaza(lid: int, lam: int, catre_mester: str, amprenta: str) -> str:
    """Seif → meșter (minus comision) și platformă (comision), cu pașaportul lucrării în memo."""
    p, s = _platforma(), seif()
    com = int(lam * config.COMISION)
    ix = [_transfer(s.pubkey(), catre_mester, lam - com), _transfer(s.pubkey(), str(p.pubkey()), com),
          _memo(f"SKILLIO release #{lid} passport sha256:{amprenta}")]
    sig = _trimite(ix, [p, s])
    _jurnal("release", True, sig)
    return sig


def returneaza(lid: int, lam: int) -> str:
    p, s = _platforma(), seif()
    sig = _trimite([_transfer(s.pubkey(), str(p.pubkey()), lam), _memo(f"SKILLIO refund #{lid}")], [p, s])
    _jurnal("refund", True, sig)
    return sig


def in_fundal(nume, functie, dupa):
    """Rulează o operație on-chain fără să blocheze ecranul; `dupa(rezultat)` salvează semnătura."""
    def lucru():
        try:
            dupa(functie())
        except Exception as e:
            log.warning("Solana %s eșuat: %s", nume, e)
            _jurnal(nume, False, e)
    threading.Thread(target=lucru, daemon=True).start()


def amprenta_lucrare(l: dict, plati: list[dict]) -> str:
    """Amprenta (sha256) a datelor esențiale ale lucrării: pașaportul ei."""
    date = {"id": l["id"], "meserie": l["meserie"], "titlu": l["titlu"], "client": l["client_id"],
            "mester": l["mester_id"], "programat_la": l["programat_la"], "sosit_la": l["sosit_la"],
            "confirmat_la": l["confirmat_la"], "plati": [(p["tip"], p["suma"]) for p in plati]}
    return hashlib.sha256(json.dumps(date, sort_keys=True, default=str).encode()).hexdigest()
