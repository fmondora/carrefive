"""Forecast — fabbisogno per reparto e fascia (`01` §4.3).

Niente LLM se la storia basta: la media delle teste presenti nelle ultime
settimane è aritmetica, non ragionamento (`01` §3, costo). L'LLM entra **solo**
per interpretare una nota libera della testata («FESTA PROLOCO») che non è nel
vocabolario noto — e se è giù, il forecast esce lo stesso, senza modificatore.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from ..domain.modelli import Piano
from ..domain.ore import ore_in_fascia
from ..domain.proposta import Proposta
from ..kb import persone as kb_persone
from ..orchestrator.contesto import Contesto
from ..security import allowlist
from .base import registra
from .llm import LLMGiu, SchemaNonRispettato, llm

#: fasce del punto vendita. Non è un orologio: è come si guarda la copertura.
FASCE: tuple[tuple[str, dt.time, dt.time], ...] = (
    ("mattina", dt.time(6), dt.time(12)),
    ("centrale", dt.time(12), dt.time(16)),
    ("pomeriggio", dt.time(16), dt.time(20)),
)

#: note della testata che sappiamo leggere senza modello
MODIFICATORI_NOTI: dict[str, tuple[str, float]] = {
    "shooting": ("preparazione", 1.0),
    "inventario": ("magazzino", 1.0),
    "alzare": ("sala", 1.0),
    "ordine": ("scatolame", 0.5),
    "festa": ("sala", 1.0),
    "sagra": ("sala", 1.0),
    "proloco": ("sala", 1.0),
}

SCHEMA_NOTA = {
    "type": "object",
    "required": ["reparto", "teste_extra"],
    "properties": {
        "reparto": {"type": "string"},
        "teste_extra": {"type": "number"},
        "perche": {"type": "string"},
    },
}


def reparto_di(mansioni: list[str]) -> str:
    return mansioni[0] if mansioni else "sala"


@dataclass(slots=True)
class Fabbisogno:
    data: dt.date
    fascia: str
    reparto: str
    teste: float

    def come_dict(self) -> dict:
        return {
            "data": self.data.isoformat(),
            "fascia": self.fascia,
            "reparto": self.reparto,
            "teste": round(self.teste, 1),
        }


def _presenze(piano: Piano, schede: dict) -> dict[tuple[int, str, str], float]:
    """Teste per (giorno-settimana, fascia, reparto) in una settimana storica."""
    conteggio: dict[tuple[int, str, str], float] = {}
    for slug in piano.persone():
        persona = schede.get(slug)
        for turno in piano.della_persona(slug):
            if not turno.lavorato:
                continue
            reparto = reparto_di(list(turno.mansioni) or (persona.nomi_mansioni() if persona else []))
            for nome, dalle, alle in FASCE:
                if ore_in_fascia(turno, dalle, alle) > 0.5:
                    chiave = (turno.data.weekday(), nome, reparto)
                    conteggio[chiave] = conteggio.get(chiave, 0) + 1
    return conteggio


def previsione(
    settimana: dt.date, storia: list[Piano], schede: dict | None = None
) -> list[Fabbisogno]:
    schede = schede if schede is not None else kb_persone.per_slug()
    if not storia:
        return []
    somme: dict[tuple[int, str, str], list[float]] = {}
    for piano in storia:
        for chiave, teste in _presenze(piano, schede).items():
            somme.setdefault(chiave, []).append(teste)
    fuori: list[Fabbisogno] = []
    for (giorno, fascia, reparto), valori in sorted(somme.items()):
        media = sum(valori) / len(storia)
        if media < 0.5:
            continue
        fuori.append(
            Fabbisogno(
                data=settimana + dt.timedelta(days=giorno),
                fascia=fascia,
                reparto=reparto,
                teste=round(media, 1),
            )
        )
    return fuori


class Forecast:
    id = "forecast"
    usa_llm = True  # solo per le note libere
    modello = "codice+llm-note"
    versione_prompt = "forecast-1"

    def _modificatori(self, note: dict[str, str]) -> tuple[list[dict], list[str]]:
        modificatori: list[dict] = []
        fonti: list[str] = []
        for data, nota in note.items():
            testo = nota.lower()
            riconosciuta = False
            for parola, (reparto, extra) in MODIFICATORI_NOTI.items():
                if re.search(rf"\b{parola}", testo):
                    modificatori.append(
                        {
                            "data": data,
                            "reparto": reparto,
                            "teste_extra": extra,
                            "perche": f"nota di settimana: {nota}",
                            "fonte": "vocabolario noto",
                        }
                    )
                    riconosciuta = True
                    break
            if riconosciuta:
                continue
            # nota fuori vocabolario: qui — e solo qui — serve interpretare NL
            try:
                dati, _ = llm().genera_json(
                    prompt=(
                        "Una nota operativa della testata del tabellone di un supermercato. "
                        "Dimmi che reparto tocca e quante teste in più servono (0 se nessuna).\n"
                        + allowlist.blocco_dati(nota)
                    ),
                    schema=SCHEMA_NOTA,
                    sistema="forecast: interpreti note operative. Rispondi solo JSON.",
                )
            except (LLMGiu, SchemaNonRispettato):
                continue  # degrado onesto: nessun modificatore, non un numero finto
            modificatori.append(
                {
                    "data": data,
                    "reparto": str(dati.get("reparto", "sala")),
                    "teste_extra": float(dati.get("teste_extra", 0)),
                    "perche": str(dati.get("perche", "")) or f"nota: {nota}",
                    "fonte": "llm",
                }
            )
        return modificatori, fonti

    def nel_ciclo(self, contesto: Contesto, **fase) -> Proposta:
        schede = kb_persone.per_slug()
        fabbisogni = previsione(contesto.settimana, contesto.piani, schede)
        modificatori, _ = self._modificatori(contesto.note_settimana)
        for m in modificatori:
            for f in fabbisogni:
                if f.data.isoformat() == m["data"] and f.reparto == m["reparto"]:
                    f.teste += float(m["teste_extra"])
                    break
        rationale = (
            f"Fabbisogno da {len(contesto.piani)} settimane di storia, "
            f"{len(fabbisogni)} fasce coperte"
            + (f"; {len(modificatori)} note della testata applicate." if modificatori else ".")
        )
        return Proposta(
            agente=self.id,
            tipo="previsione",
            payload={
                "settimana": contesto.settimana.isoformat(),
                "fabbisogno": [f.come_dict() for f in fabbisogni],
                "modificatori": modificatori,
            },
            rationale=rationale,
            fonti=[f for f in contesto.fonti if f.startswith("kb/turni/")],
            confidenza=min(1.0, len(contesto.piani) / 8) if contesto.piani else 0.0,
        )

    def consulta(self, domanda: str, contesto: Contesto, **extra) -> Proposta:
        p = self.nel_ciclo(contesto)
        p.payload["domanda"] = domanda
        giorno = _giorno_citato(domanda)
        if giorno is not None:
            p.payload["fabbisogno"] = [
                f for f in p.payload["fabbisogno"] if dt.date.fromisoformat(f["data"]).weekday() == giorno
            ]
        return p


_GIORNI_NL = {
    "lunedì": 0, "lunedi": 0, "martedì": 1, "martedi": 1, "mercoledì": 2, "mercoledi": 2,
    "giovedì": 3, "giovedi": 3, "venerdì": 4, "venerdi": 4, "sabato": 5, "domenica": 6,
}


def _giorno_citato(testo: str) -> int | None:
    basso = (testo or "").lower()
    for parola, i in _GIORNI_NL.items():
        if parola in basso:
            return i
    return None


AGENTE = registra(Forecast())
