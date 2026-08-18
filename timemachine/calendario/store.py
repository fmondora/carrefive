"""Store dei segreti — token OAuth cifrati a riposo (`03` §3, `05` §4.5).

**Mai** in `kb/`, mai in git, mai in un prompt, mai in un log. La chiave di
cifratura si passa come *nome di variabile d'ambiente*; se manca, se ne genera
una in `.stato/` con permessi stretti e si avvisa (dev), perché un token in
chiaro sul disco non è un default accettabile.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from ..kb.paths import stato_root

ENV_CHIAVE = "TM_CHIAVE_STORE"


@dataclass(slots=True)
class TokenGoogle:
    persona: str
    access_token: str
    refresh_token: str
    scadenza: float = 0.0
    google_sub: str = ""
    email: str = ""
    calendario_id: str = ""
    scope: str = ""


def _chiave() -> bytes:
    grezza = os.environ.get(ENV_CHIAVE)
    if grezza:
        # accetta sia una chiave Fernet sia una passphrase
        try:
            Fernet(grezza.encode())
            return grezza.encode()
        except (ValueError, TypeError):
            return base64.urlsafe_b64encode(hashlib.sha256(grezza.encode()).digest())
    p = stato_root() / "chiave-store"
    if not p.exists():
        p.write_bytes(Fernet.generate_key())
        p.chmod(0o600)
    return p.read_bytes()


def _file() -> Path:
    return stato_root() / "token-google.enc"


def _leggi_tutto() -> dict[str, dict[str, Any]]:
    p = _file()
    if not p.exists():
        return {}
    try:
        return json.loads(Fernet(_chiave()).decrypt(p.read_bytes()).decode("utf-8"))
    except (InvalidToken, ValueError):
        return {}


def _scrivi_tutto(dati: dict[str, dict[str, Any]]) -> None:
    p = _file()
    p.write_bytes(Fernet(_chiave()).encrypt(json.dumps(dati).encode("utf-8")))
    p.chmod(0o600)


def salva(token: TokenGoogle) -> None:
    dati = _leggi_tutto()
    dati[token.persona] = asdict(token)
    _scrivi_tutto(dati)


def leggi(persona: str) -> TokenGoogle | None:
    dati = _leggi_tutto().get(persona)
    return TokenGoogle(**dati) if dati else None


def cancella(persona: str) -> bool:
    dati = _leggi_tutto()
    if persona in dati:
        del dati[persona]
        _scrivi_tutto(dati)
        return True
    return False


def collegate() -> list[str]:
    return sorted(_leggi_tutto())


def aggiorna_calendario(persona: str, calendario_id: str) -> None:
    token = leggi(persona)
    if token is None:
        return
    token.calendario_id = calendario_id
    salva(token)
