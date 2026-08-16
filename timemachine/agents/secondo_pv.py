"""Secondo del punto vendita — memoria collettiva (`01` §4.6).

Impara **solo** da decisioni umane: accettata / modificata / rifiutata. Non
decide i turni, non giudica le persone. La scrittura è una `Proposta`:
auto-append solo se è un append su `kb/secondo/` che non cancella nulla e non
parla di una persona in modo valutativo; altrimenti serve conferma.
"""

from __future__ import annotations

import datetime as dt

from ..domain.proposta import Decisione, Proposta
from ..kb import secondo as kb_secondo
from ..orchestrator.contesto import Contesto
from .base import registra
from .llm import LLMGiu, SchemaNonRispettato, llm

SCHEMA_MEMORIA = {
    "type": "object",
    "required": ["nota"],
    "properties": {"nota": {"type": "string"}, "argomento": {"type": "string"}},
}


def _distilla_deterministico(decisione: Decisione, settimana: dt.date) -> tuple[str, str]:
    mese = settimana.strftime("%B")
    if decisione.esito == "accettata":
        return ("schemi-che-vanno", f"settimana del {settimana.isoformat()}: bozza accettata senza modifiche.")
    if decisione.esito == "rifiutata":
        motivo = f" — motivo: {decisione.motivo}" if decisione.motivo else ""
        return ("schemi-rifiutati", f"settimana del {settimana.isoformat()}: bozza rifiutata{motivo}.")
    cambi = ", ".join(
        f"{d.get('persona')} {d.get('giorno', d.get('data', ''))}: {d.get('prima')} → {d.get('dopo')}"
        for d in decisione.diff[:6]
    )
    return (
        f"modifiche-{mese.lower()}",
        f"settimana del {settimana.isoformat()}: il manager ha spostato {cambi}." if cambi
        else f"settimana del {settimana.isoformat()}: bozza modificata prima della pubblicazione.",
    )


class SecondoPV:
    id = "secondo-pv"
    usa_llm = True
    modello = "llm-distillazione"
    versione_prompt = "secondo-1"

    def impara(self, decisione: Decisione, settimana: dt.date, contesto: Contesto | None = None) -> Proposta:
        argomento, nota = _distilla_deterministico(decisione, settimana)
        fonte = "codice"
        try:
            dati, _ = llm().genera_json(
                prompt=(
                    "Distilla in una riga il pattern di NEGOZIO che emerge da questa decisione "
                    "del manager. Vietato parlare di singole persone in termini di resa, "
                    "velocità o valore. Solo pattern organizzativi.\n"
                    f"decisione: {decisione.esito}\ndiff: {decisione.diff}\nsettimana: {settimana}"
                ),
                schema=SCHEMA_MEMORIA,
                sistema="secondo-pv: memoria collettiva del punto vendita. Solo JSON.",
            )
            candidata = str(dati.get("nota", "")).strip()
            if candidata and kb_secondo_ammessa(candidata):
                nota = candidata
                argomento = str(dati.get("argomento") or argomento)
                fonte = "llm"
        except (LLMGiu, SchemaNonRispettato):
            pass  # il pattern deterministico basta: il loop non dipende dal modello

        auto = kb_secondo_ammessa(nota)
        return Proposta(
            agente=self.id,
            tipo="memoria",
            payload={
                "argomento": argomento,
                "nota": nota,
                "auto_append": auto,
                "fonte_testo": fonte,
            },
            rationale=(
                "Append automatico: non cancella nulla e non parla di una persona in modo valutativo."
                if auto
                else "Serve conferma: la nota tocca una persona in modo valutativo."
            ),
            fonti=[f"kb/turni/{settimana.isoformat()}.md"],
        )

    def applica(self, proposta: Proposta, quando: str = "") -> str | None:
        """Append-only. Se non è auto-accettabile, non scrive."""
        if not proposta.payload.get("auto_append"):
            return None
        p = kb_secondo.append(
            argomento=proposta.payload["argomento"],
            testo=proposta.payload["nota"],
            fonti=proposta.fonti,
            quando=quando,
        )
        return str(p)

    def nel_ciclo(self, contesto: Contesto, **fase) -> Proposta:
        decisione: Decisione | None = fase.get("decisione")
        if decisione is None:
            raise ValueError("secondo-pv impara da una decisione umana, non dal nulla")
        return self.impara(decisione, contesto.settimana, contesto)

    def consulta(self, domanda: str, contesto: Contesto, **extra) -> Proposta:
        termini = [t for t in (domanda or "").lower().split() if len(t) > 3]
        note = kb_secondo.retrieval(termini, limite=5)
        return Proposta(
            agente=self.id,
            tipo="risposta",
            payload={"domanda": domanda, "note": note},
            rationale=(
                f"{len(note)} note pertinenti nella memoria del punto vendita."
                if note
                else "Il negozio non ha ancora memoria su questo."
            ),
            fonti=["kb/secondo/"],
        )


def kb_secondo_ammessa(testo: str) -> bool:
    from .anomaly import nota_ammessa

    return nota_ammessa(testo)


AGENTE = registra(SecondoPV())
