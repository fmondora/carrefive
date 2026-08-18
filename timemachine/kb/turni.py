"""Settimane di turni — `kb/turni/YYYY-MM-DD.md` (lunedì).

Il tabellone resta la knowledge scritta (`02` §3). Qui si legge e — solo dopo
`pubblica`, che è un atto umano (`01` §4.4 regola 2) — si riscrive.
Il consuntivo si **aggiunge**, non sovrascrive il piano pubblicato.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from ..domain.modelli import GIORNI, Piano, Spezzone, Turno, slug_persona
from . import paths
from .celle import formatta_cella, parse_cella

_INTESTAZIONE_GIORNO = re.compile(r"^(lun|mar|mer|gio|ven|sab|dom)\s+(\d{1,2})", re.I)
_NOTA_GIORNO = re.compile(r"^(lun|mar|mer|gio|ven|sab|dom)\s+(\d{1,2})/(\d{1,2})", re.I)
_META = re.compile(r"^-\s*([a-z_]+)\s*:\s*(.+?)\s*$", re.I)

INTESTAZIONE_TABELLA = (
    "| Contr. | Persona | lun {g0} | mar {g1} | mer {g2} | gio {g3} | ven {g4} | sab {g5} | dom {g6} | h |"
)


def percorso(settimana: dt.date) -> Path:
    return paths.dir_turni() / f"{settimana.isoformat()}.md"


def lunedi_di(data: dt.date) -> dt.date:
    return data - dt.timedelta(days=data.weekday())


def _celle(riga: str) -> list[str]:
    if not riga.strip().startswith("|"):
        return []
    return [c.strip() for c in riga.strip().strip("|").split("|")]


def parse(testo: str, settimana: dt.date) -> Piano:
    piano = Piano(settimana=settimana)
    meta_ok = True
    sezione = ""
    giorni = piano.giorni

    for riga in testo.splitlines():
        if riga.startswith("## "):
            sezione = riga[3:].strip().lower()
            continue
        if meta_ok:
            m = _META.match(riga.strip())
            if m:
                chiave, valore = m.group(1).lower(), m.group(2).strip()
                if chiave == "punto_vendita":
                    piano.punto_vendita = valore
                elif chiave == "stato":
                    piano.stato = "bozza" if valore.startswith("bozza") else "pubblicato"
                elif chiave == "fonte":
                    piano.fonte = valore.strip("`")
                continue

        celle = _celle(riga)
        if not celle:
            continue
        if set("".join(celle)) <= set("-: "):
            continue

        if sezione.startswith("note"):
            if len(celle) >= 2:
                m = _NOTA_GIORNO.match(celle[0])
                if m:
                    giorno = int(m.group(2))
                    for d in giorni:
                        if d.day == giorno:
                            piano.note_settimana[d] = celle[1]
                            break
            continue

        if sezione.startswith("piano") or not sezione:
            if len(celle) < 9:
                continue
            if celle[1].lower().startswith("persona"):
                continue
            nome = celle[1]
            if not nome or nome.startswith("-"):
                continue
            slug = slug_persona(nome)
            for i, giorno in enumerate(giorni):
                grezzo = celle[2 + i] if 2 + i < len(celle) else ""
                spezzoni, badge, note = parse_cella(grezzo)
                piano.imposta(
                    Turno(
                        persona=slug,
                        data=giorno,
                        spezzoni=spezzoni,
                        badge=badge,
                        note=note,
                        grezzo=grezzo,
                    )
                )
    return piano


def leggi(settimana: dt.date) -> Piano | None:
    p = percorso(settimana)
    if not p.exists():
        return None
    return parse(p.read_text(encoding="utf-8"), settimana)


def settimane_disponibili() -> list[dt.date]:
    d = paths.dir_turni()
    if not d.exists():
        return []
    out = []
    for f in sorted(d.glob("*.md")):
        try:
            out.append(dt.date.fromisoformat(f.stem))
        except ValueError:
            continue
    return out


def ultimo_pubblicato(alla_data: dt.date | None = None) -> Piano | None:
    settimane = settimane_disponibili()
    if not settimane:
        return None
    if alla_data is not None:
        passate = [s for s in settimane if s <= lunedi_di(alla_data)]
        settimane = passate or settimane
    for s in reversed(settimane):
        piano = leggi(s)
        if piano and piano.stato == "pubblicato":
            return piano
    return None


def piano_di_riferimento(settimana: dt.date) -> Piano | None:
    """Contro cosa si confronta una bozza.

    Se quella settimana è già pubblicata, è lei (si sta ripubblicando). Se è
    nuova, il riferimento è **l'ultima settimana pubblicata**: è quella che il
    manager ha in testa. Confrontare una settimana nuova col nulla produce un
    diff in cui «cambiano tutti», cioè nessuna informazione.
    """
    return leggi(settimana) or ultimo_pubblicato(settimana - dt.timedelta(days=1))


def piani_pubblicati() -> list[Piano]:
    out = []
    for s in settimane_disponibili():
        p = leggi(s)
        if p and p.stato == "pubblicato":
            out.append(p)
    return out


def turni_persona(
    slug: str, da: dt.date, a: dt.date, piani: list[Piano] | None = None
) -> list[Turno]:
    """Tutti i turni pubblicati di una persona nell'intervallo, ordinati."""
    piani = piani if piani is not None else piani_pubblicati()
    fuori: list[Turno] = []
    for piano in piani:
        for turno in piano.della_persona(slug):
            if da <= turno.data <= a:
                fuori.append(turno)
    fuori.sort(key=lambda t: t.data)
    return fuori


