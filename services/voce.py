"""Citire cu voce (ElevenLabs): diagnosticul AI și ofertele, pentru cine preferă să asculte.

Cu ELEVENLABS_API_KEY în .env: voce naturală, în română (model multilingv).
Fără cheie: folosim vocea din browser (Web Speech API), deci butonul „Ascultă” merge oricum.
"""
import hashlib
import logging

import requests

from core import config

log = logging.getLogger("skillio.voce")
_cache: dict[str, bytes] = {}


def activ() -> bool:
    return bool(config.ELEVENLABS_API_KEY)


def sintetizeaza(text: str) -> bytes | None:
    """MP3 de la ElevenLabs, sau None (fără cheie / eroare)."""
    if not activ() or not text.strip():
        return None
    cheie = hashlib.sha1(text.encode()).hexdigest()
    if cheie in _cache:
        return _cache[cheie]
    try:
        r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}",
                          headers={"xi-api-key": config.ELEVENLABS_API_KEY, "Accept": "audio/mpeg"},
                          json={"text": text[:2500], "model_id": config.ELEVENLABS_MODEL,
                                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
                          timeout=30)
        r.raise_for_status()
    except Exception as e:
        log.warning("ElevenLabs a eșuat: %s", e)
        return None
    if len(_cache) > 100:
        _cache.clear()
    _cache[cheie] = r.content
    return r.content
