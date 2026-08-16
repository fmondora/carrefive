"""Contratto di dominio dei saldi (`04` §4.1).

Un numero uscito da un LLM non è un saldo. Questa struttura la riempiono solo
gli adapter (file, Gamma).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

TIPI_SALDO = ("ferie", "permessi", "rol", "ex_festivita", "banca_ore")

ETICHETTE = {
    "ferie": "Ferie",
    "permessi": "Permessi",
    "rol": "ROL",
    "ex_festivita": "Ex festività",
    "banca_ore": "Banca ore",
}


@dataclass(frozen=True, slots=True)
class Saldo:
    persona: str
    tipo: str
    maturato: float
    goduto: float
    residuo: float
    prenotato_fonte: float = 0.0
    unita: Literal["ore"] = "ore"
    aggiornato_at: str = ""
    fonte: Literal["file", "gamma"] = "file"
    fonte_ref: str = ""

    def residuo_giorni(self, ore_giorno: float | None) -> float | None:
        """Display, non store (`04` §3). Senza `ore_giorno` non si inventa."""
        if not ore_giorno:
            return None
        return round(self.residuo / ore_giorno, 1)


class PortaSaldi(Protocol):
    """La UI e lo Scheduling non sanno quale adapter gira."""

    nome: str

    def di(self, persona: str) -> list[Saldo]: ...

    def aggiornati_at(self, persona: str) -> str | None: ...

    def stale(self, persona: str) -> bool: ...
