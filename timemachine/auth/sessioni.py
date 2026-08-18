"""Sessioni — cookie httpOnly, secure, SameSite=Lax (`07` §4.4, `05` §4.5).

Niente token lunghi in localStorage. Rotazione dell'id all'attivazione e al
login. Il logout è visibile nel guscio.
"""

from __future__ import annotations

import datetime as dt
import secrets
from dataclasses import dataclass, field

from ..kb import persone as kb_persone
from ..security.authz import ANONIMO, Attore

NOME_COOKIE = "tm_sessione"
DURATA_ORE = 12


@dataclass(slots=True)
class Sessione:
    id: str
    persona: str
    creata_at: dt.datetime
    scade_at: dt.datetime

    def valida(self, adesso: dt.datetime | None = None) -> bool:
        return (adesso or dt.datetime.now(dt.UTC)) < self.scade_at


@dataclass(slots=True)
class Registro:
    sessioni: dict[str, Sessione] = field(default_factory=dict)

    def apri(self, persona: str) -> Sessione:
        adesso = dt.datetime.now(dt.UTC)
        s = Sessione(
            id=secrets.token_urlsafe(32),
            persona=persona,
            creata_at=adesso,
            scade_at=adesso + dt.timedelta(hours=DURATA_ORE),
        )
        self.sessioni[s.id] = s
        return s

    def ruota(self, vecchia_id: str | None, persona: str) -> Sessione:
        if vecchia_id:
            self.sessioni.pop(vecchia_id, None)
        return self.apri(persona)

    def chiudi(self, sessione_id: str | None) -> None:
        if sessione_id:
            self.sessioni.pop(sessione_id, None)

    def attore(self, sessione_id: str | None) -> Attore:
        if not sessione_id:
            return ANONIMO
        s = self.sessioni.get(sessione_id)
        if s is None or not s.valida():
            self.sessioni.pop(sessione_id, None)
            return ANONIMO
        persona = kb_persone.leggi(s.persona)
        ruoli = tuple(persona.ruoli) if persona and persona.ruoli else ("dipendente",)
        if "dipendente" not in ruoli:
            ruoli = ("dipendente", *ruoli)
        return Attore(slug=s.persona, ruoli=ruoli)

    def svuota(self) -> None:
        self.sessioni.clear()


REGISTRO = Registro()


def cookie_kwargs() -> dict:
    """`Secure` di default.

    `TM_COOKIE_INSICURO=1` lo toglie: serve **solo** in sviluppo, perché un
    client non-browser (curl, httpx, uno script di prova) su `http://` non
    manda i cookie `Secure` e la sessione sembra sparire. In produzione resta
    acceso: senza TLS la sessione viaggia in chiaro (`05` §4.5).
    """
    import os

    return {
        "httponly": True,
        "secure": os.environ.get("TM_COOKIE_INSICURO", "") not in ("1", "true", "si"),
        "samesite": "lax",
        "max_age": DURATA_ORE * 3600,
        "path": "/",
    }
