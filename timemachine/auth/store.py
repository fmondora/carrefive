"""Store degli account e dei token di attivazione (`07` §3, `05` §4.5).

Password (hash) e token **fuori da `kb/`**: qui, cifrati a riposo con la stessa
chiave dello store Google. Del token di attivazione si salva solo l'**hash**:
un dump dello store non permette di attivare nessuno.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from ..calendario.store import _chiave  # stessa chiave, stesso confine
from ..kb.paths import stato_root


@dataclass(slots=True)
class Account:
    persona: str
    uid: str = ""
    email: str = ""
    password_hash: str = ""
    google_sub: str = ""
    stato: str = "invitata"  # invitata | attiva | sospesa
    creato_at: str = ""
    ultimo_login: str = ""

    @property
    def attiva(self) -> bool:
        return self.stato == "attiva"


@dataclass(slots=True)
class Invito:
    token_hash: str
    persona: str
    email: str = ""
    via: str = "email"  # email | qr
    creato_at: str = ""
    scade_at: str = ""
    usato: bool = False
    revocato: bool = False

    def valido(self, adesso: dt.datetime | None = None) -> bool:
        if self.usato or self.revocato:
            return False
        adesso = adesso or dt.datetime.now(dt.UTC)
        try:
            return adesso < dt.datetime.fromisoformat(self.scade_at)
        except ValueError:
            return False


def _file() -> Path:
    return stato_root() / "account.enc"


def _leggi() -> dict[str, Any]:
    p = _file()
    if not p.exists():
        return {"account": {}, "inviti": {}}
    try:
        return json.loads(Fernet(_chiave()).decrypt(p.read_bytes()).decode("utf-8"))
    except (InvalidToken, ValueError):
        return {"account": {}, "inviti": {}}


def _scrivi(dati: dict[str, Any]) -> None:
    p = _file()
    p.write_bytes(Fernet(_chiave()).encrypt(json.dumps(dati).encode("utf-8")))
    p.chmod(0o600)


def impronta(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- account -----------------------------------------------------------------


def salva_account(a: Account) -> None:
    dati = _leggi()
    dati["account"][a.persona] = asdict(a)
    _scrivi(dati)


def account(persona: str) -> Account | None:
    d = _leggi()["account"].get(persona)
    return Account(**d) if d else None


def tutti_account() -> list[Account]:
    return [Account(**d) for d in _leggi()["account"].values()]


def per_uid(uid: str) -> Account | None:
    uid = (uid or "").strip().lower()
    for a in tutti_account():
        if a.uid.lower() == uid or a.email.lower() == uid:
            return a
    return None


def per_google_sub(sub: str) -> Account | None:
    for a in tutti_account():
        if sub and a.google_sub == sub:
            return a
    return None


def cancella_account(persona: str) -> bool:
    dati = _leggi()
    if persona in dati["account"]:
        del dati["account"][persona]
        _scrivi(dati)
        return True
    return False


# --- inviti ------------------------------------------------------------------


def salva_invito(i: Invito) -> None:
    dati = _leggi()
    dati["inviti"][i.token_hash] = asdict(i)
    _scrivi(dati)


def invito(token: str) -> Invito | None:
    d = _leggi()["inviti"].get(impronta(token))
    return Invito(**d) if d else None


def inviti_di(persona: str) -> list[Invito]:
    return [Invito(**d) for d in _leggi()["inviti"].values() if d["persona"] == persona]


def aggiorna_invito(i: Invito) -> None:
    salva_invito(i)


def revoca_inviti(persona: str) -> int:
    dati = _leggi()
    n = 0
    for chiave, d in dati["inviti"].items():
        if d["persona"] == persona and not d["usato"] and not d["revocato"]:
            d["revocato"] = True
            n += 1
    _scrivi(dati)
    return n


def svuota() -> None:
    _scrivi({"account": {}, "inviti": {}})
