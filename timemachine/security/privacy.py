"""La regola della storia (`05` §4.2).

Ciò che Anna *dice* («ho lezione di pianoforte») si può salvare in scheda:
è il suo testo. Ciò che **manager e modello** ricevono di default è il
*vincolo operativo* (`no_pomeriggio: gio`), non l'aneddoto.

La riduzione è **codice**, non un giudizio dell'LLM: deve essere prevedibile e
uguale ogni volta (`05` §5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..domain.modelli import GIORNI, Preferenza

_GIORNI_ESTESI = {
    "lunedi": "lun",
    "lunedì": "lun",
    "martedi": "mar",
    "martedì": "mar",
    "mercoledi": "mer",
    "mercoledì": "mer",
    "giovedi": "gio",
    "giovedì": "gio",
    "venerdi": "ven",
    "venerdì": "ven",
    "sabato": "sab",
    "domenica": "dom",
    **{g: g for g in GIORNI},
}

_FASCE = {
    "mattina": "mattina",
    "mattino": "mattina",
    "mattutino": "mattina",
    "pomeriggio": "pomeriggio",
    "pome": "pomeriggio",
    "sera": "sera",
    "serale": "sera",
    "chiusura": "chiusura",
    "notte": "sera",
}

_NEGAZIONE = re.compile(r"\b(non posso|non riesco|no|niente|evitare|libera|libero|impegn)", re.I)


@dataclass(frozen=True, slots=True)
class Riduzione:
    vincolo: str
    storia: str
    spiegazione: str


def deriva_vincolo(testo: str) -> Riduzione:
    """Da linguaggio naturale al vincolo operativo. Nessuna rete, nessun LLM."""
    t = (testo or "").strip()
    basso = t.lower()

    giorno = ""
    for parola, sigla in _GIORNI_ESTESI.items():
        if re.search(rf"\b{parola}\b", basso):
            giorno = sigla
            break

    fascia = ""
    for parola, nome in _FASCE.items():
        if re.search(rf"\b{parola}\w*\b", basso):
            fascia = nome
            break

    if fascia and giorno:
        vincolo = f"no_{fascia}: {giorno}"
    elif fascia:
        vincolo = f"no_{fascia}"
    elif giorno:
        vincolo = f"no_turno: {giorno}"
    else:
        # niente di riconoscibile: si tiene il testo come vincolo da confermare,
        # non si inventa una regola che lo Scheduling userebbe.
        vincolo = "da_chiarire"

    spiegazione = {
        "da_chiarire": "Non ho riconosciuto giorno o fascia: resta da chiarire, non entra nello Scheduling.",
    }.get(vincolo, f"Il manager e lo Scheduling vedranno «{vincolo}», non il motivo.")

    return Riduzione(vincolo=vincolo, storia=t, spiegazione=spiegazione)


def preferenza_da_testo(testo: str, data: str = "") -> Preferenza:
    r = deriva_vincolo(testo)
    return Preferenza(vincolo=r.vincolo, storia=r.storia, origine="da-confermare", data=data)


def vincoli_operativi(preferenze: list[Preferenza]) -> list[str]:
    """Ciò che esce verso manager e modello: solo la forma operativa."""
    return [p.operativa() for p in preferenze if p.vincolo and p.vincolo != "da_chiarire"]


def viola(vincolo: str, giorno: str, inizio_ora: int) -> bool:
    """Il vincolo morbido è violato da questo spezzone? Usato in rationale."""
    m = re.match(r"no_(\w+)(?::\s*(\w+))?", vincolo or "")
    if not m:
        return False
    fascia, g = m.group(1), (m.group(2) or "")
    if g and g != giorno:
        return False
    if fascia == "mattina":
        return inizio_ora < 12
    if fascia == "pomeriggio":
        return 12 <= inizio_ora < 18
    if fascia in {"sera", "chiusura"}:
        return inizio_ora >= 16
    if fascia == "turno":
        return True
    return False
