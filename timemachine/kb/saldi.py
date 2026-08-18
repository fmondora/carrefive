"""Schede saldo — `kb/saldi/{slug}.md` (`04` §4.2).

Snapshot del montante. Lo scrive l'import da file o l'adapter Gamma; nessun
agente, nessun LLM. Un `tipo` sconosciuto si scarta con log, non si inventa.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from ..domain.saldi import TIPI_SALDO, Saldo
from . import paths

_META = re.compile(r"^-\s*([a-z_]+)\s*:\s*(.+?)\s*$", re.I)


def percorso(slug: str) -> Path:
    return paths.dir_saldi() / f"{slug}.md"


def _numero(v: str) -> float:
    v = (v or "").strip().replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", v)
    return float(m.group(0)) if m else 0.0


def parse(testo: str, slug: str) -> list[Saldo]:
    meta: dict[str, str] = {}
    for riga in testo.splitlines():
        m = _META.match(riga.strip())
        if m:
            meta[m.group(1).lower()] = m.group(2).strip()
    fonte = meta.get("fonte", "file")
    fonte_ref = meta.get("fonte_ref", "")
    aggiornato = meta.get("aggiornato_at", "")

    fuori: list[Saldo] = []
    for riga in testo.splitlines():
        if not riga.strip().startswith("|"):
            continue
        celle = [c.strip() for c in riga.strip().strip("|").split("|")]
        if len(celle) < 5:
            continue
        tipo = celle[0].lower()
        if tipo not in TIPI_SALDO:
            continue
        fuori.append(
            Saldo(
                persona=slug,
                tipo=tipo,
                maturato=_numero(celle[1]),
                goduto=_numero(celle[2]),
                prenotato_fonte=_numero(celle[3]),
                residuo=_numero(celle[4]),
                aggiornato_at=aggiornato,
                fonte=fonte,  # type: ignore[arg-type]
                fonte_ref=fonte_ref,
            )
        )
    return fuori


def leggi(slug: str) -> list[Saldo]:
    p = percorso(slug)
    if not p.exists():
        return []
    return parse(p.read_text(encoding="utf-8"), slug)


def aggiornati_at(slug: str) -> str | None:
    saldi = leggi(slug)
    return saldi[0].aggiornato_at if saldi else None


def serializza(nome: str, saldi: list[Saldo]) -> str:
    primo = saldi[0]
    righe = [
        f"# Saldi — {nome}",
        "",
        f"- persona: {primo.persona}",
        f"- fonte: {primo.fonte}",
        f"- fonte_ref: {primo.fonte_ref}",
        f"- aggiornato_at: {primo.aggiornato_at}",
        "",
        "| tipo | maturato_ore | goduto_ore | prenotato_ore | residuo_ore |",
        "|---|---|---|---|---|",
    ]
    for s in saldi:
        righe.append(
            f"| {s.tipo} | {s.maturato:g} | {s.goduto:g} | {s.prenotato_fonte:g} | {s.residuo:g} |"
        )
    return "\n".join(righe) + "\n"


def scrivi(slug: str, saldi: list[Saldo], nome: str | None = None) -> Path:
    if not saldi:
        raise ValueError("nessun saldo da scrivere: non si crea un file vuoto")
    from . import persone as kb_persone

    persona = kb_persone.leggi(slug)
    p = percorso(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(serializza(nome or (persona.nome if persona else slug), saldi), encoding="utf-8")
    return p


def cancella(slug: str) -> bool:
    """Diritto alla cancellazione (`05` §4.2)."""
    p = percorso(slug)
    if p.exists():
        p.unlink()
        return True
    return False


def oggi() -> str:
    return dt.date.today().isoformat()
