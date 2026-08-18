"""Import saldi da file dello studio (`04` §4.2).

Comando **deterministico**, non un agente: il mapping delle colonne è
dichiarato, non «indovinato» da un LLM. Una riga non matchata va nel report,
non fa fallire la run né produce un file spazzatura (S2).
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..domain.saldi import TIPI_SALDO, Saldo
from ..kb import persone as kb_persone
from ..kb import saldi as kb_saldi

#: mapping di default: colonne dell'export dello studio → nostro vocabolario
MAPPING_DEFAULT: dict[str, str] = {
    "persona": "persona",
    "nome": "persona",
    "dipendente": "persona",
    "codice_gamma": "codice_gamma",
    "cf": "cf",
    "tipo": "tipo",
    "maturato_ore": "maturato",
    "goduto_ore": "goduto",
    "prenotato_ore": "prenotato",
    "residuo_ore": "residuo",
}


@dataclass(slots=True)
class Report:
    file: str
    aggiornato_at: str
    importate: list[str] = field(default_factory=list)
    scartate: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.importate)

    def testo(self) -> str:
        righe = [f"import-saldi {self.file} (at {self.aggiornato_at})"]
        righe.append(f"  importate: {len(self.importate)} → {', '.join(sorted(self.importate))}")
        for riga, motivo in self.scartate:
            righe.append(f"  scartata: {riga} — {motivo}")
        return "\n".join(righe)


def _normalizza_nome(v: str) -> str:
    t = re.sub(r"[^a-zà-ù ]+", " ", (v or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def _indice_persone() -> dict[str, str]:
    idx: dict[str, str] = {}
    for p in kb_persone.tutte():
        idx[_normalizza_nome(p.nome)] = p.slug
        idx[p.slug] = p.slug
        idx[_normalizza_nome(p.slug.replace("-", " "))] = p.slug
    return idx


def _numero(v: str) -> float | None:
    if v is None:
        return None
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(v))
    return float(m.group(0).replace(",", ".")) if m else None


def importa(
    file: str | Path,
    at: str | None = None,
    mapping: dict[str, str] | None = None,
) -> Report:
    percorso = Path(file)
    mapping = {**MAPPING_DEFAULT, **(mapping or {})}
    quando = at or dt.date.fromtimestamp(percorso.stat().st_mtime).isoformat()
    report = Report(file=percorso.name, aggiornato_at=quando)
    idx = _indice_persone()

    per_persona: dict[str, list[Saldo]] = {}
    with percorso.open(newline="", encoding="utf-8-sig") as f:
        for numero_riga, riga in enumerate(csv.DictReader(f), start=2):
            campi = {
                mapping.get((k or "").strip().lower(), (k or "").strip().lower()): (v or "").strip()
                for k, v in riga.items()
            }
            etichetta = campi.get("persona", "") or campi.get("codice_gamma", "") or f"riga {numero_riga}"
            slug = None
            for chiave in (campi.get("codice_gamma"), campi.get("cf")):
                if chiave and chiave.lower() in idx:
                    slug = idx[chiave.lower()]
                    break
            if slug is None:
                slug = idx.get(_normalizza_nome(campi.get("persona", "")))
            if slug is None:
                report.scartate.append((etichetta, "persona non trovata in kb/persone"))
                continue

            tipo = campi.get("tipo", "").lower()
            if tipo not in TIPI_SALDO:
                report.scartate.append((f"{etichetta} [{tipo}]", "tipo di saldo sconosciuto"))
                continue

            maturato = _numero(campi.get("maturato")) or 0.0
            goduto = _numero(campi.get("goduto")) or 0.0
            prenotato = _numero(campi.get("prenotato")) or 0.0
            residuo = _numero(campi.get("residuo"))
            if residuo is None:
                residuo = round(maturato - goduto - prenotato, 2)

            per_persona.setdefault(slug, []).append(
                Saldo(
                    persona=slug,
                    tipo=tipo,
                    maturato=maturato,
                    goduto=goduto,
                    prenotato_fonte=prenotato,
                    residuo=residuo,
                    aggiornato_at=quando,
                    fonte="file",
                    fonte_ref=percorso.name,
                )
            )

    for slug, saldi in per_persona.items():
        kb_saldi.scrivi(slug, saldi)  # sovrascrive lo snapshot di quella persona
        report.importate.append(slug)
    return report
