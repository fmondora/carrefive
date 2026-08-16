"""Compliance — **zero LLM** (`01` §4.3). Può bloccare, non può riscrivere.

Implementa i check che sappiamo oggi (`01` §7 aperto): riposo settimanale,
cap ore della scheda, riposo giornaliero, giorni consecutivi, minori, mansione
posseduta. Il motore CCNL Commercio/DMO completo è spec propria, prima del
go-live sul pubblicabile.

Se blocca, `pubblicabile: false` e l'orchestratore non offre `pubblica` (E4).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from ..domain.modelli import Piano
from ..domain.ore import giorni_consecutivi_lavorati, ore_settimana, riposo_fra_turni
from ..domain.proposta import Proposta
from ..kb import persone as kb_persone
from ..orchestrator.contesto import Contesto
from .base import registra

#: tetto settimanale oltre il quale non si pubblica (direttiva 2003/88/CE, 48h
#: medie). Sotto il tetto ma sopra contratto = segnalazione, non blocco.
MAX_ORE_SETTIMANA = 48.0
MIN_RIPOSO_GIORNALIERO = 11.0
#: sotto questo stacco si blocca anche col turno frazionato
MIN_RIPOSO_ASSOLUTO = 9.0
MAX_GIORNI_CONSECUTIVI = 6
MAX_ORE_GIORNO_MINORE = 8.0
ORA_MASSIMA_MINORE = 22


@dataclass(slots=True)
class Violazione:
    persona: str
    regola: str
    dettaglio: str
    data: str = ""
    gravita: str = "blocco"  # blocco | segnalazione

    def come_dict(self) -> dict:
        return {
            "persona": self.persona,
            "regola": self.regola,
            "dettaglio": self.dettaglio,
            "data": self.data,
            "gravita": self.gravita,
        }


def verifica_piano(piano: Piano, schede: dict | None = None) -> list[Violazione]:
    schede = schede if schede is not None else kb_persone.per_slug()
    fuori: list[Violazione] = []

    for slug in piano.persone():
        persona = schede.get(slug)
        turni = piano.della_persona(slug)
        lavorati = [t for t in turni if t.lavorato]

        # 1. riposo settimanale
        if lavorati and len(lavorati) >= 7:
            fuori.append(
                Violazione(
                    persona=slug,
                    regola="riposo-settimanale",
                    dettaglio="nessun giorno di riposo nella settimana",
                )
            )

        # 2. cap ore
        ore = ore_settimana(piano, slug)
        contratto = persona.contratto_ore_settimanali if persona else None
        if ore > MAX_ORE_SETTIMANA:
            fuori.append(
                Violazione(
                    persona=slug,
                    regola="ore-massime",
                    dettaglio=f"{ore:g}h nella settimana, tetto {MAX_ORE_SETTIMANA:g}h",
                )
            )
        elif contratto and ore > contratto:
            fuori.append(
                Violazione(
                    persona=slug,
                    regola="oltre-contratto",
                    dettaglio=f"{ore:g}h su contratto {contratto:g}h (straordinario)",
                    gravita="segnalazione",
                )
            )

        # 3. riposo giornaliero fra turni.
        #    D.Lgs 66/2003 art. 7 prevede deroga per il **lavoro frazionato**
        #    nella giornata: sui turni spezzati sotto le 11h si segnala, non si
        #    blocca — sotto il minimo assoluto si blocca comunque.
        for prima, dopo in zip(turni, turni[1:]):
            stacco = riposo_fra_turni(prima, dopo)
            if stacco is None or stacco >= MIN_RIPOSO_GIORNALIERO:
                continue
            frazionato = len(prima.spezzoni) > 1 or len(dopo.spezzoni) > 1
            grave = stacco < MIN_RIPOSO_ASSOLUTO or not frazionato
            fuori.append(
                Violazione(
                    persona=slug,
                    regola="riposo-giornaliero",
                    dettaglio=(
                        f"{stacco:g}h fra {prima.giorno} e {dopo.giorno}, minimo "
                        f"{MIN_RIPOSO_GIORNALIERO:g}h"
                        + ("" if grave else " (turno frazionato: deroga art. 7, da verificare)")
                    ),
                    data=dopo.data.isoformat(),
                    gravita="blocco" if grave else "segnalazione",
                )
            )

        # 4. giorni consecutivi
        consecutivi = giorni_consecutivi_lavorati(piano, slug)
        if consecutivi > MAX_GIORNI_CONSECUTIVI:
            fuori.append(
                Violazione(
                    persona=slug,
                    regola="giorni-consecutivi",
                    dettaglio=f"{consecutivi} giorni consecutivi, massimo {MAX_GIORNI_CONSECUTIVI}",
                )
            )

        # 5. mansione posseduta (grounding hard: non è estetica, è assegnazione)
        if persona is not None:
            for t in lavorati:
                for m in t.mansioni:
                    if not persona.ha_mansione(m):
                        fuori.append(
                            Violazione(
                                persona=slug,
                                regola="mansione-non-in-scheda",
                                dettaglio=f"«{m}» non è fra le mansioni di {slug}",
                                data=t.data.isoformat(),
                            )
                        )

        # 6. minori
        if persona is not None and persona.minore:
            for t in lavorati:
                if t.ore > MAX_ORE_GIORNO_MINORE:
                    fuori.append(
                        Violazione(
                            persona=slug,
                            regola="minori-ore-giorno",
                            dettaglio=f"{t.ore:g}h in un giorno, massimo {MAX_ORE_GIORNO_MINORE:g}h",
                            data=t.data.isoformat(),
                        )
                    )
                if any(s.fine.hour >= ORA_MASSIMA_MINORE or s.fine.hour == 0 for s in t.spezzoni):
                    fuori.append(
                        Violazione(
                            persona=slug,
                            regola="minori-orario-serale",
                            dettaglio=f"turno oltre le {ORA_MASSIMA_MINORE}",
                            data=t.data.isoformat(),
                        )
                    )

    return fuori


def pubblicabile(violazioni: list[Violazione]) -> bool:
    return not any(v.gravita == "blocco" for v in violazioni)


class Compliance:
    """Non ha LLM e non ne vuole. `modello: codice`."""

    id = "compliance"
    usa_llm = False
    modello = "codice"
    versione_prompt = "-"

    def verifica(self, piano: Piano, contesto: Contesto | None = None) -> Proposta:
        violazioni = verifica_piano(piano)
        blocchi = [v for v in violazioni if v.gravita == "blocco"]
        segnalazioni = [v for v in violazioni if v.gravita != "blocco"]
        ok = not blocchi
        rationale = (
            "Nessuna violazione bloccante sul piano proposto."
            if ok
            else "Piano non pubblicabile: "
            + "; ".join(f"{v.persona} — {v.dettaglio}" for v in blocchi)
        )
        return Proposta(
            agente=self.id,
            tipo="blocco",
            payload={
                "settimana": piano.settimana.isoformat(),
                "pubblicabile": ok,
                "violazioni": [v.come_dict() for v in blocchi],
                "segnalazioni": [v.come_dict() for v in segnalazioni],
            },
            rationale=rationale,
            fonti=[f"kb/persone/{s}.md" for s in sorted({v.persona for v in violazioni})],
        )

    def nel_ciclo(self, contesto: Contesto, **fase) -> Proposta:
        piano: Piano | None = fase.get("piano")
        if piano is None:
            raise ValueError("compliance nel ciclo richiede un piano da verificare")
        return self.verifica(piano, contesto)

    def consulta(self, domanda: str, contesto: Contesto, **extra) -> Proposta:
        """«questo cambio rompe un riposo?» — risposta da codice, non da modello."""
        piano: Piano | None = extra.get("piano")
        if piano is None:
            from ..kb import turni as kb_turni

            piano = kb_turni.leggi(contesto.settimana) or Piano(settimana=contesto.settimana)
        p = self.verifica(piano, contesto)
        p.payload["domanda"] = domanda
        return p


AGENTE = registra(Compliance())


def oggi() -> dt.date:
    return dt.date.today()
