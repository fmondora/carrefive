"""Porta `Saldi` — un contratto, due adapter (`04` §3, §4.3).

Il flag di punto vendita `SALDI_FONTE=file|gamma` decide quale gira.
La UI e lo Scheduling non lo sanno: nessun `if` in `person-shifts`.
"""

from __future__ import annotations

import os

from ..domain.saldi import PortaSaldi, Saldo
from .adapter_file import AdapterFile
from .adapter_gamma import AdapterGamma, ClientGammaHTTP, ErroreGamma

_porta: PortaSaldi | None = None


def porta() -> PortaSaldi:
    global _porta
    if _porta is not None:
        return _porta
    if os.environ.get("SALDI_FONTE", "file").lower() == "gamma":
        _porta = AdapterGamma(client=ClientGammaHTTP())
    else:
        _porta = AdapterFile()
    return _porta


def imposta_porta(p: PortaSaldi | None) -> None:
    """Config di punto vendita / test. Non è un atto d'agente."""
    global _porta
    _porta = p


def di(persona: str) -> list[Saldo]:
    return porta().di(persona)


def aggiornati_at(persona: str) -> str | None:
    return porta().aggiornati_at(persona)


def stale(persona: str) -> bool:
    return porta().stale(persona)


__all__ = [
    "AdapterFile",
    "AdapterGamma",
    "ClientGammaHTTP",
    "ErroreGamma",
    "PortaSaldi",
    "Saldo",
    "aggiornati_at",
    "di",
    "imposta_porta",
    "porta",
    "stale",
]
