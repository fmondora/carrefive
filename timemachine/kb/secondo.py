"""Secondo del punto vendita — `kb/secondo/*.md`, **append-only** (`01` §4.6).

Impara solo da decisioni umane e distilla pattern di *negozio*.
Vietato: produttività individuale, ranking, giudizi su persone (art. 4, `05`).
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from . import paths

#: parole che segnalano un giudizio su una persona → la nota si rifiuta
_GIUDIZIO = re.compile(
    r"\b(lent[ao]|pigr[ao]|inaffidabile|scars[ao]|produttivit[àa]|rendimento|"
    r"performance|migliore|peggiore|classifica|ranking|voto|punteggio)\b",
    re.I,
)


class NotaValutativa(Exception):
    """Il secondo non giudica le persone. Art. 4 Statuto."""


def dir_secondo() -> Path:
    d = paths.dir_secondo()
    d.mkdir(parents=True, exist_ok=True)
    return d


def valida(testo: str) -> None:
    if _GIUDIZIO.search(testo):
        raise NotaValutativa(
            "la memoria del punto vendita non contiene giudizi individuali (art. 4)"
        )


def append(argomento: str, testo: str, fonti: list[str] | None = None, quando: str = "") -> Path:
    """Aggiunge una nota. Non cancella mai (append-only)."""
    valida(testo)
    slug = re.sub(r"[^a-z0-9]+", "-", argomento.lower()).strip("-") or "note"
    p = dir_secondo() / f"{slug}.md"
    quando = quando or dt.date.today().isoformat()
    intestazione = "" if p.exists() else f"# Secondo del punto vendita — {argomento}\n\n"
    riga = f"- {quando} — {testo.strip()}"
    if fonti:
        riga += " — fonti: " + ", ".join(f"`{f}`" for f in fonti)
    with p.open("a", encoding="utf-8") as f:
        f.write(f"{intestazione}{riga}\n")
    return p


def leggi(argomento: str) -> str:
    p = dir_secondo() / f"{re.sub(r'[^a-z0-9]+', '-', argomento.lower()).strip('-')}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def note(limite: int | None = None) -> list[str]:
    fuori: list[str] = []
    d = paths.dir_secondo()
    if not d.exists():
        return fuori
    for f in sorted(d.glob("*.md")):
        for riga in f.read_text(encoding="utf-8").splitlines():
            if riga.strip().startswith("- "):
                fuori.append(riga.strip()[2:])
    return fuori[-limite:] if limite else fuori


def retrieval(termini: list[str], limite: int = 5) -> list[str]:
    """Retrieval, non dump (`01` §4.4 `carica_contesto`)."""
    termini = [t.lower() for t in termini if t]
    punteggiate: list[tuple[int, str]] = []
    for n in note():
        p = sum(1 for t in termini if t in n.lower())
        if p:
            punteggiate.append((p, n))
    punteggiate.sort(key=lambda x: -x[0])
    return [n for _, n in punteggiate[:limite]]
