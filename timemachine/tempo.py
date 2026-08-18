"""L'orologio del sistema, in un posto solo.

`TM_OGGI` sposta «adesso»: serve ai test e alle demo sul pilota, la cui
settimana pubblicata è il 29/06/2026. Accetta una data (`2026-06-29`) o una
data e un'ora (`2026-06-29T14:05`).

**Con una data sola l'ora è 00:00, non l'ora vera del sistema.** Mescolare una
data finta con l'orologio reale rende non deterministico tutto ciò che guarda
«cosa è ancora futuro» — il sync del calendario, per dire, cambiava risultato
a seconda dell'ora in cui giravano i test.

Fuso: `Europe/Rome` — è l'unico che esiste per un negozio a Poggiridenti.
"""

from __future__ import annotations

import datetime as dt
import os

FUSO = "Europe/Rome"
ENV = "TM_OGGI"


def _forzato() -> dt.datetime | None:
    grezzo = os.environ.get(ENV)
    if not grezzo:
        return None
    try:
        return dt.datetime.fromisoformat(grezzo)
    except ValueError:
        return None


def oggi() -> dt.date:
    forzato = _forzato()
    return forzato.date() if forzato else dt.date.today()


def adesso() -> dt.datetime:
    forzato = _forzato()
    return forzato if forzato else dt.datetime.now()


def lunedi_di(data: dt.date | None = None) -> dt.date:
    data = data or oggi()
    return data - dt.timedelta(days=data.weekday())
