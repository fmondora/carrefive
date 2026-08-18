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
    #: una bozza che cade fuori dall'orizzonte non ha niente da dire su questa
    #: vista: dipingere la settimana in corso con la proposta di quella dopo è
    #: la bugia più comoda (Book 08, «Overlay bozza su me»).
    if bozza is not None and not (oggi <= bozza.settimana <= fine):
        bozza = None
    if bozza is not None and slug in bozza.piano.persone():
        pubblicato = kb_turni.piano_di_riferimento(bozza.settimana)
        righe = bozza.diff(pubblicato, slug)
        # I turni della bozza si mostrano **sempre**, anche a chi la bozza non
        # tocca: guardando un candidato per un buco si vuole vedere la sua
        # settimana, non una card vuota che dice «nessun turno» mentre il
        # rationale dice «è già in turno altrove».
        proposti = {t.data: t for t in bozza.piano.della_persona(slug) if t.data >= oggi}
        uniti: dict[dt.date, Turno] = {t.data: t for t in turni}
        uniti.update(proposti)
        turni = [uniti[d] for d in sorted(uniti)]
        if righe:
            # il badge e l'albicocca restano a chi cambia davvero
            overlay = "bozza"
            diff = righe
            date_bozza = {dt.date.fromisoformat(r["data"]) for r in righe} & set(proposti)

    #: «Adesso» è un orologio, non un'ancora: vale solo se la card parte da
    #: **oggi**. Una card puntata alla settimana in bozza che dice «adesso
    #: 10-14» sta parlando di un lunedì che deve ancora arrivare — sul
    #: candidato di un buco di martedì è una bugia di orologio (Book 02 A2).
    mostra_adesso = oggi == oggi_reale()
    adesso = None
    prossimi = []
    ora = adesso_reale().time()
    for turno in turni:
        segno = "bozza" if turno.data in date_bozza else ""
        if mostra_adesso and turno.data == oggi and turno.lavorato:
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
        "mostra_adesso": mostra_adesso,
        "riferimento": oggi.isoformat(),
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


GIORNI_ESTESI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")


def scheda_preview(slug: str, testo_libero: str, data: str = "") -> dict[str, Any]:
    """Approval card su `kb/persone/{slug}.md`: storia **e** vincolo (`05` §4.2).

    `data` è l'**ambito**: con una data il vincolo vale solo quel giorno, e la
    card lo dice in italiano («solo il 02/07») invece di lasciare che sia il
    token `no_turno: gio` a farlo capire — che vuol dire il contrario.
    Chi vuole la regola settimanale la chiede con la seconda chip.
    """
    riduzione = privacy.deriva_vincolo(testo_libero)
    persona = kb_persone.leggi(slug)
    giorno_esteso = ""
    ambito = ""
    spiegazione = riduzione.spiegazione
    if data:
        try:
            quel_giorno = dt.date.fromisoformat(data)
        except ValueError:
            data = ""
        else:
            giorno_esteso = GIORNI_ESTESI[quel_giorno.weekday()]
            ambito = f"solo il {quel_giorno.day:02d}/{quel_giorno.month:02d}"
            #: la spiegazione deve dire ciò che si vedrà davvero: `operativa()`
            #: appende l'ambito, e prometterne uno diverso è la bugia più
            #: facile da fare proprio nella card che serve a non farne
            if riduzione.vincolo != "da_chiarire":
                spiegazione = (
                    f"Il manager e lo Scheduling vedranno «{riduzione.vincolo}» "
                    f"limitato al {quel_giorno.day:02d}/{quel_giorno.month:02d}, non il motivo."
                )
    return {
        "tipo": "scheda-preview",
        "persona": slug,
        "path": f"kb/persone/{slug}.md",
        "storia": riduzione.storia,
        "vincolo": riduzione.vincolo,
        "spiegazione": spiegazione,
        "data": data,
        "ambito": ambito,
        #: l'etichetta della seconda chip: «tutti i giovedì»
        "ricorrente": f"tutti i {giorno_esteso}" if giorno_esteso else "",
        "preferenze_attuali": [p.vincolo for p in persona.preferenze] if persona else [],
        "chip": ["salva-preferenza"],
    }


# --- insieme -----------------------------------------------------------------


