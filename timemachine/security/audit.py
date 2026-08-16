"""Audit — ogni proposta e ogni decisione umana si loggano (`01` §5, AI Act).

Due registri con due vite diverse:

- **inferenza** (prompt/output, versione modello): retention ≤ 30 giorni.
- **decisioni** umane: più lunga (AI Act + uso interno).

Nessun dato retributivo, nessun token, nessun CF nei log (`05` §4.5,
matcher `pii-in-log`).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from ..kb.paths import stato_root

RETENTION_INFERENZA_GIORNI = 30

_PII = re.compile(
    r"([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])"  # codice fiscale
    r"|(ya29\.[0-9A-Za-z_-]+)"
    r"|(AIza[0-9A-Za-z_-]+)"
    r"|(\b1//[0-9A-Za-z_-]{20,})"
    r"|(Bearer\s+[A-Za-z0-9._-]{10,})",
    re.I,
)


def _dir() -> Path:
    d = stato_root() / "audit"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pulisci(valore: Any) -> Any:
    if isinstance(valore, str):
        return _PII.sub("[redatto]", valore)
    if isinstance(valore, dict):
        return {k: ("[redatto]" if "token" in k.lower() or "password" in k.lower() else _pulisci(v)) for k, v in valore.items()}
    if isinstance(valore, list):
        return [_pulisci(v) for v in valore]
    if is_dataclass(valore) and not isinstance(valore, type):
        return _pulisci(asdict(valore))
    return valore


def _append(nome: str, record: dict[str, Any]) -> None:
    record = {"at": dt.datetime.now(dt.UTC).isoformat(), **_pulisci(record)}
    with (_dir() / f"{nome}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def hash_input(dati: Any) -> str:
    testo = json.dumps(dati, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()[:16]


def inferenza(
    agente: str,
    proposta_id: str,
    input_hash: str,
    modello: str,
    versione_prompt: str,
    esito: str,
    costo_stimato: float | None = None,
) -> None:
    _append(
        "inferenza",
        {
            "agente": agente,
            "proposta_id": proposta_id,
            "input_hash": input_hash,
            "modello": modello,
            "versione_prompt": versione_prompt,
            "esito": esito,
            "costo_stimato": costo_stimato,
        },
    )


def decisione(
    proposta_id: str, esito: str, da: str, motivo: str = "", diff: list | None = None
) -> None:
    _append(
        "decisioni",
        {"proposta_id": proposta_id, "esito": esito, "da": da, "motivo": motivo, "diff": diff or []},
    )


def accesso(caller: str, risorsa: str, esito: str) -> None:
    """Ogni read ha un `caller_id`; un 403 si logga (`05` §4.3, G2)."""
    _append("accessi", {"caller": caller, "risorsa": risorsa, "esito": esito})


def leggi(nome: str) -> list[dict[str, Any]]:
    p = _dir() / f"{nome}.jsonl"
    if not p.exists():
        return []
    return [json.loads(r) for r in p.read_text(encoding="utf-8").splitlines() if r.strip()]


def purga_inferenza(adesso: dt.datetime | None = None) -> int:
    """Retention: i record di inferenza oltre 30 giorni spariscono (G7)."""
    adesso = adesso or dt.datetime.now(dt.UTC)
    limite = adesso - dt.timedelta(days=RETENTION_INFERENZA_GIORNI)
    p = _dir() / "inferenza.jsonl"
    if not p.exists():
        return 0
    tenuti, buttati = [], 0
    for record in leggi("inferenza"):
        try:
            quando = dt.datetime.fromisoformat(record["at"])
        except (KeyError, ValueError):
            tenuti.append(record)
            continue
        if quando < limite:
            buttati += 1
        else:
            tenuti.append(record)
    p.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in tenuti), encoding="utf-8"
    )
    return buttati


def record_di(persona: str) -> dict[str, list[dict[str, Any]]]:
    """Diritto di accesso: estratto dei record riferibili a una persona."""
    fuori: dict[str, list[dict[str, Any]]] = {}
    for nome in ("inferenza", "decisioni", "accessi"):
        fuori[nome] = [
            r for r in leggi(nome) if persona in json.dumps(r, ensure_ascii=False, default=str)
        ]
    return fuori


def cancella_di(persona: str) -> int:
    """Diritto all'oblio: via i log a lei riferibili, gli altri restano (G6)."""
    tolti = 0
    for nome in ("inferenza", "decisioni", "accessi"):
        record = leggi(nome)
        tenuti = [
            r for r in record if persona not in json.dumps(r, ensure_ascii=False, default=str)
        ]
        tolti += len(record) - len(tenuti)
        (_dir() / f"{nome}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in tenuti), encoding="utf-8"
        )
    return tolti
