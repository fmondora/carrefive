"""Il parametro `state` degli OAuth, fatto sul serio (`05` §4.6 CSRF).

Senza uno `state` imprevedibile e a uso singolo, un callback OAuth è una GET
che chiunque può far partire dal browser di qualcun altro: login CSRF (entri
nell'account di un attaccante senza accorgertene) o consenso replayato.

Regole:

- valore da `secrets.token_urlsafe(32)` (256 bit), mai un valore parlante;
- **uso singolo** e scadenza corta;
- legato allo *scopo* (login ≠ attivazione ≠ calendario) e, quando c'è, alla
  sessione che ha avviato il giro;
- i dati sensibili (token d'invito, slug) stanno **qui**, non nell'URL: nel
  `state` viaggia solo un identificatore opaco.
"""

from __future__ import annotations

import datetime as dt
import secrets
from dataclasses import dataclass, field

DURATA_MINUTI = 10
SCOPI = ("login", "attivazione", "calendario")


class StatoNonValido(PermissionError):
    """State assente, scaduto, già usato, di un altro scopo o di un'altra sessione."""


@dataclass(frozen=True, slots=True)
class Stato:
    valore: str
    scopo: str
    dati: str
    sessione: str
    scade_at: dt.datetime

    def valido(self, adesso: dt.datetime | None = None) -> bool:
        return (adesso or dt.datetime.now(dt.UTC)) < self.scade_at


@dataclass(slots=True)
class Registro:
    stati: dict[str, Stato] = field(default_factory=dict)

    def crea(self, scopo: str, dati: str = "", sessione: str = "") -> str:
        if scopo not in SCOPI:
            raise ValueError(f"scopo OAuth sconosciuto: {scopo}")
        self._pulisci()
        valore = secrets.token_urlsafe(32)
        self.stati[valore] = Stato(
            valore=valore,
            scopo=scopo,
            dati=dati,
            sessione=sessione or "",
            scade_at=dt.datetime.now(dt.UTC) + dt.timedelta(minutes=DURATA_MINUTI),
        )
        return valore

    def consuma(self, valore: str, scopo: str, sessione: str = "") -> Stato:
        """Verifica e **brucia** lo state. Un replay non passa due volte."""
        stato = self.stati.pop(valore or "", None)
        if stato is None or not stato.valido():
            raise StatoNonValido("state OAuth assente, scaduto o già usato")
        if not secrets.compare_digest(stato.scopo, scopo):
            raise StatoNonValido("state OAuth di un altro flusso")
        if stato.sessione and not secrets.compare_digest(stato.sessione, sessione or ""):
            raise StatoNonValido("state OAuth di un'altra sessione")
        return stato

    def _pulisci(self) -> None:
        adesso = dt.datetime.now(dt.UTC)
        for valore, stato in list(self.stati.items()):
            if not stato.valido(adesso):
                del self.stati[valore]

    def svuota(self) -> None:
        self.stati.clear()


REGISTRO = Registro()
