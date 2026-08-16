"""Motore ore — **zero AI** (`01` §5, `00` §5.2 confine deterministico).

Non calcola la busta paga: conta le ore del piano, il riposo settimanale e i
cap di contratto. È il pezzo che Compliance usa per bloccare.
"""

from __future__ import annotations

import datetime as dt

from .modelli import Piano, Turno


def ore_turni(turni: list[Turno]) -> float:
    return round(sum(t.ore for t in turni), 2)


def ore_settimana(piano: Piano, persona: str) -> float:
    return ore_turni(piano.della_persona(persona))


def ore_periodo(turni: list[Turno], da: dt.date, a: dt.date) -> float:
    return ore_turni([t for t in turni if da <= t.data <= a])


def giorni_riposo(piano: Piano, persona: str) -> list[dt.date]:
    """Un giorno è riposo se ha badge R/F o se non c'è nessuno spezzone."""
    fuori = []
    for giorno in piano.giorni:
        t = piano.turno(persona, giorno)
        if t is None or (not t.lavorato and t.badge != "No" or t.riposo or t.ferie):
            if t is None or not t.lavorato:
                fuori.append(giorno)
    return fuori


def ha_riposo_settimanale(piano: Piano, persona: str) -> bool:
    return len(giorni_riposo(piano, persona)) >= 1


def giorni_consecutivi_lavorati(piano: Piano, persona: str) -> int:
    massimo = corrente = 0
    for giorno in piano.giorni:
        t = piano.turno(persona, giorno)
        if t is not None and t.lavorato:
            corrente += 1
            massimo = max(massimo, corrente)
        else:
            corrente = 0
    return massimo


def riposo_fra_turni(precedente: Turno | None, successivo: Turno | None) -> float | None:
    """Ore fra la fine dell'ultimo spezzone e l'inizio del primo del giorno dopo."""
    if not precedente or not successivo or not precedente.lavorato or not successivo.lavorato:
        return None
    fine = dt.datetime.combine(precedente.data, precedente.spezzoni[-1].fine)
    inizio = dt.datetime.combine(successivo.data, successivo.spezzoni[0].inizio)
    return round((inizio - fine).total_seconds() / 3600, 2)


def ore_in_fascia(turno: Turno, dalle: dt.time, alle: dt.time) -> float:
    """Sovrapposizione fra il turno e una fascia (per la copertura)."""
    def minuti(t: dt.time) -> int:
        return t.hour * 60 + t.minute

    tot = 0
    for s in turno.spezzoni:
        a = max(minuti(s.inizio), minuti(dalle))
        b = min(minuti(s.fine), minuti(alle))
        if b > a:
            tot += b - a
    return round(tot / 60, 2)
