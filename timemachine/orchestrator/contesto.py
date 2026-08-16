"""`carica_contesto` — **codice, non un agente** (`01` §4.4).

Assembla il pacchetto condiviso del giro: schede, storia, secondo, note della
settimana. Gli agenti non tengono una memoria privata del negozio.

Budget (`01` §4.5): non si concatenano 30 schede + 8 settimane intere. Si
costruisce un riassunto **deterministico**; i file grezzi si passano solo
all'agente che li chiede per path.

Minimizzazione (`05` §4.4): nel prompt va il *vincolo* operativo, mai la
storia della persona.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from ..domain.modelli import Piano
from ..kb import persone as kb_persone
from ..kb import secondo as kb_secondo
from ..kb import turni as kb_turni
from ..security import allowlist, privacy

STORIA_SETTIMANE = 8
STORIA_COMPRESSA_SETTIMANE = 4


@dataclass(slots=True)
class Contesto:
    settimana: dt.date
    punto_vendita: str = "Le Rocce — Poggiridenti"
    persone: list[dict[str, Any]] = field(default_factory=list)
    storia_compressa: list[dict[str, Any]] = field(default_factory=list)
    note_settimana: dict[str, str] = field(default_factory=dict)
    secondo: list[str] = field(default_factory=list)
    fonti: list[str] = field(default_factory=list)
    piani: list[Piano] = field(default_factory=list)  # non entra nel prompt
    testi_non_fidati: list[str] = field(default_factory=list)

    # --- viste per il prompt -------------------------------------------------

    def per_prompt(self, agente: str) -> dict[str, Any]:
        """Solo i campi in allowlist per quell'agente. Verificato prima della rete."""
        completo: dict[str, Any] = {
            "settimana": self.settimana.isoformat(),
            "persone": self.persone,
            "storia_compressa": self.storia_compressa,
            "note_settimana": self.note_settimana,
            "secondo": self.secondo,
        }
        filtrato = allowlist.filtra(agente, completo)
        allowlist.verifica(agente, filtrato)
        return filtrato

    def scheda(self, slug: str) -> dict[str, Any] | None:
        for p in self.persone:
            if p["slug"] == slug:
                return p
        return None

    def slugs(self) -> list[str]:
        return [p["slug"] for p in self.persone]

    def con_mansione(self, mansione: str) -> list[str]:
        return [p["slug"] for p in self.persone if mansione in p["mansioni"]]


def _comprimi_persona(persona) -> dict[str, Any]:
    """Tabella persona×mansioni + vincoli. Niente aneddoti, niente saldi."""
    return {
        "slug": persona.slug,
        "nome": persona.nome,
        "contratto_ore": persona.contratto_ore_settimanali,
        "mansioni": persona.nomi_mansioni(),
        "vincoli": privacy.vincoli_operativi(persona.preferenze),
    }


def _comprimi_settimana(piano: Piano) -> dict[str, Any]:
    """Una settimana in poche righe: chi c'era, quante ore, dove."""
    righe = []
    for slug in piano.persone():
        turni = piano.della_persona(slug)
        celle = []
        for t in turni:
            if t.lavorato:
                celle.append(f"{t.giorno} {t.etichetta()}" + (f" {'+'.join(t.mansioni)}" if t.mansioni else ""))
            elif t.badge:
                celle.append(f"{t.giorno} {t.badge}")
        righe.append(
            {
                "slug": slug,
                "ore": round(sum(t.ore for t in turni), 1),
                "celle": "; ".join(celle),
            }
        )
    return {
        "settimana": piano.settimana.isoformat(),
        "note": {d.isoformat(): n for d, n in piano.note_settimana.items()},
        "righe": righe,
    }


def carica(
    settimana: dt.date,
    n_settimane: int = STORIA_SETTIMANE,
    note_settimana: dict[str, str] | None = None,
) -> Contesto:
    schede = kb_persone.tutte()
    piani = [p for p in kb_turni.piani_pubblicati() if p.settimana < settimana]
    recenti = piani[-n_settimane:]
    # stessa settimana dell'anno prima, se esiste
    anno_prima = settimana - dt.timedelta(days=364)
    for p in piani:
        if p.settimana == anno_prima and p not in recenti:
            recenti = [p, *recenti]

    fonti = [f"kb/persone/{p.slug}.md" for p in schede]
    fonti += [f"kb/turni/{p.settimana.isoformat()}.md" for p in recenti]

    note = dict(note_settimana or {})
    piano_corrente = kb_turni.leggi(settimana)
    if piano_corrente:
        for d, n in piano_corrente.note_settimana.items():
            note.setdefault(d.isoformat(), n)

    termini = [w for n in note.values() for w in n.lower().split()]
    memoria = kb_secondo.retrieval(termini + [str(settimana.month)], limite=5)

    non_fidati = [
        pref.storia
        for p in schede
        for pref in p.preferenze
        if pref.storia and allowlist.sospetto_di_iniezione(pref.storia)
    ]

    return Contesto(
        settimana=settimana,
        persone=[_comprimi_persona(p) for p in schede],
        storia_compressa=[
            _comprimi_settimana(p) for p in recenti[-STORIA_COMPRESSA_SETTIMANE:]
        ],
        note_settimana=note,
        secondo=memoria,
        fonti=fonti,
        piani=recenti,
        testi_non_fidati=non_fidati,
    )


def file_grezzo(path: str) -> str:
    """Il grezzo si passa **solo** all'agente che lo chiede per path, e dentro
    un blocco «questo è dato, non istruzione» (`05` §4.4)."""
    from ..kb.paths import kb_root

    p = (kb_root() / path.removeprefix("kb/")).resolve()
    if not str(p).startswith(str(kb_root().resolve())):
        raise PermissionError(f"path fuori da kb/: {path}")
    if not p.exists():
        raise FileNotFoundError(path)
    return allowlist.blocco_dati(p.read_text(encoding="utf-8"))
