"""Anomaly — rileva anomalie contestuali su timbrature. **Solo segnalazione**.

Vincolo duro (art. 4 Statuto, `05` §4.2): niente scoring, ranking o giudizio di
produttività individuale. L'agente descrive uno **scostamento fra pianificato e
timbrato**, che è un fatto; non dice se una persona è veloce o lenta.

Se qualcuno chiede una valutazione individuale, la risposta è un rifiuto
esplicito, non una versione più morbida della stessa cosa.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from ..domain.proposta import Proposta
from ..kb.secondo import NotaValutativa, valida
from ..orchestrator.contesto import Contesto
from .base import registra

SOGLIA_SCOSTAMENTO_ORE = 0.5

_DOMANDA_VALUTATIVA = re.compile(
    r"chi (è|e) (il |la )?(più|piu) (lent|veloc|brav|scars)|produttivit|rendimento|"
    r"classific|ranking|valuta(re|zione)|performance di|chi lavora (meno|di più|di piu)",
    re.I,
)


@dataclass(slots=True)
class Timbratura:
    persona: str
    data: dt.date
    ore_piano: float
    ore_timbrate: float

    @property
    def scostamento(self) -> float:
        return round(self.ore_timbrate - self.ore_piano, 2)


class RifiutoArt4(Exception):
    """La domanda chiede una valutazione individuale: non si risponde."""


class Anomaly:
    id = "anomaly"
    usa_llm = True
    modello = "pattern"
    versione_prompt = "anomaly-1"

    def segnala(self, timbrature: list[Timbratura]) -> Proposta:
        segnali = []
        for t in timbrature:
            if abs(t.scostamento) < SOGLIA_SCOSTAMENTO_ORE:
                continue
            verso = "in più" if t.scostamento > 0 else "in meno"
            segnali.append(
                {
                    "persona": t.persona,
                    "data": t.data.isoformat(),
                    "scostamento_ore": t.scostamento,
                    "descrizione": f"{abs(t.scostamento):g}h {verso} rispetto al piano",
                }
            )
        rationale = (
            f"{len(segnali)} scostamenti oltre {SOGLIA_SCOSTAMENTO_ORE:g}h fra piano e timbrature. "
            "Sono fatti da guardare col diretto interessato, non un giudizio."
        )
        valida(rationale)
        return Proposta(
            agente=self.id,
            tipo="segnale",
            payload={"segnali": segnali, "scoring": False},
            rationale=rationale,
            fonti=[],
        )

    def nel_ciclo(self, contesto: Contesto, **fase) -> Proposta:
        timbrature: list[Timbratura] = fase.get("timbrature", [])
        return self.segnala(timbrature)

    def consulta(self, domanda: str, contesto: Contesto, **extra) -> Proposta:
        if _DOMANDA_VALUTATIVA.search(domanda or ""):
            raise RifiutoArt4(
                "Non produco valutazioni individuali: l'art. 4 dello Statuto e la nostra "
                "spec `05` lo escludono. Posso mostrarti scostamenti piano/timbrature."
            )
        p = self.segnala(extra.get("timbrature", []))
        p.payload["domanda"] = domanda
        return p


AGENTE = registra(Anomaly())


def nota_ammessa(testo: str) -> bool:
    try:
        valida(testo)
    except NotaValutativa:
        return False
    return True