def coverage_gap(
    gap: list[dict[str, Any]], primario: tuple[str, str, str] | None = None
) -> dict[str, Any]:
    """I buchi. **Non** un veto: sono ore scoperte, non una violazione.

    `primario` è la chiave `(data, fascia, reparto)` dell'unica riga che sta
    aperta — il prossimo copribile, calcolato dal chiamante. Quindici chip
    identiche sono un muro: si legge un numero e si tocca una riga, il resto
    sta in disclosure (Book 02 Loop A3).
    """
    buchi = []
    for g in gap:
        b = dict(g)
        b["primario"] = primario is not None and (
            (str(g["data"]), str(g["fascia"]), str(g["reparto"])) == primario
        )
        buchi.append(b)
    return {"tipo": "coverage-gap", "buchi": buchi}


def candidati_gap(
    bozza: Bozza,
    attore: Attore,
    data: dt.date,
    fascia: str,
    reparto: str,
    liberi: list[str],
    orario: str,
) -> list[dict[str, Any]]:
    """Dal buco alle persone. **Nessun tipo nuovo**: `rationale` + `person-shifts`.

    Gli slug arrivano già calcolati da `scheduling.candidati_per_gap`: qui si
    mappa e basta. `vista` non importa `agents/` — è l'invariante verificato da
    `tests/test_confine.py`, e vale anche quando la funzione chiamata è
    deterministica.

    La copy è deterministica anche se il tipo è «Gen copy»: qui non c'è niente
    da interpretare — si contano le persone e si dice quante sono (Book 03).
    Ogni card porta con sé il bersaglio di `sposta-turno`, così la conferma
    parte già compilata e non c'è una chip nuda da nessuna parte.
    """
    quando = f"{['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom'][data.weekday()]} {data.day:02d}/{data.month:02d}"
    if not liberi:
        return [
            rationale(
                f"Nessuno con la mansione «{reparto}» è libero o spostabile {quando} "
                f"in fascia {fascia}. I riposi e le ferie non entrano in questa lista: "
                "un riposo si tocca a mano, ed è una tua decisione.",
                fonti=[f"kb/turni/{bozza.settimana.isoformat()}.md"],
            )
        ]

    #: chi è già in turno quel giorno va etichettato: spostarlo è un secondo
    #: atto, non un buco da riempire a costo zero
    in_turno = {
        slug
        for slug in liberi
        if (t := bozza.piano.turno(slug, data)) is not None and t.lavorato
    }
    testa = (
        f"{len(liberi)} con la mansione «{reparto}» {quando}"
        + (
            f" — già in turno altrove: {', '.join(sorted(in_turno))}. Spostarli è un cambio, non un buco."
            if in_turno
            else ", liberi quel giorno."
        )
    )
    fuori: list[dict[str, Any]] = [
        rationale(testa, fonti=[f"kb/turni/{bozza.settimana.isoformat()}.md"])
    ]
    for slug in liberi:
        card = person_shifts(slug, attore, oggi=bozza.settimana, bozza=bozza)
        attuale = bozza.piano.turno(slug, data)
        card["sposta"] = {
            "persona": slug,
            "data": data.isoformat(),
            # l'**orario** (7-12), non il nome della fascia: «pomeriggio» sul
            # piano diventerebbe un badge da zero ore, non un turno
            "fascia": orario,
            "etichetta_fascia": fascia,
            "reparto": reparto,
            "gia_in_turno": slug in in_turno,
            # il soggetto della card è **il buco**, non la settimana di chi lo
            # tappa: giorno e fascia stanno scritti sulla card (Book 02 A2)
            "quando": quando,
            # `imposta` sostituisce la cella-giorno: si dice cosa si perde
            "prima": (attuale.etichetta().replace("–", "-") if attuale else ""),
        }
        fuori.append(card)
    return fuori


