"""`Proposta` — l'unico output di un agente (`01` §4.2).

Mai un side-effect sul mondo. Un agente che vuole cambiare qualcosa emette una
Proposta; a muovere lo stato sono l'orchestratore (macchina a stati) e l'umano.

L'output LLM è **input non fidato** (`01` §3): si valida allo schema, e uno
scarto è un evento normale, non un'eccezione da nascondere.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

TipoProposta = Literal["previsione", "bozza-turni", "blocco", "segnale", "risposta", "memoria"]

TIPI = ("previsione", "bozza-turni", "blocco", "segnale", "risposta", "memoria")
AGENTI = ("forecast", "scheduling", "compliance", "anomaly", "copilot", "secondo-pv")


class PropostaInvalida(ValueError):
    """Schema non rispettato: si scarta con motivo, non si renderizza (E8)."""


@dataclass(slots=True)
class Scarto:
    """Ciò che il grounding gate ha buttato, con il perché. Si mostra, non si nasconde."""

    cosa: str
    motivo: str


@dataclass(slots=True)
class Proposta:
    agente: str
    tipo: TipoProposta
    payload: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    fonti: list[str] = field(default_factory=list)
    confidenza: float | None = None
    varianti: list[dict[str, Any]] = field(default_factory=list)
    scarti: list[Scarto] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    creato_at: str = field(default_factory=lambda: dt.datetime.now(dt.UTC).isoformat())

    def __post_init__(self) -> None:
        if self.agente not in AGENTI:
            raise PropostaInvalida(f"agente sconosciuto: {self.agente!r}")
        if self.tipo not in TIPI:
            raise PropostaInvalida(f"tipo di proposta sconosciuto: {self.tipo!r}")
        if self.confidenza is not None and not 0.0 <= self.confidenza <= 1.0:
            raise PropostaInvalida(f"confidenza fuori range: {self.confidenza}")
        if not isinstance(self.payload, dict):
            raise PropostaInvalida("payload deve essere un oggetto")

    def come_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agente": self.agente,
            "creato_at": self.creato_at,
            "tipo": self.tipo,
            "payload": self.payload,
            "rationale": self.rationale,
            "fonti": list(self.fonti),
            "confidenza": self.confidenza,
            "varianti": list(self.varianti),
            "scarti": [{"cosa": s.cosa, "motivo": s.motivo} for s in self.scarti],
        }


@dataclass(slots=True)
class Decisione:
    """L'atto umano che segue una Proposta. Si logga più a lungo dell'inferenza."""

    proposta_id: str
    esito: Literal["accettata", "modificata", "rifiutata", "pubblicata"]
    da: str  # slug della persona che decide
    quando: str = field(default_factory=lambda: dt.datetime.now(dt.UTC).isoformat())
    motivo: str = ""
    diff: list[dict[str, Any]] = field(default_factory=list)
