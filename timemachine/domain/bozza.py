"""Bozza di settimana — il payload di `bozza-turni` (`01` §4.2).

Il vocabolario è quello del tabellone: persona × giorno → fascia + mansione +
note. La forma serializzata (celle) è ciò che passa dentro una `Proposta`; il
`Piano` è la forma comoda per calcolare e per renderizzare.

Una bozza **non è** un piano pubblicato: overlay albicocca, mai foglia (`06`).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from ..kb.celle import formatta_cella, parse_cella
from .modelli import Piano, Turno


def celle_da_piano(piano: Piano) -> list[dict]:
    celle: list[dict] = []
    for slug in piano.persone():
        for turno in piano.della_persona(slug):
            celle.append(
                {
                    "persona": slug,
                    "data": turno.data.isoformat(),
                    "fascia": formatta_cella(turno.spezzoni, None, ""),
                    "badge": turno.badge,
                    "mansioni": list(turno.mansioni),
                    "note": turno.note,
                }
            )
    return celle


def piano_da_celle(celle: list[dict], settimana: dt.date, stato: str = "bozza") -> Piano:
    piano = Piano(settimana=settimana, stato=stato)  # type: ignore[arg-type]
    for cella in celle:
        data = dt.date.fromisoformat(str(cella["data"]))
        grezzo = str(cella.get("fascia") or cella.get("badge") or "")
        spezzoni, badge, note = parse_cella(grezzo)
        mansioni = tuple(cella.get("mansioni") or ())
        if mansioni and spezzoni:
            spezzoni = tuple(
                s if s.mansioni else type(s)(s.inizio, s.fine, mansioni, s.note) for s in spezzoni
            )
        piano.imposta(
            Turno(
                persona=str(cella["persona"]),
                data=data,
                spezzoni=spezzoni,
                badge=badge or (str(cella["badge"]) if cella.get("badge") else None),
                note=str(cella.get("note") or note or ""),
                grezzo=grezzo,
            )
        )
    return piano


@dataclass(slots=True)
class Variante:
    nome: str
    piano: Piano
    rationale: str = ""
    confidenza: float | None = None


@dataclass(slots=True)
class Bozza:
    settimana: dt.date
    varianti: list[Variante] = field(default_factory=list)
    scelta: int = 0
    proposta_id: str = ""
    pubblicabile: bool = False
    violazioni: list[dict] = field(default_factory=list)
    segnalazioni: list[dict] = field(default_factory=list)
    gap: list[dict] = field(default_factory=list)
    fonti: list[str] = field(default_factory=list)
    accettata: bool = False

    @property
    def piano(self) -> Piano:
        return self.varianti[self.scelta].piano

    @property
    def rationale(self) -> str:
        return self.varianti[self.scelta].rationale

    def _riferimento(self, pubblicato: Piano | None, persona: str, giorno: dt.date) -> Turno | None:
        """Il turno omologo nel piano di confronto.

        Se il confronto è con un'**altra** settimana (bozza nuova vs ultima
        pubblicata) si allinea per giorno della settimana, non per data:
        «il lunedì di prima» è la domanda che si fa un manager.
        """
        if pubblicato is None:
            return None
        scarto = self.settimana - pubblicato.settimana
        return pubblicato.turno(persona, giorno - scarto)

    def persone_toccate(self, pubblicato: Piano | None) -> list[str]:
        """Chi cambia rispetto al riferimento. È l'unità della vista (`02` §4.3)."""
        if pubblicato is None:
            return self.piano.persone()
        toccate = []
        for slug in self.piano.persone():
            for giorno in self.piano.giorni:
                nuovo = self.piano.turno(slug, giorno)
                vecchio = self._riferimento(pubblicato, slug, giorno)
                if _etichetta(nuovo) != _etichetta(vecchio):
                    toccate.append(slug)
                    break
        return toccate

    def diff(self, pubblicato: Piano | None, persona: str) -> list[dict]:
        """Righe per `diff-edit`: un turno che cambia, non una tabella 30×7."""
        fuori: list[dict] = []
        for giorno in self.piano.giorni:
            nuovo = self.piano.turno(persona, giorno)
            vecchio = self._riferimento(pubblicato, persona, giorno)
            a, b = _etichetta(vecchio), _etichetta(nuovo)
            if a != b:
                fuori.append(
                    {
                        "data": giorno.isoformat(),
                        "giorno": nuovo.giorno if nuovo else vecchio.giorno if vecchio else "",
                        "prima": a,
                        "dopo": b,
                    }
                )
        return fuori


def _etichetta(turno: Turno | None) -> str:
    if turno is None:
        return ""
    return turno.etichetta()
