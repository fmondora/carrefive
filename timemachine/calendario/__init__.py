"""Collegamento del calendario Google (`03` §4.2).

Chi collega: **solo la persona, sul proprio account**. Niente on-behalf del
manager. In scheda va solo il fatto non segreto (`calendario:`); il token sta
nello store cifrato.

Identità Google (`07`) e calendario Google (`03`) sono due consensi distinti:
entrare con Google non scrive un evento.
"""

from __future__ import annotations

import datetime as dt
import os

from ..tempo import oggi as _oggi
from urllib.parse import urlencode

from ..kb import persone as kb_persone
from ..security.authz import Attore, esigi_collegamento_calendario
from . import client as modulo_client  # noqa: F401  (i test sostituiscono il client)
from . import store, sync
from .client import SCOPE, ErroreGoogle
from .client import client as client_attivo
from .client import imposta_client
from .store import TokenGoogle


def url_consenso(slug: str, redirect_uri: str, state: str) -> str:
    """La schermata è di Google, non un form nostro (`03` §4.2 punto 2)."""
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPE),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "login_hint": slug,
        }
    )


def collega(
    attore: Attore,
    slug: str,
    access_token: str,
    refresh_token: str = "",
    email: str = "",
    google_sub: str = "",
    scadenza: float = 0.0,
) -> dict:
    esigi_collegamento_calendario(attore, slug)
    store.salva(
        TokenGoogle(
            persona=slug,
            access_token=access_token,
            refresh_token=refresh_token,
            email=email,
            google_sub=google_sub,
            scadenza=scadenza,
            scope=" ".join(SCOPE),
        )
    )
    kb_persone.imposta_blocco(
        slug,
        "calendario",
        {
            "provider": "google",
            "email": email,
            "stato": "collegato",
            "da": _oggi().isoformat(),
        },
    )
    return sync.sincronizza(slug)  # primo sync: crea il calendario e i futuri


def scollega(attore: Attore, slug: str, cancella_calendario: bool = True) -> dict:
    """Revoca + cancellazione dei **soli** eventi nostri. Conferma obbligatoria."""
    esigi_collegamento_calendario(attore, slug)
    c = client_attivo()
    token = store.leggi(slug)
    cancellati = 0
    if token:
        try:
            calendario_id = token.calendario_id or c.assicura_calendario(slug)
            if cancella_calendario:
                c.cancella_calendario(calendario_id)
            else:
                for e in c.elenca_nostri(calendario_id, dt.datetime(1970, 1, 1)):
                    c.cancella(calendario_id, e.id or e.shift_key)
                    cancellati += 1
        except ErroreGoogle:
            pass  # se Google non risponde, il token nostro sparisce comunque
        c.revoca(slug)
    store.cancella(slug)
    persona = kb_persone.leggi(slug)
    blocco = dict(persona.calendario) if persona else {}
    blocco.update({"stato": "scollegato", "da": _oggi().isoformat()})
    blocco.pop("email", None)
    kb_persone.imposta_blocco(slug, "calendario", blocco)
    return {"persona": slug, "eventi_cancellati": cancellati, "token": "rimosso"}


__all__ = [
    "client_attivo",
    "collega",
    "imposta_client",
    "scollega",
    "store",
    "sync",
    "url_consenso",
]
