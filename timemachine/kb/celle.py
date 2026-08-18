"""Parser di una cella del tabellone.

Il tabellone cartaceo è la *knowledge* (`02` §3, principio 11): non lo
riscriviamo, lo leggiamo. Una cella può essere:

    "6-14"                      un solo spezzone
    "7-12 C / 16-20 B"          spezzato, mansioni diverse
    "8-12 16-20 PREP SHOOTING"  spezzato, stessa nota
    "R" / "F" / "No" / ""       badge, nessun turno
    "BORMIO"                    badge libero (trasferta)
    "Inventario 7-16"           etichetta prima dell'orario
    "recupera 12/06/2026"       nota senza orario

Regola dura: un token che non è una mansione nota resta **nota**, non diventa
una mansione inventata (grounding, `01` §4.2).
"""

from __future__ import annotations

import datetime as dt
import re

from ..domain.modelli import ABBREVIAZIONI, QUALIFICHE, Spezzone, normalizza_mansione

_ORARIO = re.compile(r"(\d{1,2})(?:[:.](\d{2}))?\s*-\s*(\d{1,2})(?:[:.](\d{2}))?")
_BADGE_SEMPLICI = {"r": "R", "f": "F", "no": "No", "-": None, "": None}


def _tempo(ora: str, minuti: str | None) -> dt.time:
    h = int(ora)
    m = int(minuti) if minuti else 0
    if h == 24:
        h, m = 23, 59
    return dt.time(hour=h % 24, minute=m)


def _pulisci(testo: str) -> str:
    t = re.sub(r"[+/]", " ", testo)
    t = re.sub(r"\s+", " ", t).strip(" .,;·")
    return t.strip()


def _mansioni_e_note(etichetta: str) -> tuple[tuple[str, ...], str]:
    """Separa i token-mansione noti dal resto (che resta nota, in chiaro)."""
    etichetta = _pulisci(etichetta)
    if not etichetta:
        return (), ""
    mansioni: list[str] = []
    resto: list[str] = []
    for token in etichetta.split(" "):
        chiave = re.sub(r"[^a-zà-ù0-9]", "", token.lower())
        if not chiave:
            continue
        if chiave in QUALIFICHE:
            resto.append(token)
            continue
        if chiave in ABBREVIAZIONI:
            m = normalizza_mansione(chiave)
            if m not in mansioni:
                mansioni.append(m)
            resto.append(token)
        else:
            resto.append(token)
    return tuple(mansioni), " ".join(resto).strip()


def parse_cella(grezzo: str) -> tuple[tuple[Spezzone, ...], str | None, str]:
    """Ritorna (spezzoni, badge, note)."""
    testo = (grezzo or "").strip()
    if not testo:
        return (), None, ""

    semplice = re.sub(r"[^a-z]", "", testo.lower())
    if semplice in _BADGE_SEMPLICI and not _ORARIO.search(testo):
        return (), _BADGE_SEMPLICI[semplice], ""

    if not _ORARIO.search(testo):
        # nessun orario: è un badge libero (BORMIO) o una nota (recupera ...)
        return (), testo.upper() if len(testo.split()) == 1 else None, testo

    spezzoni: list[Spezzone] = []
    note_globali: list[str] = []

    for chunk in re.split(r"\s*/\s*", testo):
        chunk = chunk.strip()
        if not chunk:
            continue
        trovati = list(_ORARIO.finditer(chunk))
        if not trovati:
            note_globali.append(_pulisci(chunk))
            continue
        prefisso = chunk[: trovati[0].start()]
        suffisso = chunk[trovati[-1].end() :]
        etichetta = f"{prefisso} {suffisso}"
        mansioni, nota = _mansioni_e_note(etichetta)
        for i, m in enumerate(trovati):
            fra = ""
            if i + 1 < len(trovati):
                fra = chunk[m.end() : trovati[i + 1].start()]
            man_i, nota_i = _mansioni_e_note(fra)
            spezzoni.append(
                Spezzone(
                    inizio=_tempo(m.group(1), m.group(2)),
                    fine=_tempo(m.group(3), m.group(4)),
                    mansioni=tuple(dict.fromkeys(mansioni + man_i)),
                    note=" ".join(x for x in (nota_i, nota) if x).strip(),
                )
            )

    note = " · ".join(x for x in note_globali if x)
    return tuple(spezzoni), None, note


def formatta_cella(spezzoni: tuple[Spezzone, ...], badge: str | None, note: str = "") -> str:
    """Il ritorno verso il markdown: `pubblica` riscrive `kb/turni/`."""
    if not spezzoni:
        return badge or note or ""
    pezzi = []
    for s in spezzoni:
        etichetta = s.etichetta_orario().replace("–", "-")
        if s.note:
            etichetta = f"{etichetta} {s.note}"
        pezzi.append(etichetta)
    testo = " / ".join(pezzi)
    return f"{testo} {note}".strip() if note else testo