# --- scrittura (dopo `pubblica`) --------------------------------------------

_TESTATA = """# Turni {inizio} – {fine}

- punto_vendita: {pv}
- stato: {stato}
- fonte: {fonte}
"""


def _riga_persona(piano: Piano, slug: str, contratto: str) -> str:
    celle = []
    ore = 0.0
    for giorno in piano.giorni:
        t = piano.turno(slug, giorno)
        if t is None:
            celle.append("")
            continue
        ore += t.ore
        celle.append(formatta_cella(t.spezzoni, t.badge, t.note))
    nome = _nome_visibile(slug)
    h = f"{ore:g}" if ore else ""
    return "| " + " | ".join([contratto, nome, *celle, h]) + " |"


def _nome_visibile(slug: str) -> str:
    from . import persone as kb_persone

    p = kb_persone.leggi(slug)
    return p.nome if p else slug.replace("-", " ").title()


def serializza(piano: Piano, consuntivo: str = "") -> str:
    from . import persone as kb_persone

    giorni = piano.giorni
    testata = _TESTATA.format(
        inizio=giorni[0].strftime("%d/%m/%Y"),
        fine=giorni[-1].strftime("%d/%m/%Y"),
        pv=piano.punto_vendita or "Le Rocce — Poggiridenti",
        stato=piano.stato,
        fonte=f"`{piano.fonte}`" if piano.fonte else "TIME MACHINE — pubblicazione",
    )
    parti = [testata]

    if piano.note_settimana:
        parti.append("## Note di settimana (testata del foglio)\n")
        parti.append("| Giorno | Nota operativa |")
        parti.append("|---|---|")
        for d in giorni:
            if d in piano.note_settimana:
                parti.append(f"| {GIORNI[d.weekday()]} {d.strftime('%d/%m')} | {piano.note_settimana[d]} |")
        parti.append("")

    parti.append("## Piano\n")
    parti.append(
        "Abbreviazioni: `R` riposo · `F` ferie · `C` cassa · `B` bar · `M` macelleria · `G` gastronomia\n"
    )
    parti.append(INTESTAZIONE_TABELLA.format(**{f"g{i}": giorni[i].day for i in range(7)}))
    parti.append("|" + "---|" * 10)
    schede = kb_persone.per_slug()
    for slug in piano.persone():
        persona = schede.get(slug)
        contratto = (
            f"{persona.contratto_ore_settimanali:g}"
            if persona and persona.contratto_ore_settimanali
            else "—"
        )
        parti.append(_riga_persona(piano, slug, contratto))
    parti.append("")
    parti.append("## Consuntivo\n")
    parti.append(consuntivo.strip() or "Non c'è. Si aggiunge qui dopo le timbrature, senza riscrivere il pubblicato.")
    return "\n".join(parti) + "\n"


def _consuntivo_esistente(settimana: dt.date) -> str:
    p = percorso(settimana)
    if not p.exists():
        return ""
    testo = p.read_text(encoding="utf-8")
    m = re.search(r"^## Consuntivo\s*$", testo, re.M)
    if not m:
        return ""
    corpo = testo[m.end() :].strip()
    if corpo.startswith("Non c'è"):
        return ""
    return corpo


def scrivi(piano: Piano) -> Path:
    """Materializza il piano. Chiamata **solo** dal gate `pubblica` di `01`."""
    p = percorso(piano.settimana)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(serializza(piano, _consuntivo_esistente(piano.settimana)), encoding="utf-8")
    return p


def aggiungi_consuntivo(settimana: dt.date, testo: str) -> Path:
    piano = leggi(settimana)
    if piano is None:
        raise FileNotFoundError(f"settimana {settimana} non in kb")
    precedente = _consuntivo_esistente(settimana)
    corpo = f"{precedente}\n\n{testo}".strip() if precedente else testo.strip()
    p = percorso(settimana)
    p.write_text(serializza(piano, corpo), encoding="utf-8")
    return p


def spezzone_da_testo(testo: str) -> tuple[Spezzone, ...]:
    spezzoni, _, _ = parse_cella(testo)
    return spezzoni
