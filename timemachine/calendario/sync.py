"""Sync calendario — effetto **deterministico** di `pubblica` (`03` §4.4).

Trigger unico: la transizione a `pubblica` in `01`. Bozze mai (C7).
Job idempotente per `(persona, data, fonte=turni-pubblicati)`; il passato non
si tocca; il piano pubblicato vince sulle modifiche manuali agli eventi nostri.

Se Google è giù, `pubblica` **è già riuscita**: qui si ritenta, e la persona
vede lo stato sul widget (C5).
"""

from __future__ import annotations

import datetime as dt

from ..domain.modelli import Piano, Turno
from ..kb import persone as kb_persone
from ..kb import turni as kb_turni
from ..orchestrator.jobs import CODA, Job
from ..tempo import adesso as adesso_reale
from .client import Evento, ErroreAutorizzazione, ErroreGoogle, client

DESCRIZIONE_CODA = "Turno pubblicato. Non rispondere a questo evento."


def chiave_turno(settimana: dt.date, persona: str, data: dt.date, idx: int) -> str:
    return f"{settimana.isoformat()}:{persona}:{data.isoformat()}:{idx}"


def eventi_da_turno(turno: Turno, settimana: dt.date, note_settimana: str = "") -> list[Evento]:
    """`R` e `F` non diventano eventi: non si occupa il giorno libero (`03` §4.3)."""
    if not turno.lavorato:
        return []
    fuori: list[Evento] = []
    for idx, spezzone in enumerate(turno.spezzoni):
        mansione = ", ".join(spezzone.mansioni) or ", ".join(turno.mansioni)
        titolo = f"{mansione.capitalize()} — Le Rocce" if mansione else "Turno — Le Rocce"
        descrizione = " · ".join(
            x for x in (spezzone.note, turno.note, note_settimana, DESCRIZIONE_CODA) if x
        )
        fuori.append(
            Evento(
                shift_key=chiave_turno(settimana, turno.persona, turno.data, idx),
                summary=titolo,
                inizio=dt.datetime.combine(turno.data, spezzone.inizio),
                fine=dt.datetime.combine(turno.data, spezzone.fine),
                description=descrizione,
            )
        )
    return fuori


#: stati in cui il collegamento c'è ancora e il sync deve ritentare.
#: `da-ricollegare` no: lì il token è stato revocato lato Google e insistere
#: sarebbe rumore; `scollegato` nemmeno, per ovvi motivi.
STATI_ATTIVI = {"collegato", "in-errore", "in-aggiornamento"}


def collegato(slug: str) -> bool:
    persona = kb_persone.leggi(slug)
    return bool(persona and persona.calendario.get("stato") in STATI_ATTIVI)


def sincronizza(
    slug: str, adesso: dt.datetime | None = None, piani: list[Piano] | None = None
) -> dict:
    """Diff fra i futuri del piano pubblicato e i nostri eventi sul calendario."""
    adesso = adesso or adesso_reale()
    if not collegato(slug):
        return {"persona": slug, "saltato": "non collegato"}

    c = client()
    calendario_id = c.assicura_calendario(slug)
    piani = piani if piani is not None else kb_turni.piani_pubblicati()

    voluti: dict[str, Evento] = {}
    for piano in piani:
        note = piano.note_settimana
        for turno in piano.della_persona(slug):
            if turno.data < adesso.date():
                continue  # il passato non si tocca
            for evento in eventi_da_turno(turno, piano.settimana, note.get(turno.data, "")):
                if evento.fine >= adesso:
                    voluti[evento.shift_key] = evento

    esistenti = {e.shift_key: e for e in c.elenca_nostri(calendario_id, adesso)}

    creati = aggiornati = cancellati = 0
    for chiave, evento in voluti.items():
        precedente = esistenti.get(chiave)
        if precedente:
            evento.id = precedente.id
            aggiornati += 1
        else:
            creati += 1
        c.upsert(calendario_id, evento)  # il piano pubblicato vince, niente merge

    for chiave, evento in esistenti.items():
        if chiave not in voluti:
            c.cancella(calendario_id, evento.id or chiave)
            cancellati += 1

    persona = kb_persone.leggi(slug)
    if persona and persona.calendario.get("stato") != "collegato":
        _marca(slug, "collegato")  # tornato su: il badge d'errore si spegne

    return {
        "persona": slug,
        "calendario": calendario_id,
        "creati": creati,
        "aggiornati": aggiornati,
        "cancellati": cancellati,
    }


def dopo_pubblicazione(piano: Piano) -> list[Job]:
    """Chiamata solo dal gate `pubblica`. Una bozza non arriva mai qui."""
    if piano.stato != "pubblicato":
        raise ValueError("sul calendario vanno solo i turni pubblicati")
    jobs: list[Job] = []
    for slug in piano.persone():
        if not collegato(slug):
            continue
        jobs.append(
            CODA.accoda(
                "sync-calendario",
                _lavoro(slug),
                chiave=f"sync:{slug}:{piano.settimana.isoformat()}",
            )
        )
    return jobs


def dopo_pubblicazione_persona(slug: str) -> Job | None:
    """Chip `riprova` dal widget: rimette in coda il sync di una sola persona."""
    if not collegato(slug):
        return None
    return CODA.accoda("sync-calendario", _lavoro(slug), chiave=f"sync:{slug}:riprova")


def _lavoro(slug: str):
    def esegui():
        try:
            return sincronizza(slug)
        except ErroreAutorizzazione:
            _marca(slug, "da-ricollegare")
            raise
        except ErroreGoogle:
            _marca(slug, "in-errore")
            raise

    return esegui


def _marca(slug: str, stato: str) -> None:
    persona = kb_persone.leggi(slug)
    if persona is None:
        return
    blocco = dict(persona.calendario)
    blocco["stato"] = stato
    kb_persone.imposta_blocco(slug, "calendario", blocco)


def stato_widget(slug: str) -> dict:
    """Ciò che `person-shifts` mostra sul calendario (`03` §4.5)."""
    persona = kb_persone.leggi(slug)
    stato = (persona.calendario.get("stato") if persona else "") or "non-collegato"
    job = CODA.ultimo("sync-calendario")
    in_corso = bool(job and job.stato in ("in_coda", "in_corso"))
    email = (persona.calendario.get("email") if persona else "") or ""
    return {
        "stato": "in-aggiornamento" if in_corso and stato == "collegato" else stato,
        "email_mascherata": maschera_email(email),
        "chip": _chip(stato),
        "job": job.come_dict() if job else None,
    }


def _chip(stato: str) -> list[str]:
    if stato == "collegato":
        return ["scollega-google"]
    if stato in ("in-errore", "da-ricollegare"):
        return ["riprova", "scollega-google"]
    return ["collega-google"]


def maschera_email(email: str) -> str:
    if "@" not in email:
        return email
    nome, dominio = email.split("@", 1)
    return f"{nome[0]}***@{dominio}" if nome else f"***@{dominio}"
