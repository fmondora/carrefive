"""Dove vive la knowledge.

`kb/` è **archivio di dati personali** (`05` §3), non uno scratch.
Root sovrascrivibile con `TM_KB` (i test ci puntano una copia).
"""

from __future__ import annotations

import os
from pathlib import Path


def radice_repo() -> Path:
    return Path(__file__).resolve().parents[2]


def kb_root() -> Path:
    env = os.environ.get("TM_KB")
    return Path(env).resolve() if env else radice_repo() / "kb"


def dir_persone() -> Path:
    return kb_root() / "persone"


def dir_turni() -> Path:
    return kb_root() / "turni"


def dir_saldi() -> Path:
    return kb_root() / "saldi"


def dir_secondo() -> Path:
    return kb_root() / "secondo"


def stato_root() -> Path:
    """Store applicativo: sessioni, account, token, audit.

    **Mai** dentro `kb/` (`03` §3, `05` §4.5). Default `.stato/` alla radice,
    sovrascrivibile con `TM_STATO`.
    """
    env = os.environ.get("TM_STATO")
    p = Path(env).resolve() if env else radice_repo() / ".stato"
    p.mkdir(parents=True, exist_ok=True)
    return p
