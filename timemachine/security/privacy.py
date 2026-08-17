"""La regola della storia (`05` §4.2).

Ciò che Anna *dice* («ho lezione di pianoforte») si può salvare in scheda:
è il suo testo. Ciò che **manager e modello** ricevono di default è il
*vincolo operativo* (`no_pomeriggio: gio`), non l'aneddoto.

La riduzione è **codice**, non un giudizio dell'LLM: deve essere prevedibile e
uguale ogni volta (`05` §5).
"""

from __future__ import annotations

import datetime as dt
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


#: l'ambito appeso alla forma operativa: `no_turno: gio @2026-07-02`
_AMBITO = re.compile(r"@(\d{4}-\d{2}-\d{2})\s*$")


def ambito(vincolo: str) -> str:
    """La data a cui il vincolo è limitato, se c'è. Stringa vuota = ricorrente."""
    m = _AMBITO.search(vincolo or "")
    return m.group(1) if m else ""


def viola(
    vincolo: str, giorno: str, inizio_ora: int, data: dt.date | str | None = None
) -> bool:
    """Il vincolo morbido è violato da questo spezzone? Usato in rationale.

    Se il vincolo porta un ambito (`@2026-07-02`) vale **solo** quel giorno:
    gli altri giovedì non sono violati. Senza la data del turno non si può
    dire, e allora si risponde come prima — sul giorno della settimana: meglio
    una segnalazione in più che un vincolo perso in silenzio.
    """
    vincolo = vincolo or ""
    solo_il = ambito(vincolo)
    if solo_il:
        vincolo = _AMBITO.sub("", vincolo).strip()
        if data is not None:
            quando = data.isoformat() if isinstance(data, dt.date) else str(data)
            if quando != solo_il:
                return False
    m = re.match(r"no_(\w+)(?::\s*(\w+))?", vincolo)
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