def celle_blocco(
    bozza: Bozza,
    attore: Attore,
    violazione: dict,
    mosse: list[dict],
) -> list[dict[str, Any]]:
    """Dal blocco alle celle. **Nessun tipo nuovo**: `rationale` + `person-shifts`.

    Stesso contratto del gap: un blocco è un buco che riguarda *una* persona.
    Le mosse arrivano già calcolate e già verificate da
    `compliance.celle_che_sciolgono` — `vista` non importa `agents/`
    (`tests/test_confine.py`), e qui si mappa e basta.

    Le mosse si attaccano **alla riga del giorno** a cui appartengono: la cella
    è il posto dove il gesto ha senso, non un elenco di bottoni in fondo.
    """
    slug = str(violazione.get("persona") or "")
    dettaglio = str(violazione.get("dettaglio") or "")
    persona = kb_persone.leggi(slug)
    nome = persona.nome if persona else slug

    card = person_shifts(slug, attore, oggi=bozza.settimana, bozza=bozza)
    per_giorno: dict[str, list[dict]] = {}
    for m in mosse:
        per_giorno.setdefault(str(m["data"]), []).append(m)
    for riga in card["prossimi"]:
        riga["mosse"] = per_giorno.get(riga["data"], [])
    card["blocco"] = dettaglio

    if mosse:
        testo = (
            f"{nome} — {dettaglio}. Ho provato le celle della sua settimana in bozza, "
            f"una alla volta: {len(mosse)} bastano da sole a togliere il blocco. "
            "Quale, lo decidi tu: accorciare una persona non è una cosa che faccio io."
        )
    else:
        testo = (
            f"{nome} — {dettaglio}. Nessuna singola cella della sua settimana toglie "
            "il blocco: qui servono più giorni insieme, o una decisione fuori dal piano."
        )
    return [
        rationale(testo, fonti=[f"kb/persone/{slug}.md"]),
        card,
    ]


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
    motivo: str = "",
    generata: bool | None = None,
) -> dict[str, Any]:
    """`motivo` dice *perché* manca la prosa (P-D):

    - `""` → il modello ha risposto, il testo è generato;
    - `"non-configurato"` → nessun backend: risposta di solo calcolo;
    - `"schema"` → ha risposto fuori schema: prosa scartata, fatti tenuti;
    - `"giu"` → c'era un backend e non risponde. Questo è un guasto.

    `generata` di norma segue il motivo, ma si può dire di no: una frase
    scritta nel codice (il saluto del gateway) non è una proposta del modello,
    e marcarla come tale svuota il segno per quelle che lo sono (P-I).
    """
    chip_ok, _ = catalogo.filtra_chip(chip or [])
    widget_ok, scartati = catalogo.filtra_widget(widget or [])
    return {
        "tipo": "copilot-turn",
        "testo": testo,
        "chip": chip_ok,
        "widget": widget_ok,
        "scartati": scartati,
        "generata": (not motivo) if generata is None else generata,
        "degradato": bool(motivo),
        "motivo": motivo,
    }


def week_grid(piano: Piano, bozza: Bozza | None = None) -> dict[str, Any]:
    """Il tabellone. **Non** nel landing, **non** scelto dal Copilot (`02` §4.2).

    Con una bozza in mano la griglia è quella della bozza, e le celle che
    cambiano portano un segno: allineate per **giorno della settimana** contro
    il riferimento pubblicato, che è la domanda che si fa un manager guardando
    il foglio («il lunedì di prima cosa faceva?»).
    """
    riferimento = kb_turni.piano_di_riferimento(bozza.settimana) if bozza else None
    scarto = (bozza.settimana - riferimento.settimana) if (bozza and riferimento) else None

    righe = []
    for slug in piano.persone():
        persona = kb_persone.leggi(slug)
        celle = []
        for g in piano.giorni:
            turno = piano.turno(slug, g)
            testo = turno.etichetta() if turno else ""
            cambiata = False
            if riferimento is not None and scarto is not None:
                prima = riferimento.turno(slug, g - scarto)
                cambiata = (prima.etichetta() if prima else "") != testo
            celle.append({"data": g.isoformat(), "testo": testo, "overlay": cambiata})
        righe.append(
            {
                "persona": slug,
                "nome": persona.nome if persona else slug,
                "contratto": persona.contratto_ore_settimanali if persona else None,
                "celle": celle,
                "ore": ore_turni(piano.della_persona(slug)),
            }
        )
    return {
        "tipo": "week-grid",
        "bozza": bool(bozza),
        "settimana": piano.settimana.isoformat(),
        "giorni": [
            {"data": g.isoformat(), "etichetta": f"{['lun','mar','mer','gio','ven','sab','dom'][g.weekday()]} {g.day}"}
            for g in piano.giorni
        ],
        "righe": righe,
        "note": {d.isoformat(): n for d, n in piano.note_settimana.items()},
    }
