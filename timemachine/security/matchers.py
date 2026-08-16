"""Matcher di dominio, stile DeepSec (`05` §4.7).

DeepSec è il *come verifichiamo*; questa è la parte gratis della pipeline —
`scan`, regex sul nostro dominio. Il `process` con agente e il `revalidate`
arrivano quando si onborda il repo; qui c'è ciò che gira già in CI.

Storia **append-only**: un re-scan non cancella un finding, lo marca
`fixed` / `false-positive`.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..kb.paths import radice_repo


@dataclass(frozen=True, slots=True)
class Matcher:
    slug: str
    cerca: re.Pattern[str]
    perche: str
    gravita: str = "HIGH"
    solo_in: tuple[str, ...] = ()  # prefissi di path; vuoto = ovunque
    escludi: tuple[str, ...] = ()


MATCHERS: tuple[Matcher, ...] = (
    Matcher(
        slug="kb-secret",
        cerca=re.compile(
            r"(refresh_token|access_token|client_secret|Bearer\s+[A-Za-z0-9._-]{10,}|"
            r"AIza[0-9A-Za-z_-]{10,}|ya29\.[0-9A-Za-z_-]{10,}|\$2[aby]\$\d{2}\$)"
        ),
        perche="token o hash dentro kb/ — C8 di `03`",
        solo_in=("kb/",),
    ),
    Matcher(
        slug="prompt-full-kb",
        cerca=re.compile(r"read_text\(\)[^\n]{0,40}\bprompt\b|prompt\s*\+=\s*.*read_text\(\)"),
        perche="loader che concatena schede raw nel prompt senza allowlist — `01` §4.5",
        escludi=("timemachine/security/matchers.py",),
    ),
    Matcher(
        slug="balances-list-all",
        cerca=re.compile(r"def\s+\w*saldi\w*\(.*\)\s*->\s*.*\bdict\[str,\s*list\[Saldo\]\]|/saldi/tutti|saldi_di_tutti"),
        perche="endpoint che elenca i residui del punto vendita — S4 di `04`",
    ),
    Matcher(
        slug="calendar-on-draft",
        cerca=re.compile(r"(sincronizza|upsert)\([^)]*bozza|bozza[^\n]{0,40}\.upsert\("),
        perche="write su Calendar prima di `pubblica` — C7 di `03`",
        escludi=("timemachine/security/matchers.py",),
    ),
    Matcher(
        slug="llm-writes-published",
        cerca=re.compile(r"(llm|genera_json|Copilot)[^\n]{0,60}(kb_turni\.scrivi|\.pubblica\()"),
        perche="path di pubblicazione senza gate umano — `01` §5",
        escludi=("timemachine/security/matchers.py",),
    ),
    Matcher(
        slug="anomaly-individual-score",
        cerca=re.compile(r"\b(score|punteggio|ranking|classifica)[_\s]*(persona|dipendente|individual)", re.I),
        perche="scoring individuale — art. 4 Statuto",
        escludi=("timemachine/security/matchers.py", "timemachine/kb/secondo.py", "timemachine/agents/anomaly.py"),
    ),
    Matcher(
        slug="pii-in-log",
        cerca=re.compile(r"(print|log\w*)\([^)]*(password|token|codice_fiscale|residuo)", re.I),
        perche="CF, token o residui nei log applicativi — minimizzazione `05`",
        escludi=("timemachine/security/matchers.py",),
    ),
)

ESTENSIONI = {".py", ".md", ".html", ".js", ".css", ".json", ".yaml", ".yml", ".toml"}
IGNORA = {".git", ".venv", "__pycache__", ".stato", "node_modules", ".claude", ".deepsec"}


@dataclass(slots=True)
class Finding:
    matcher: str
    file: str
    riga: int
    estratto: str
    gravita: str
    perche: str
    stato: str = "candidate"  # candidate | fixed | false-positive
    visto_at: str = field(default_factory=lambda: dt.date.today().isoformat())

    @property
    def chiave(self) -> str:
        return f"{self.matcher}:{self.file}:{self.estratto[:40]}"


def _file_da_scansionare(radice: Path) -> list[Path]:
    fuori = []
    for p in radice.rglob("*"):
        if not p.is_file() or p.suffix not in ESTENSIONI:
            continue
        if any(parte in IGNORA for parte in p.parts):
            continue
        fuori.append(p)
    return fuori


def scan(radice: Path | None = None) -> list[Finding]:
    radice = radice or radice_repo()
    fuori: list[Finding] = []
    for percorso in _file_da_scansionare(radice):
        relativo = str(percorso.relative_to(radice))
        try:
            testo = percorso.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for m in MATCHERS:
            if m.solo_in and not any(relativo.startswith(p) for p in m.solo_in):
                continue
            if any(relativo.startswith(p) for p in m.escludi):
                continue
            for numero, riga in enumerate(testo.splitlines(), start=1):
                trovato = m.cerca.search(riga)
                if trovato:
                    fuori.append(
                        Finding(
                            matcher=m.slug,
                            file=relativo,
                            riga=numero,
                            estratto=riga.strip()[:160],
                            gravita=m.gravita,
                            perche=m.perche,
                        )
                    )
    return fuori


def percorso_storia() -> Path:
    """`docs/security/findings/` come da `05` §4.7 (`TM_FINDINGS` per i test)."""
    env = os.environ.get("TM_FINDINGS")
    d = Path(env) if env else radice_repo() / "docs" / "security" / "findings"
    d.mkdir(parents=True, exist_ok=True)
    return d / "findings.json"


def storia() -> list[Finding]:
    p = percorso_storia()
    if not p.exists():
        return []
    return [Finding(**d) for d in json.loads(p.read_text(encoding="utf-8"))]


def registra(nuovi: list[Finding]) -> dict[str, int]:
    """Append-only: chi non c'è più diventa `fixed`, non sparisce."""
    vecchi = {f.chiave: f for f in storia()}
    visti = {f.chiave for f in nuovi}
    for f in nuovi:
        if f.chiave not in vecchi:
            vecchi[f.chiave] = f
        elif vecchi[f.chiave].stato == "fixed":
            vecchi[f.chiave].stato = "candidate"
            vecchi[f.chiave].visto_at = f.visto_at
    risolti = 0
    for chiave, f in vecchi.items():
        if chiave not in visti and f.stato == "candidate":
            f.stato = "fixed"
            risolti += 1
    percorso_storia().write_text(
        json.dumps([asdict(f) for f in vecchi.values()], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    aperti = sum(1 for f in vecchi.values() if f.stato == "candidate")
    return {"nuovi": len(nuovi), "aperti": aperti, "risolti": risolti}


def blocca_merge(findings: list[Finding]) -> bool:
    """HIGH+ aperti = merge bloccato finché `revalidate` non dice altro."""
    return any(f.gravita in ("HIGH", "CRITICAL") and f.stato == "candidate" for f in findings)
