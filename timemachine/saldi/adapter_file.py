"""Adapter `file` — la fonte di *ora* (`04` §4.2).

Legge lo snapshot in `kb/saldi/{slug}.md`. Se non c'è: vuoto onesto, non zeri.
"""

from __future__ import annotations

from ..domain.saldi import Saldo
from ..kb import saldi as kb_saldi


class AdapterFile:
    nome = "file"

    def di(self, persona: str) -> list[Saldo]:
        return kb_saldi.leggi(persona)

    def aggiornati_at(self, persona: str) -> str | None:
        return kb_saldi.aggiornati_at(persona)

    def stale(self, persona: str) -> bool:
        return False
