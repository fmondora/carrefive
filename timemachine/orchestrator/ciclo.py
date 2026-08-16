"""Orchestratore — macchina a stati del ciclo settimana (`01` §4.4).

    idle → carica_contesto → forecast → scheduling → compliance → attesa_umano
         ├─ (modifica) → scheduling → compliance → attesa_umano
         ├─ (rifiuta)  → idle  + secondo-pv impara il rifiuto
         └─ (approva)  → pubblica → monitora → (consuntivo) → anomaly → secondo-pv → idle

Regole dure:

1. Non si salta `compliance` prima di `attesa_umano` né prima di `pubblica`.
2. `pubblica` è un atto **umano**. L'orchestratore non pubblica da solo.
3. Se l'AI è giù non nasce una bozza nuova: il pubblicato resta (degrado onesto).
4. I comandi arrivano da chip o dal Copilot. **Qui non si interpreta linguaggio.**
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Literal

from ..agents import base as agenti
from ..agents.compliance import Compliance
from ..agents.llm import LLMGiu
from ..agents.scheduling import bozza_da_proposta
from ..domain.bozza import Bozza
from ..domain.modelli import Piano, Turno
from ..domain.proposta import Decisione, Proposta
from ..kb import turni as kb_turni
from ..kb.celle import parse_cella
from ..security import audit
from ..security.authz import Attore, esigi_manager
from . import contesto as ctx
from .jobs import CODA, Job

Stato = Literal[
    "idle", "carica_contesto", "forecast", "scheduling", "compliance", "attesa_umano",
    "pubblica", "monitora",
]

CHIP_PER_STATO: dict[str, tuple[str, ...]] = {
    "idle": ("genera-bozza", "consulta", "apri-tabellone"),
    # `sposta-turno` non sta qui: una chip nuda non porta con sé persona,
    # giorno e fascia, e senza bersaglio l'atto non esiste. Vive sulle card
    # (candidato di un gap, `diff-edit`), dove i campi ci sono (Book 05).
    "attesa_umano": (
        "accetta-bozza",
        "scegli-variante",
        "rifiuta-bozza",
        "consulta",
        "apri-tabellone",
    ),
    "monitora": ("consulta", "apri-tabellone"),
}


class CicloBloccato(Exception):
    """Una transizione non ammessa dalla macchina a stati."""


@dataclass(slots=True)
class Ciclo:
    settimana: dt.date
    punto_vendita: str = "Le Rocce — Poggiridenti"
    stato: Stato = "idle"
    bozza: Bozza | None = None
    proposte: list[Proposta] = field(default_factory=list)
    decisioni: list[Decisione] = field(default_factory=list)
    job_corrente: Job | None = None
    errore: str = ""
    varianti_default: int = 1

    # --- lettura -------------------------------------------------------------

    @property
    def pubblicabile(self) -> bool:
        return bool(self.bozza and self.bozza.pubblicabile and self.bozza.accettata)

    def chip(self) -> list[str]:
        base = list(CHIP_PER_STATO.get(self.stato, ("consulta",)))
        if self.stato == "attesa_umano" and self.bozza and self.bozza.accettata:
            base = [c for c in base if c != "accetta-bozza"]
            if self.bozza.pubblicabile:
                base.insert(0, "pubblica")
        return base

    def stato_visibile(self) -> dict[str, Any]:
        """Ciò che il guscio mostra. Verità dal job, non dal client (`02` §4.3)."""
        job = self.job_corrente
        return {
            "stato": self.stato,
            "settimana": self.settimana.isoformat(),
            "job": job.come_dict() if job else None,
            "errore": self.errore,
            "pubblicabile": bool(self.bozza and self.bozza.pubblicabile),
            "accettata": bool(self.bozza and self.bozza.accettata),
            "chip": self.chip(),
        }

    def piano_pubblicato(self) -> Piano | None:
        return kb_turni.leggi(self.settimana) or kb_turni.ultimo_pubblicato(self.settimana)

    # --- transizioni ---------------------------------------------------------

    def genera_bozza(self, attore: Attore, varianti: int | None = None) -> Job:
        """Chip `genera-bozza`. Non naviga via: il lavoro va in coda (U9)."""
        esigi_manager(attore, "ciclo/genera-bozza")
        if self.stato not in ("idle", "attesa_umano", "monitora"):
            raise CicloBloccato(f"non posso generare una bozza da {self.stato}")
        self.errore = ""
        n = varianti if varianti is not None else self.varianti_default

        def lavoro() -> dict[str, Any]:
            self.stato = "carica_contesto"
            contesto = ctx.carica(self.settimana)
            self.stato = "forecast"
            previsione = agenti.agente("forecast").nel_ciclo(contesto)
            self._registra(previsione, "ciclo")
            fabbisogni = _fabbisogni_da_proposta(previsione)
            self.stato = "scheduling"
            proposta = agenti.agente("scheduling").nel_ciclo(
                contesto, fabbisogni=fabbisogni, varianti=n
            )
            self._registra(proposta, "ciclo")
            self.bozza = bozza_da_proposta(proposta)
            self._compliance()  # regola 1: non si salta
            self.stato = "attesa_umano"
            return {"proposta": proposta.id, "pubblicabile": self.bozza.pubblicabile}

        self.job_corrente = CODA.accoda(
            "genera-bozza", self._protetto(lavoro), chiave=f"bozza:{self.settimana}"
        )
        return self.job_corrente

    def _protetto(self, lavoro):
        def wrapper():
            try:
                return lavoro()
            except LLMGiu as e:
                # regola 3: nessuna bozza nuova, nessun 200 finto
                self.stato = "idle"
                self.bozza = None
                self.errore = f"Copilota/agenti non disponibili: {e}"
                raise
            except Exception:
                self.stato = "idle"
                raise

        return wrapper

    def _compliance(self) -> Proposta:
        assert self.bozza is not None
        self.stato = "compliance"
        proposta = Compliance().verifica(self.bozza.piano)
        self._registra(proposta, "ciclo")
        self.bozza.pubblicabile = bool(proposta.payload["pubblicabile"])
        self.bozza.violazioni = proposta.payload["violazioni"]
        self.bozza.segnalazioni = proposta.payload["segnalazioni"]
        return proposta

    def sposta_turno(
        self, attore: Attore, persona: str, data: dt.date, fascia: str
    ) -> Proposta:
        """Modifica sulla persona → di nuovo scheduling/compliance → attesa_umano."""
        esigi_manager(attore, "ciclo/sposta-turno")
        if self.stato != "attesa_umano" or self.bozza is None:
            raise CicloBloccato("nessuna bozza in attesa da modificare")
        spezzoni, badge, note = parse_cella(fascia)
        self.bozza.piano.imposta(
            Turno(persona=persona, data=data, spezzoni=spezzoni, badge=badge, note=note, grezzo=fascia)
        )
        self.bozza.accettata = False
        proposta = self._compliance()
        self.stato = "attesa_umano"
        audit.decisione(
            proposta_id=self.bozza.proposta_id,
            esito="modificata",
            da=attore.slug,
            diff=[{"persona": persona, "data": data.isoformat(), "dopo": fascia}],
        )
        return proposta

    def scegli_variante(self, attore: Attore, indice: int) -> None:
        esigi_manager(attore, "ciclo/scegli-variante")
        if self.bozza is None or not 0 <= indice < len(self.bozza.varianti):
            raise CicloBloccato("variante inesistente")
        self.bozza.scelta = indice
        self.bozza.accettata = False
        self._compliance()
        self.stato = "attesa_umano"

    def accetta(self, attore: Attore) -> None:
        """Chip `accetta-bozza`. Non pubblica: prepara la seconda conferma."""
        esigi_manager(attore, "ciclo/accetta-bozza")
        if self.stato != "attesa_umano" or self.bozza is None:
            raise CicloBloccato("niente da accettare")
        self.bozza.accettata = True
        audit.decisione(self.bozza.proposta_id, "accettata", attore.slug, diff=self._diff())

    def rifiuta(self, attore: Attore, motivo: str = "") -> Proposta | None:
        esigi_manager(attore, "ciclo/rifiuta-bozza")
        if self.bozza is None:
            raise CicloBloccato("niente da rifiutare")
        decisione = Decisione(
            proposta_id=self.bozza.proposta_id, esito="rifiutata", da=attore.slug, motivo=motivo
        )
        self.decisioni.append(decisione)
        audit.decisione(decisione.proposta_id, "rifiutata", attore.slug, motivo)
        memoria = self._impara(decisione)
        self.bozza = None
        self.stato = "idle"
        return memoria

    def pubblica(self, attore: Attore) -> Piano:
        """Atto umano. Compliance ha già detto la sua; qui si ricontrolla."""
        esigi_manager(attore, "ciclo/pubblica")
        if self.bozza is None or not self.bozza.accettata:
            raise CicloBloccato("si pubblica solo una bozza accettata")
        self._compliance()  # regola 1: nemmeno prima di pubblica si salta
        if not self.bozza.pubblicabile:
            self.stato = "attesa_umano"
            raise CicloBloccato("piano non pubblicabile: Compliance ha bloccato")

        self.stato = "pubblica"
        piano = self.bozza.piano
        piano.stato = "pubblicato"
        piano.punto_vendita = self.punto_vendita
        piano.fonte = "TIME MACHINE — bozza approvata dal manager"
        diff = self._diff()
        kb_turni.scrivi(piano)

        decisione = Decisione(
            proposta_id=self.bozza.proposta_id, esito="pubblicata", da=attore.slug, diff=diff
        )
        self.decisioni.append(decisione)
        audit.decisione(decisione.proposta_id, "pubblicata", attore.slug, diff=diff)
        self._impara(decisione)

        from ..calendario import sync as sync_calendario

        sync_calendario.dopo_pubblicazione(piano)

        self.stato = "monitora"
        self.bozza = None
        return piano

    def consuntivo_chiuso(self, timbrature: list) -> tuple[Proposta, Proposta | None]:
        """monitora → anomaly → secondo-pv → idle."""
        if self.stato != "monitora":
            raise CicloBloccato("il consuntivo si chiude solo in monitora")
        contesto = ctx.carica(self.settimana)
        segnale = agenti.agente("anomaly").nel_ciclo(contesto, timbrature=timbrature)
        self._registra(segnale, "ciclo")
        self.stato = "idle"
        return segnale, None

    # --- utilità -------------------------------------------------------------

    def _diff(self) -> list[dict[str, Any]]:
        if self.bozza is None:
            return []
        pubblicato = kb_turni.piano_di_riferimento(self.settimana)
        fuori: list[dict[str, Any]] = []
        for slug in self.bozza.persone_toccate(pubblicato):
            for riga in self.bozza.diff(pubblicato, slug):
                fuori.append({"persona": slug, **riga})
        return fuori

    def _impara(self, decisione: Decisione) -> Proposta | None:
        """Il secondo che non impara non ferma la settimana — ma lo si sa."""
        try:
            agente = agenti.agente("secondo-pv")
            proposta = agente.impara(decisione, self.settimana)  # type: ignore[attr-defined]
            self._registra(proposta, "ciclo")
            agente.applica(proposta)  # type: ignore[attr-defined]
            return proposta
        except Exception as e:
            self.errore = f"il secondo del punto vendita non ha imparato: {e}"
            return None

    def _registra(self, proposta: Proposta, esito: str) -> None:
        self.proposte.append(proposta)
        audit.inferenza(
            agente=proposta.agente,
            proposta_id=proposta.id,
            input_hash=audit.hash_input(proposta.payload.get("settimana", "")),
            modello=getattr(agenti.agente(proposta.agente), "modello", "codice"),
            versione_prompt=getattr(agenti.agente(proposta.agente), "versione_prompt", "1"),
            esito=esito,
        )


def _fabbisogni_da_proposta(proposta: Proposta):
    from ..agents.forecast import Fabbisogno

    fuori = []
    for f in proposta.payload.get("fabbisogno", []):
        fuori.append(
            Fabbisogno(
                data=dt.date.fromisoformat(f["data"]),
                fascia=f["fascia"],
                reparto=f["reparto"],
                teste=float(f["teste"]),
            )
        )
    return fuori


# --- registro dei cicli (uno per punto vendita) ------------------------------

_CICLI: dict[str, Ciclo] = {}


def ciclo(settimana: dt.date, punto_vendita: str = "Le Rocce — Poggiridenti") -> Ciclo:
    chiave = f"{punto_vendita}:{settimana.isoformat()}"
    if chiave not in _CICLI:
        _CICLI[chiave] = Ciclo(settimana=settimana, punto_vendita=punto_vendita)
    return _CICLI[chiave]


def azzera() -> None:
    _CICLI.clear()
