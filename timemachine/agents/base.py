"""Contratto di un agente (`01` §4.1).

Un agente ha un `id` stabile, un mestiere solo, e produce **`Proposta`** —
mai un side-effect sul mondo. Due invocazioni, stesso schema:

    consult(agente, domanda, contesto)      # non avanza il ciclo
    ciclo.invoca(agente, contesto_di_fase)  # avanza

Un solo agente parla con l'umano: il Copilot (P-L). Gli altri emettono dominio.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.proposta import Proposta
from ..orchestrator.contesto import Contesto
from ..security import audit

ID_AGENTI = ("forecast", "scheduling", "compliance", "anomaly", "copilot", "secondo-pv")


@runtime_checkable
class Agente(Protocol):
    id: str
    usa_llm: bool

    def nel_ciclo(self, contesto: Contesto, **fase) -> Proposta: ...

    def consulta(self, domanda: str, contesto: Contesto, **extra) -> Proposta: ...


class AgenteSconosciuto(KeyError):
    pass


_ROSTER: dict[str, Agente] = {}
_CARICATO = False


def registra(agente: Agente) -> Agente:
    if agente.id not in ID_AGENTI:
        raise AgenteSconosciuto(f"agente fuori roster: {agente.id}")
    _ROSTER[agente.id] = agente
    return agente


def roster() -> dict[str, Agente]:
    """Il roster è chiuso (`01` §4.3): questi sei, non uno di più.

    L'import è pigro ma **completo**: basta che un modulo si registri per primo
    e senza questo passaggio gli altri cinque resterebbero invisibili.
    """
    global _CARICATO
    if not _CARICATO:
        _CARICATO = True
        from . import anomaly, compliance, copilot, forecast, scheduling, secondo_pv  # noqa: F401
    return dict(_ROSTER)


def agente(id_agente: str) -> Agente:
    r = roster()
    if id_agente not in r:
        raise AgenteSconosciuto(id_agente)
    return r[id_agente]


def consult(id_agente: str, domanda: str, contesto: Contesto, **extra) -> Proposta:
    """Consulta: zero side-effect, zero avanzamento di stato (E5, UC-04)."""
    a = agente(id_agente)
    p = a.consulta(domanda, contesto, **extra)
    audit.inferenza(
        agente=a.id,
        proposta_id=p.id,
        input_hash=audit.hash_input({"domanda": domanda, "settimana": str(contesto.settimana)}),
        modello=getattr(a, "modello", "codice"),
        versione_prompt=getattr(a, "versione_prompt", "1"),
        esito="consult",
    )
    return p
