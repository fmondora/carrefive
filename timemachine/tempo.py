"""L'orologio del sistema, in un posto solo.

`TM_OGGI` (YYYY-MM-DD) sposta «oggi»: serve ai test e alle demo sul pilota, la
cui settimana pubblicata è il 29/06/2026. Senza la variabile è l'ora vera.

Fuso: `Europe/Rome` — è l'unico che esiste per un negozio a Poggiridenti.
"""

from __future__ import annotations

import datetime as dt
import os

FUSO = "Europe/Rome"


def oggi() -> dt.date:
    forzata = os.environ.get("TM_OGGI")
    return dt.date.fromisoformat(forzata) if forzata else dt.date.today()


def adesso() -> dt.datetime:
    forzata = os.environ.get("TM_OGGI")
    if not forzata:
        return dt.datetime.now()
    reale = dt.datetime.now()
    return dt.datetime.combine(dt.date.fromisoformat(forzata), reale.time())


def lunedi_di(data: dt.date | None = None) -> dt.date:
    data = data or oggi()
    return data - dt.timedelta(days=data.weekday())
