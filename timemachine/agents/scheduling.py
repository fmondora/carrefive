"""Scheduling — 1–3 bozze di settimana (`01` §4.3).

Divisione del lavoro, esplicita:

- **Vincoli hard** (mansione posseduta, riposo settimanale, disponibilità):
  solver deterministico. Non li tocca un modello.
- **Assegnazione morbida** (chi fra i candidati copre il buco): l'LLM può
  ordinare i candidati; l'output passa dal grounding gate e, se il backend è
  giù, si usa l'ordine deterministico (meno ore prima).
- **Straordinario oltre il tetto**: *non* si aggiusta da soli. Spostare il
  turno di una persona su un'altra è una decisione, non una pulizia: resta al
  manager (`sposta-turno`), e la rationale lo dice (UC-03).

Le preferenze si onorano se copertura e CCNL lo permettono; se no, la
rationale spiega perché no (E3).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from ..domain.bozza import Bozza, Variante, celle_da_piano
from ..domain.grounding import Gate
from ..domain.modelli import Piano, Turno
from ..domain.ore import ore_in_fascia, ore_settimana
from ..domain.proposta import Proposta, Scarto
from ..kb import persone as kb_persone
from ..kb import turni as kb_turni
from ..orchestrator.contesto import Contesto
from ..security import privacy
from .base import registra
from .forecast import FASCE, Fabbisogno, previsione, reparto_di
from .llm import LLMGiu, SchemaNonRispettato, llm

#: quante persone si propongono per un buco. Stesso tetto della preview di
#: `pubblica`: oltre, una lista smette di essere una scelta.
MAX_CANDIDATI = 8

SCHEMA_ORDINE = {
    "type": "object",
    "required": ["ordine"],
    "properties": {
        "ordine": {"type": "array", "items": {"type": "string"}},
        "perche": {"type": "string"},
    },
}


@dataclass(slots=True)
class Gap:
    data: dt.date
    fascia: str
    reparto: str
    mancanti: float
    coperto_da: list[str] = field(default_factory=list)

    def come_dict(self) -> dict:
        return {
            "data": self.data.isoformat(),
            "fascia": self.fascia,
            "reparto": self.reparto,
            "teste_mancanti": round(self.mancanti, 1),
            "coperto_da": self.coperto_da,
        }


def _fascia(nome: str) -> tuple[dt.time, dt.time]:
    for n, dalle, alle in FASCE:
        if n == nome:
            return dalle, alle
    return dt.time(0), dt.time(23, 59)


def _template(settimana: dt.date, storia: list[Piano]) -> Piano:
    """La settimana precedente come punto di partenza. È ciò che il negozio fa
    già: si parte da lì e si corregge (principio 11, addizionalità)."""
    piano = Piano(settimana=settimana, stato="bozza")
    if not storia:
        return piano
    base = storia[-1]
    delta = settimana - base.settimana
    for slug in base.persone():
        for turno in base.della_persona(slug):
            piano.imposta(
                Turno(
                    persona=slug,
                    data=turno.data + delta,
                    spezzoni=turno.spezzoni,
                    badge=turno.badge,
                    note=turno.note,
                    grezzo=turno.grezzo,
                )
            )
    return piano


def _teste_in_fascia(piano: Piano, data: dt.date, fascia: str, reparto: str, schede: dict) -> list[str]:
    dalle, alle = _fascia(fascia)
    fuori = []
    for slug in piano.persone():
        turno = piano.turno(slug, data)
        if turno is None or not turno.lavorato:
            continue
        persona = schede.get(slug)
        rep = reparto_di(list(turno.mansioni) or (persona.nomi_mansioni() if persona else []))
        if rep == reparto and ore_in_fascia(turno, dalle, alle) > 0.5:
            fuori.append(slug)
    return fuori


def _candidati(piano: Piano, data: dt.date, reparto: str, schede: dict) -> list[str]:
    """Chi ha la mansione ed è libero quel giorno.

    **Riposo e ferie non sono disponibilità.** Un buco di copertura non è un
    buon motivo per prendersi il riposo di qualcuno: quella è una decisione del
    manager, non una scelta del solver.
    """
    fuori = []
    for slug, persona in schede.items():
        if not persona.ha_mansione(reparto):
            continue
        turno = piano.turno(slug, data)
        if turno is not None and (turno.lavorato or turno.ferie or turno.riposo or turno.badge):
            continue
        fuori.append(slug)
    return fuori


def _movibili(
    piano: Piano, data: dt.date, fascia: str, reparto: str, schede: dict
) -> list[str]:
    """Chi quel giorno **è già in turno**, ma in un'altra fascia o reparto.

    Serve perché dopo `genera-bozza` i liberi sui buchi rimasti sono vuoti per
    costruzione: lo Scheduling ha già assegnato chi poteva, e quel che resta è
    per definizione senza nessuno libero. Senza questo secondo giro il gesto
    sarebbe morto sulla demo (Book 08, riga «Layer 2 movibili»).

    Non è una proposta di spostamento: è un elenco di persone su cui il manager
    *può* decidere. Riposi e ferie restano fuori anche qui.
    """
    dalle, alle = _fascia(fascia)
    fuori = []
    for slug, persona in schede.items():
        if not persona.ha_mansione(reparto):
            continue
        turno = piano.turno(slug, data)
        if turno is None or not turno.lavorato:
            continue  # libero → è già layer 1; R/F/badge → non si toccano
        gia_li = ore_in_fascia(turno, dalle, alle) > 0.5 and reparto in (
            reparto_di(list(turno.mansioni) or persona.nomi_mansioni()),
        )
        if not gia_li:
            fuori.append(slug)
    return fuori


def candidati_per_gap(
    piano: Piano,
    data: dt.date,
    fascia: str,
    reparto: str,
    schede: dict,
    tetto: int = MAX_CANDIDATI,
) -> list[str]:
    """Chi può coprire questo buco. **Zero LLM, zero rete** (Book 05).

    Due strati, il secondo solo se il primo è vuoto: prima i liberi, poi chi è
    già in turno altrove quel giorno. Ordine deterministico (meno carico
    prima), tetto corto: otto card sono già una lista, sedici sono rumore.
    """
    liberi = _candidati(piano, data, reparto, schede)
    scelti = liberi or _movibili(piano, data, fascia, reparto, schede)
    return _ordine_deterministico(piano, scelti, schede)[:tetto]


def _garantisci_riposo(piano: Piano) -> list[str]:
    """Nessuno lavora 7 giorni su 7: il più leggero diventa riposo."""
    note: list[str] = []
    for slug in piano.persone():
        lavorati = [t for t in piano.della_persona(slug) if t.lavorato]
        if len(lavorati) < 7:
            continue
        leggero = min(lavorati, key=lambda t: t.ore)
        piano.imposta(Turno(persona=slug, data=leggero.data, badge="R"))
        note.append(f"{slug}: aggiunto riposo il {leggero.giorno} (settimana senza riposi).")
    return note


def _ordine_deterministico(piano: Piano, candidati: list[str], schede: dict) -> list[str]:
    def chiave(slug: str) -> tuple[float, str]:
        ore = ore_settimana(piano, slug)
        contratto = schede[slug].contratto_ore_settimanali or 40
        return (ore / contratto, slug)

    return sorted(candidati, key=chiave)


class Scheduling:
    id = "scheduling"
    usa_llm = True
    modello = "solver+llm"
    versione_prompt = "scheduling-2"

    # --- assegnazione morbida ------------------------------------------------

    def _ordina(self, piano: Piano, candidati: list[str], schede: dict, motivo: str) -> tuple[list[str], str]:
        deterministico = _ordine_deterministico(piano, candidati, schede)
        if len(candidati) < 2:
            return deterministico, "candidato unico"
        try:
            dati, _ = llm().genera_json(
                prompt=(
                    f"Buco da coprire: {motivo}. Candidati (già filtrati per mansione e "
                    f"disponibilità): {', '.join(deterministico)}. "
                    "Ordinali dal più adatto al meno adatto. Usa SOLO questi slug."
                ),
                schema=SCHEMA_ORDINE,
                sistema="scheduling: ordini candidati. Rispondi solo JSON.",
            )
        except (LLMGiu, SchemaNonRispettato):
            return deterministico, "ordine deterministico (meno ore prima)"
        proposti = [s for s in dati.get("ordine", []) if s in candidati]
        coda = [s for s in deterministico if s not in proposti]
        return proposti + coda, str(dati.get("perche") or "ordine proposto dal modello")

    # --- costruzione della bozza --------------------------------------------

    def costruisci(
        self,
        contesto: Contesto,
        fabbisogni: list[Fabbisogno] | None = None,
        variante: int = 0,
    ) -> tuple[Piano, list[Gap], list[str], list[Scarto]]:
        schede = kb_persone.per_slug()
        gate = Gate(schede=schede)
        piano = _template(contesto.settimana, contesto.piani)
        fabbisogni = fabbisogni if fabbisogni is not None else previsione(
            contesto.settimana, contesto.piani, schede
        )
        note: list[str] = []
        scarti: list[Scarto] = []

        # 1. preferenze (vincolo morbido, mai la storia)
        for slug, persona in schede.items():
            vincoli = privacy.vincoli_operativi(persona.preferenze)
            if not vincoli:
                continue
            for giorno in piano.giorni:
                turno = piano.turno(slug, giorno)
                if turno is None or not turno.lavorato:
                    continue
                for vincolo in vincoli:
                    if not any(privacy.viola(vincolo, turno.giorno, s.inizio.hour) for s in turno.spezzoni):
                        continue
                    reparto = reparto_di(list(turno.mansioni) or persona.nomi_mansioni())
                    sostituti = [
                        c for c in _candidati(piano, giorno, reparto, schede) if c != slug
                    ]
                    if sostituti:
                        scelto = _ordine_deterministico(piano, sostituti, schede)[0]
                        piano.imposta(
                            Turno(
                                persona=scelto,
                                data=giorno,
                                spezzoni=turno.spezzoni,
                                note=turno.note,
                            )
                        )
                        piano.imposta(Turno(persona=slug, data=giorno, badge="R"))
                        note.append(
                            f"{slug}: onorato «{vincolo}» il {turno.giorno}; copre {scelto}."
                        )
                    else:
                        note.append(
                            f"{slug}: «{vincolo}» non onorato il {turno.giorno} — "
                            f"nessun altro con mansione «{reparto}» libero quel giorno."
                        )

        # 2. riposo settimanale: se manca, il giorno più leggero diventa R
        note += _garantisci_riposo(piano)

        # 3. copertura dei buchi
        gap: list[Gap] = []
        for f in fabbisogni:
            presenti = _teste_in_fascia(piano, f.data, f.fascia, f.reparto, schede)
            # teste intere: mezza persona non è un buco, è la media di due settimane
            mancanti = round(f.teste) - len(presenti)
            if mancanti < 1:
                continue
            candidati = _candidati(piano, f.data, f.reparto, schede)
            motivo = f"{f.data.isoformat()} {f.fascia} reparto {f.reparto}"
            ordinati, perche = self._ordina(piano, candidati, schede, motivo)
            ordinati = ordinati[variante:] + ordinati[:variante]
            coperto: list[str] = []
            for slug in ordinati[:mancanti]:
                cella, scarto = gate.valida_cella(
                    {
                        "persona": slug,
                        "data": f.data.isoformat(),
                        "mansioni": [f.reparto],
                    }
                )
                if cella is None:
                    if scarto:
                        scarti.append(scarto)
                    continue
                dalle, alle = _fascia(f.fascia)
                from ..domain.modelli import Spezzone

                piano.imposta(
                    Turno(
                        persona=slug,
                        data=f.data,
                        spezzoni=(Spezzone(inizio=dalle, fine=alle, mansioni=(f.reparto,)),),
                    )
                )
                coperto.append(slug)
                note.append(f"{f.data.isoformat()} {f.fascia}: {slug} copre {f.reparto} ({perche}).")
            residuo = mancanti - len(coperto)
            if residuo >= 1:
                gap.append(
                    Gap(
                        data=f.data,
                        fascia=f.fascia,
                        reparto=f.reparto,
                        mancanti=residuo,
                        coperto_da=presenti + coperto,
                    )
                )

        # 3bis. coprire un buco non può togliere il riposo settimanale a nessuno
        note += _garantisci_riposo(piano)

        # 4. straordinario: si segnala, non si aggiusta in silenzio
        for slug in piano.persone():
            persona = schede.get(slug)
            if not persona or not persona.contratto_ore_settimanali:
                continue
            ore = ore_settimana(piano, slug)
            if ore > 48:
                note.append(
                    f"{slug}: {ore:g}h, oltre il tetto settimanale. Non l'ho ridotto da solo: "
                    "serve una tua decisione (sposta-turno)."
                )
            elif ore > persona.contratto_ore_settimanali:
                note.append(
                    f"{slug}: {ore:g}h su contratto {persona.contratto_ore_settimanali:g}h."
                )

        # 5. ferie proposte vs residuo (`04` §4.5): vincolo morbido, non blocco
        note += self._nota_ferie(piano, schede)

        return piano, gap, note, scarti

    def _nota_ferie(self, piano: Piano, schede: dict) -> list[str]:
        from .. import saldi as porta_saldi

        fuori: list[str] = []
        for slug in piano.persone():
            giorni_f = [t for t in piano.della_persona(slug) if t.ferie]
            if not giorni_f:
                continue
            persona = schede.get(slug)
            ore_giorno = (persona.ore_giorno if persona else None) or (
                (persona.contratto_ore_settimanali or 40) / 5 if persona else 8
            )
            richieste = len(giorni_f) * ore_giorno
            saldi = [s for s in porta_saldi.di(slug) if s.tipo == "ferie"]
            if not saldi:
                continue
            residuo = saldi[0].residuo
            if richieste > residuo:
                fuori.append(
                    f"{slug}: {len(giorni_f)} giorni di ferie ≈ {richieste:g}h, "
                    f"residuo {residuo:g}h. Proposta possibile, ma il montante non copre."
                )
        return fuori

    # --- interfaccia agente --------------------------------------------------

    def nel_ciclo(self, contesto: Contesto, **fase) -> Proposta:
        fabbisogni = fase.get("fabbisogni")
        n_varianti = int(fase.get("varianti", 1))
        varianti: list[Variante] = []
        tutte_note: list[str] = []
        scarti: list[Scarto] = []
        gap: list[Gap] = []
        for i in range(max(1, n_varianti)):
            piano, gap_i, note, scarti_i = self.costruisci(contesto, fabbisogni, variante=i)
            varianti.append(
                Variante(
                    nome=f"variante-{i + 1}",
                    piano=piano,
                    rationale=" ".join(note[:12]),
                    confidenza=0.7 if contesto.piani else 0.3,
                )
            )
            if i == 0:
                gap, tutte_note, scarti = gap_i, note, scarti_i

        proposta = Proposta(
            agente=self.id,
            tipo="bozza-turni",
            payload={
                "settimana": contesto.settimana.isoformat(),
                "celle": celle_da_piano(varianti[0].piano),
                "gap": [g.come_dict() for g in gap],
                "note": tutte_note,
            },
            rationale=" ".join(tutte_note[:12])
            or "Bozza costruita sulla settimana precedente; nessuna correzione necessaria.",
            fonti=contesto.fonti[:40],
            confidenza=varianti[0].confidenza,
            varianti=[
                {
                    "nome": v.nome,
                    "celle": celle_da_piano(v.piano),
                    "rationale": v.rationale,
                }
                for v in varianti[1:]
            ],
            scarti=scarti,
        )
        proposta.payload["_varianti"] = varianti  # oggetti vivi per l'orchestratore
        return proposta

    def consulta(self, domanda: str, contesto: Contesto, **extra) -> Proposta:
        """«chi copre giovedì pomeriggio senza straordinario?» — zero side-effect."""
        schede = kb_persone.per_slug()
        piano = kb_turni.leggi(contesto.settimana) or _template(contesto.settimana, contesto.piani)
        giorno = _giorno_da_testo(domanda, contesto.settimana)
        fascia = _fascia_da_testo(domanda)
        mansione = _mansione_da_testo(domanda, schede)

        candidati: list[str] = []
        fonti: list[str] = []
        for slug, persona in schede.items():
            if mansione and not persona.ha_mansione(mansione):
                continue
            turno = piano.turno(slug, giorno) if giorno else None
            if turno is not None and (turno.lavorato or turno.ferie):
                continue
            ore = ore_settimana(piano, slug)
            contratto = persona.contratto_ore_settimanali or 40
            if "straordinario" in domanda.lower() and ore >= contratto:
                continue
            candidati.append(slug)
            fonti.append(f"kb/persone/{slug}.md")

        ordinati = _ordine_deterministico(piano, candidati, schede)
        rationale = (
            f"{len(ordinati)} persone disponibili"
            + (f" con mansione «{mansione}»" if mansione else "")
            + (f" il {giorno.isoformat()}" if giorno else "")
            + (f" in fascia {fascia}" if fascia else "")
            + ". Nessuna assegnazione fatta: per assegnare serve `sposta-turno` o un nuovo ciclo."
        )
        return Proposta(
            agente=self.id,
            tipo="risposta",
            payload={
                "domanda": domanda,
                "persone": ordinati,
                "giorno": giorno.isoformat() if giorno else None,
                "fascia": fascia,
                "mansione": mansione,
            },
            rationale=rationale,
            fonti=fonti[:10]
            + [f"kb/turni/{p.settimana.isoformat()}.md" for p in contesto.piani[-2:]],
        )


_GIORNI_NL = {
    "lunedì": 0, "lunedi": 0, "martedì": 1, "martedi": 1, "mercoledì": 2, "mercoledi": 2,
    "giovedì": 3, "giovedi": 3, "venerdì": 4, "venerdi": 4, "sabato": 5, "domenica": 6,
}


def _giorno_da_testo(testo: str, settimana: dt.date) -> dt.date | None:
    basso = (testo or "").lower()
    for parola, i in _GIORNI_NL.items():
        if parola in basso:
            return settimana + dt.timedelta(days=i)
    return None


def _fascia_da_testo(testo: str) -> str:
    basso = (testo or "").lower()
    if "mattin" in basso:
        return "mattina"
    if "pomeriggio" in basso or "pome" in basso:
        return "pomeriggio"
    if "sera" in basso or "chiusura" in basso:
        return "pomeriggio"
    return ""


def _mansione_da_testo(testo: str, schede: dict) -> str:
    basso = (testo or "").lower()
    note = {m for p in schede.values() for m in p.nomi_mansioni()}
    for m in sorted(note, key=len, reverse=True):
        if m in basso:
            return m
    return ""


AGENTE = registra(Scheduling())


def bozza_da_proposta(proposta: Proposta) -> Bozza:
    """Dalla Proposta (dominio) alla Bozza (ciò che il ciclo tiene in mano)."""
    from ..domain.bozza import piano_da_celle

    settimana = dt.date.fromisoformat(proposta.payload["settimana"])
    varianti = proposta.payload.get("_varianti")
    if not varianti:
        varianti = [
            Variante(
                nome="variante-1",
                piano=piano_da_celle(proposta.payload["celle"], settimana),
                rationale=proposta.rationale,
                confidenza=proposta.confidenza,
            )
        ]
        for v in proposta.varianti:
            varianti.append(
                Variante(
                    nome=str(v.get("nome", "variante")),
                    piano=piano_da_celle(v["celle"], settimana),
                    rationale=str(v.get("rationale", "")),
                )
            )
    return Bozza(
        settimana=settimana,
        varianti=list(varianti),
        proposta_id=proposta.id,
        gap=proposta.payload.get("gap", []),
        fonti=proposta.fonti,
    )
