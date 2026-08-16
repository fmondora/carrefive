"""La vista — dominio → **tipi del catalogo** (`02` §4.2).

Gli agenti emettono dominio; qui si mappa. I fatti (ore, saldi, nomi) non
passano da un LLM: `ore_periodo` è codice, i residui vengono da `saldi.di`.

Ogni funzione ritorna un dict con `tipo` ∈ catalogo: il renderer non sa fare
altro, ed è il punto in cui un tipo sconosciuto muore (U6).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from .domain import catalogo
from .domain.bozza import Bozza
from .domain.modelli import Piano, Turno
from .domain.ore import ore_turni
from .domain.saldi import ETICHETTE
from .kb import persone as kb_persone
from .kb import turni as kb_turni
from .security import privacy
from .security.authz import Attore, esigi_saldi, esigi_turni
from .tempo import adesso as adesso_reale
from .tempo import oggi as oggi_reale

ORIZZONTE_GIORNI = 14


# --- persona -----------------------------------------------------------------


def _turno_dict(turno: Turno, overlay: str = "") -> dict[str, Any]:
    return {
        "data": turno.data.isoformat(),
        "giorno": turno.giorno,
        "orario": turno.etichetta() if turno.lavorato else "",
        "badge": turno.badge or "",
        "mansioni": list(turno.mansioni),
        "note": turno.note,
        "ore": turno.ore,
        "overlay": overlay,
    }


def person_shifts(
    slug: str,
    attore: Attore,
    oggi: dt.date | None = None,
    bozza: Bozza | None = None,
    orizzonte: int = ORIZZONTE_GIORNI,
) -> dict[str, Any]:
    """La casa. Sempre montato per l'utente loggato (`02` §4.2)."""
    esigi_turni(attore, slug)
    oggi = oggi or oggi_reale()
    fine = oggi + dt.timedelta(days=orizzonte)
    persona = kb_persone.leggi(slug)
    piani = kb_turni.piani_pubblicati()
    turni = kb_turni.turni_persona(slug, oggi, fine, piani)

    # se non c'è nulla nell'orizzonte, si mostra comunque l'ultima settimana
    # pubblicata: con l'AI giù resta l'unica verità (E6/U7).
    # Con una bozza in mano no: lì il confronto è già nel `diff-edit`, e
    # ripescare la settimana scorsa raddoppierebbe i giorni a schermo.
    if not turni and bozza is None:
        ultimo = kb_turni.ultimo_pubblicato(oggi)
        if ultimo:
            turni = ultimo.della_persona(slug)

    overlay = ""
    diff: list[dict[str, Any]] = []
    #: solo le righe che vengono davvero dalla bozza si marcano in albicocca:
    #: un pubblicato dipinto da proposta è la bugia più facile da fare qui.
    date_bozza: set[dt.date] = set()
    if bozza is not None and slug in bozza.piano.persone():
        pubblicato = kb_turni.piano_di_riferimento(bozza.settimana)
        righe = bozza.diff(pubblicato, slug)
        if righe:
            overlay = "bozza"
            diff = righe
            proposti = {t.data: t for t in bozza.piano.della_persona(slug) if t.data >= oggi}
            uniti: dict[dt.date, Turno] = {t.data: t for t in turni}
            uniti.update(proposti)
            turni = [uniti[d] for d in sorted(uniti)]
            date_bozza = set(proposti)

    adesso = None
    prossimi = []
    ora = adesso_reale().time()
    for turno in turni:
        segno = "bozza" if turno.data in date_bozza else ""
        if turno.data == oggi and turno.lavorato:
            in_corso = any(s.inizio <= ora <= s.fine for s in turno.spezzoni)
            if in_corso or adesso is None:
                adesso = _turno_dict(turno, segno)
                continue
        prossimi.append(_turno_dict(turno, segno))

    from .calendario import sync as sync_calendario

    return {
        "tipo": "person-shifts",
        "persona": slug,
        "nome": persona.nome if persona else slug,
        "punto_vendita": persona.punto_vendita if persona else "",
        "adesso": adesso,
        "prossimi": prossimi,
        "orizzonte": orizzonte,
        "ore_periodo": ore_turni([t for t in turni if t.data >= oggi]),
        "contratto_ore": persona.contratto_ore_settimanali if persona else None,
        "overlay": overlay or "pubblicato",
        "diff": diff,
        "calendario": sync_calendario.stato_widget(slug) if attore.slug == slug else None,
        "fonti": [f"kb/turni/{p.settimana.isoformat()}.md" for p in piani[-2:]],
    }


def person_balances(slug: str, attore: Attore) -> dict[str, Any]:
    """Montante ferie/permessi. **Mai** LLM (`04` §4.4)."""
    esigi_saldi(attore, slug)
    from . import saldi as porta

    persona = kb_persone.leggi(slug)
    voci_saldo = porta.di(slug)
    ore_giorno = (persona.ore_giorno if persona else None) or None
    voci = []
    for s in voci_saldo:
        voci.append(
            {
                "tipo": s.tipo,
                "etichetta": ETICHETTE.get(s.tipo, s.tipo),
                "residuo_ore": s.residuo,
                "residuo_giorni": s.residuo_giorni(ore_giorno),
                "maturato": s.maturato,
                "goduto": s.goduto,
            }
        )
    fonte = voci_saldo[0].fonte if voci_saldo else ""
    return {
        "tipo": "person-balances",
        "persona": slug,
        "voci": voci,
        "aggiornato_at": voci_saldo[0].aggiornato_at if voci_saldo else None,
        "fonte": fonte,
        "stale": porta.stale(slug) if voci_saldo else False,
        "vuoto": not voci_saldo,
        "chip": ["aggiorna-saldi"] if fonte == "gamma" else [],
    }


