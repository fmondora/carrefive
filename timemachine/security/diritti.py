"""Diritti GDPR — accesso, portabilità, cancellazione (`05` §4.2, G6).

Procedura **deterministica**: non «chiedi al Copilot di dimenticare».

Cancellazione: via le sue preferenze, il saldo, il token, gli eventi nostri e
i log a lei riferibili. I **turni pubblicati storici restano** con lo slug —
obbligo organizzativo e retributivo — senza preferenze né segreti.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from pathlib import Path

from ..kb import persone as kb_persone
from ..kb import saldi as kb_saldi
from ..kb import turni as kb_turni
from ..kb.paths import stato_root
from . import audit


def esporta(slug: str) -> dict:
    """Diritto di accesso e portabilità: le sue md + i suoi record."""
    persona = kb_persone.leggi(slug)
    if persona is None:
        raise FileNotFoundError(slug)
    turni = []
    for piano in kb_turni.piani_pubblicati():
        for t in piano.della_persona(slug):
            turni.append(
                {
                    "settimana": piano.settimana.isoformat(),
                    "data": t.data.isoformat(),
                    "turno": t.etichetta(),
                    "mansioni": list(t.mansioni),
                }
            )
    return {
        "persona": slug,
        "esportato_at": dt.datetime.now(dt.UTC).isoformat(),
        "scheda": kb_persone.percorso(slug).read_text(encoding="utf-8"),
        "saldi": [dataclasses.asdict(s) for s in kb_saldi.leggi(slug)],
        "turni_pubblicati": turni,
        "preferenze": [
            {"vincolo": p.vincolo, "storia": p.storia, "origine": p.origine}
            for p in persona.preferenze
        ],
        "calendario": persona.calendario,
        "account": {k: v for k, v in persona.account.items() if k != "email"} | {
            "email": persona.account.get("email", "")
        },
        "log": audit.record_di(slug),
    }


def scrivi_export(slug: str, destinazione: Path | None = None) -> Path:
    destinazione = destinazione or (stato_root() / "export")
    destinazione.mkdir(parents=True, exist_ok=True)
    p = destinazione / f"{slug}.json"
    p.write_text(
        json.dumps(esporta(slug), indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return p


def cancella(slug: str, cancella_calendario: bool = True) -> dict:
    """Diritto all'oblio. Non tocca le altre persone."""
    from ..auth import store as auth_store
    from ..calendario import store as token_store
    from ..calendario.client import ErroreGoogle, client

    persona = kb_persone.leggi(slug)
    if persona is None:
        raise FileNotFoundError(slug)

    eventi = 0
    if cancella_calendario and token_store.leggi(slug):
        c = client()
        try:
            cid = c.assicura_calendario(slug)
            c.cancella_calendario(cid)
            eventi = 1
        except ErroreGoogle:
            pass
        c.revoca(slug)
    token_store.cancella(slug)
    auth_store.cancella_account(slug)

    for pref in list(persona.preferenze):
        kb_persone.rimuovi_preferenza(slug, pref.vincolo)
    kb_persone.togli_blocco(slug, "Calendario")
    kb_persone.togli_blocco(slug, "Account")
    saldo_via = kb_saldi.cancella(slug)
    log_via = audit.cancella_di(slug)

    return {
        "persona": slug,
        "preferenze_cancellate": len(persona.preferenze),
        "saldi_cancellati": saldo_via,
        "calendario_cancellato": bool(eventi),
        "log_cancellati": log_via,
        "turni_storici": "conservati (obbligo organizzativo)",
    }
