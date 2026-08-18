"""Password — hash bcrypt cost ≥ 12 (`07` §3).

Mai in `kb/`, mai in log, mai in una risposta. La verifica ha un costo
costante-ish: è quella che allinea i tempi in L9 (nessun indizio su chi esiste).
"""

from __future__ import annotations

import re

import bcrypt

COSTO = 12
LUNGHEZZA_MINIMA = 10

#: hash finto su cui verificare quando l'account non esiste: stessa spesa CPU,
#: nessun canale temporale che riveli l'esistenza di un utente (L9).
_ESCA = bcrypt.hashpw(b"esca-per-timing", bcrypt.gensalt(rounds=COSTO))

_BANALI = re.compile(r"^(password|lerocce|timemachine|123456|qwerty)", re.I)


class PasswordDebole(ValueError):
    pass


def valida(password: str, email: str = "", uid: str = "") -> None:
    if len(password or "") < LUNGHEZZA_MINIMA:
        raise PasswordDebole(f"almeno {LUNGHEZZA_MINIMA} caratteri")
    basso = password.lower()
    if email and basso == email.lower():
        raise PasswordDebole("non può essere la tua email")
    if uid and basso == uid.lower():
        raise PasswordDebole("non può essere il tuo uid")
    if _BANALI.match(basso) or basso.startswith("lerocce"):
        raise PasswordDebole("troppo prevedibile")
    if len(set(basso)) < 5:
        raise PasswordDebole("troppo ripetitiva")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=COSTO)).decode("ascii")


def verifica(password: str, hash_atteso: str | None) -> bool:
    atteso = (hash_atteso or "").encode("ascii") or _ESCA
    try:
        ok = bcrypt.checkpw((password or "").encode("utf-8"), atteso)
    except ValueError:
        bcrypt.checkpw((password or "").encode("utf-8"), _ESCA)
        return False
    return bool(hash_atteso) and ok