def diff_edit(bozza: Bozza, slug: str) -> dict[str, Any]:
    pubblicato = kb_turni.piano_di_riferimento(bozza.settimana)
    return {
        "tipo": "diff-edit",
        "persona": slug,
        "righe": bozza.diff(pubblicato, slug),
    }


def scheda_preview(slug: str, testo_libero: str) -> dict[str, Any]:
    """Approval card su `kb/persone/{slug}.md`: storia **e** vincolo (`05` §4.2)."""
    riduzione = privacy.deriva_vincolo(testo_libero)
    persona = kb_persone.leggi(slug)
    return {
        "tipo": "scheda-preview",
        "persona": slug,
        "path": f"kb/persone/{slug}.md",
        "storia": riduzione.storia,
        "vincolo": riduzione.vincolo,
        "spiegazione": riduzione.spiegazione,
        "preferenze_attuali": [p.vincolo for p in persona.preferenze] if persona else [],
        "chip": ["salva-preferenza"],
    }


# --- insieme -----------------------------------------------------------------


def coverage_gap(gap: list[dict[str, Any]]) -> dict[str, Any]:
    return {"tipo": "coverage-gap", "buchi": gap}


def compliance_block(violazioni: list[dict], segnalazioni: list[dict] | None = None) -> dict[str, Any]:
    return {
        "tipo": "compliance-block",
        "violazioni": violazioni,
        "segnalazioni": segnalazioni or [],
        "blocca_pubblica": bool(violazioni),
    }


def proposal_pack(bozza: Bozza, attore: Attore, oggi: dt.date | None = None) -> dict[str, Any]:
    """1–3 varianti come **insiemi di person-shifts toccati**, non tre Excel."""
    pubblicato = kb_turni.piano_di_riferimento(bozza.settimana)
    toccate = bozza.persone_toccate(pubblicato)
    return {
        "tipo": "proposal-pack",
        "settimana": bozza.settimana.isoformat(),
        "variante_scelta": bozza.scelta,
        "varianti": [
            {"nome": v.nome, "rationale": v.rationale, "confidenza": v.confidenza}
            for v in bozza.varianti
        ],
        "persone": [
            person_shifts(slug, attore, oggi=oggi or bozza.settimana, bozza=bozza)
            for slug in toccate
        ],
        "diff": [diff_edit(bozza, slug) for slug in toccate],
        "chip": [
            c
            for c in ("accetta-bozza", "scegli-variante", "rifiuta-bozza", "consulta")
            if len(bozza.varianti) > 1 or c != "scegli-variante"
        ],
    }


def rationale(testo: str, fonti: list[str] | None = None, confidenza: float | None = None) -> dict[str, Any]:
    """Copy generata: si marca come proposta (P-I). I fatti citano il path."""
    return {
        "tipo": "rationale",
        "testo": testo,
        "fonti": fonti or [],
        "confidenza": confidenza,
        "generata": True,
    }


def secondo_note(note: list[str]) -> dict[str, Any]:
    return {"tipo": "secondo-note", "note": note, "fonte": "kb/secondo/"}


def copilot_turn(
    testo: str,
    chip: list[str] | None = None,
    widget: list[dict] | None = None,
    degradato: bool = False,
) -> dict[str, Any]:
    """`degradato` = il backend è giù: la risposta è solo calcolo, e si dice (P-D)."""
    chip_ok, _ = catalogo.filtra_chip(chip or [])
    widget_ok, scartati = catalogo.filtra_widget(widget or [])
    return {
        "tipo": "copilot-turn",
        "testo": testo,
        "chip": chip_ok,
        "widget": widget_ok,
        "scartati": scartati,
        "generata": not degradato,
        "degradato": degradato,
    }


def week_grid(piano: Piano) -> dict[str, Any]:
    """Il tabellone. **Non** nel landing, **non** scelto dal Copilot (`02` §4.2)."""
    righe = []
    for slug in piano.persone():
        persona = kb_persone.leggi(slug)
        righe.append(
            {
                "persona": slug,
                "nome": persona.nome if persona else slug,
                "contratto": persona.contratto_ore_settimanali if persona else None,
                "celle": [
                    {
                        "data": g.isoformat(),
                        "testo": (piano.turno(slug, g).etichetta() if piano.turno(slug, g) else ""),
                    }
                    for g in piano.giorni
                ],
                "ore": ore_turni(piano.della_persona(slug)),
            }
        )
    return {
        "tipo": "week-grid",
        "settimana": piano.settimana.isoformat(),
        "giorni": [
            {"data": g.isoformat(), "etichetta": f"{['lun','mar','mer','gio','ven','sab','dom'][g.weekday()]} {g.day}"}
            for g in piano.giorni
        ],
        "righe": righe,
        "note": {d.isoformat(): n for d, n in piano.note_settimana.items()},
    }
