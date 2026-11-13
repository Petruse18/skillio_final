"""Pregătește portofelul Solana (devnet) al platformei.

    python -m scripts.solana_portofel           -> dacă nu ai cheie: creează una și îți spune ce pui în .env
                                                   dacă ai cheie: arată adresele și soldul, cere SOL de test
Pe devnet SOL-ul e gratuit și fără valoare. Dacă cererea automată e refuzată (limită), intră pe
https://faucet.solana.com, lipește adresa platformei și cere 5 SOL.
"""
from core import config
from services import solana


def main():
    if not solana.activ():
        from solders.keypair import Keypair
        k = Keypair()
        print("Nu ai încă un portofel. Am creat unul nou. Pune rândul ăsta în .env (și nu-l arăta nimănui):\n")
        print(f"SOLANA_SECRET_KEY={k}\n")
        print(f"Adresa publică (pentru faucet.solana.com): {k.pubkey()}")
        return
    adr = solana.adresa_platforma()
    print(f"Rețea:            {config.SOLANA_CLUSTER} ({config.SOLANA_RPC})")
    print(f"Platformă:        {adr}\n                  {solana.link_adresa(adr)}")
    print(f"Seif (escrow):    {solana.seif().pubkey()}")
    try:
        print(f"Sold platformă:   {solana.sold(adr):.4f} SOL")
        if solana.sold(adr) < 0.5:
            print("Cer 1 SOL de test...")
            print("Semnătură airdrop:", solana.cere_airdrop(adr, 1))
    except Exception as e:
        print(f"Nu pot vorbi cu rețeaua: {e}\nCere SOL manual pe https://faucet.solana.com pentru adresa de mai sus.")
    print(f"\nO lucrare de 230 lei blochează {solana.lamports(230) / solana.LAMPORTS:.4f} SOL.")


if __name__ == "__main__":
    main()
