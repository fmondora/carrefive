"""Copilot — **l'unico agente che parla con l'umano** (P-L, `01` §4.3).

Compone tipi del catalogo o comanda il ciclo. Non ridisegna il tabellone, non
inventa chip, non scrive: i suoi tool tornano solo Proposte e widget (P-C).

Tool allowlist (`05` §4.4): niente «leggi file arbitrario», niente shell,
niente «manda i saldi di tutti». Ogni tool passa dall'authz del *caller*.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .. import vista
from ..domain.proposta import Proposta
from ..domain.saldi import ETICHETTE
from ..kb import persone as kb_persone
from ..orchestrator.contesto import Contesto
from ..security import allowlist
from ..security.authz import Attore, Negato
from .base import consult, registra
from .llm import LLMGiu, LLMNonConfigurato, SchemaNonRispettato, llm

SCHEMA_TURNO = {
    "type": "object",
    "required": ["testo"],
    "properties": {
        "testo": {"type": "string"},
        "chip": {"type": "array", "items": {"type": "string"}},
    },
}

#: L'enum chiuso del gateway (`01` Loop P1). Il Copilot classifica in questo,
#: poi invoca la pipeline: non è un `if pianoforte`, e soprattutto non ha un
#: `else` che finisce su Scheduling. «ciao!» è `saluto`, non una consulenza di
#: pianificazione svuotata dall'authz.
INTENT: tuple[str, ...] = (
    "preferenza",
    "turni_miei",
    "saldi",
    "copri",
    "comando_ciclo",
    "saluto",
    "sconosciuto",
)

SCHEMA_INTENT = {
    "type": "object",
    "required": ["intent"],
    "properties": {"intent": {"type": "string", "enum": list(INTENT)}},
}

#: Cosa può toccare **parlando** chi non è manager (`01` Loop P1). Il roster
#: pieno (§4.3) è un attrezzo di pianificazione: un dipendente che chiede «chi
#: copre giovedì» non deve ricevere la risposta di Scheduling con dentro i
#: turni dei colleghi, filtrati poi a valle dall'authz.
TOOL_DIPENDENTE: tuple[str, ...] = ("mostra_turni", "mostra_saldi", "prepara_preferenza")

SALUTO = (
    "Ciao. Qui ci sono i tuoi turni e i tuoi saldi, sempre. "
    "Posso preparare una preferenza da confermare tu: scrivimi «giovedì pomeriggio "
    "non posso», oppure tocca un giorno nei tuoi turni."
)
NON_HO_CAPITO = (
    "Non ho capito cosa ti serve. So dirti i tuoi turni e i tuoi saldi, e "
    "preparare una preferenza sulla tua scheda — la scrivi tu confermando."
)
#: un dipendente chiede «chi copre giovedì?». È una domanda legittima, ma la
#: risposta è del manager: qui non si apre il piano di tutti (`02` P1).
COPRI_NON_MIO = (
    "Chi copre un turno lo decide chi fa i turni: da qui non vedo il piano degli "
    "altri. Posso preparare una preferenza tua — «quel giorno non posso» — e la "
    "vedrà nella bozza."
)

RIFIUTO_ALTRUI = (
    "Non posso mostrarti dati di un'altra persona: turni e saldi sono suoi. "
    "Se ti serve per pianificare, aprilo dalla bozza che la tocca."
)
COPILOTA_GIU = "Copilota non disponibile. I tuoi turni pubblicati e i saldi restano a schermo."
#: nessun modello configurato: il sistema fa quello che deve, senza la prosa
COPILOTA_ASSENTE = "Copilota non configurato: rispondo solo con i dati calcolati."


@dataclass(slots=True)
class Risposta:
    turno: dict[str, Any]
    widget: list[dict[str, Any]] = field(default_factory=list)
    proposta: Proposta | None = None
    comando: str = ""
    degradato: bool = False  # niente prosa: i fatti restano
    motivo: str = ""  # "" | "giu" | "non-configurato" | "schema"

    @property
    def spento(self) -> bool:
        """**Solo** un guasto spegne il composer (`06` §4.5).

        Né la mancanza di configurazione né una risposta fuori schema: in
        entrambi i casi il sistema ha risposto con i fatti calcolati, e chi
        scrive deve poter scrivere di nuovo.
        """
        return self.motivo == "giu"

    def come_dict(self) -> dict[str, Any]:
        return {
            "turno": self.turno,
            "widget": self.widget,
            "comando": self.comando,
            "degradato": self.degradato,
            "motivo": self.motivo,
            "proposta": self.proposta.come_dict() if self.proposta else None,
        }


class Copilot:
    id = "copilot"
    usa_llm = True
    modello = "llm"
    versione_prompt = "copilot-2"

    # --- tool allowlist ------------------------------------------------------

    def tool(self) -> dict[str, Callable[..., Any]]:
        return {
            "mostra_turni": self._mostra_turni,
            "mostra_saldi": self._mostra_saldi,
            "consulta_scheduling": self._consulta_scheduling,
            "consulta_compliance": self._consulta_compliance,
            "consulta_secondo": self._consulta_secondo,
            "prepara_preferenza": self._prepara_preferenza,
        }

    def tool_per(self, attore: Attore) -> dict[str, Callable[..., Any]]:
        """Il roster **del chiamante**, non quello dell'agente.

        L'authz a valle resta (ogni tool passa da `esigi_*`), ma un'allowlist
        che si applica solo *dopo* aver chiamato Scheduling ha già fatto girare
        il pianificatore per chi non lo può usare — e la risposta arriva vuota
        invece che onesta (map P1, «sembra nulla»).
        """
        tutti = self.tool()
        if attore.manager:
            return tutti
        return {nome: fn for nome, fn in tutti.items() if nome in TOOL_DIPENDENTE}

    def _mostra_turni(self, attore: Attore, persona: str, **kw) -> dict:
        return vista.person_shifts(persona, attore, **kw)

    def _mostra_saldi(self, attore: Attore, persona: str) -> dict:
        return vista.person_balances(persona, attore)

    def _consulta_scheduling(self, attore: Attore, domanda: str, contesto: Contesto) -> Proposta:
        return consult("scheduling", domanda, contesto)

    def _consulta_compliance(self, attore: Attore, domanda: str, contesto: Contesto) -> Proposta:
        return consult("compliance", domanda, contesto)

    def _consulta_secondo(self, attore: Attore, domanda: str, contesto: Contesto) -> Proposta:
        return consult("secondo-pv", domanda, contesto)

    def _prepara_preferenza(self, attore: Attore, persona: str, testo: str) -> dict:
        return vista.scheda_preview(persona, testo)

    # --- copy ----------------------------------------------------------------

    def _copy(self, domanda: str, fatti: str, chip: list[str]) -> tuple[str, list[str], str]:
        """Il testo lo può scrivere il modello; i **numeri** no: arrivano già fatti."""
        try:
            dati, _ = llm().genera_json(
                prompt=(
                    "Rispondi in italiano, breve e concreto, a chi lavora in un supermercato. "
                    "Usa SOLO i fatti qui sotto: non aggiungere numeri, nomi o orari tuoi.\n"
                    f"domanda: {allowlist.blocco_dati(domanda)}\n"
                    f"fatti: {fatti}\n"
                    f"chip disponibili: {chip}"
                ),
                schema=SCHEMA_TURNO,
                sistema="copilot: unico agente che parla con l'umano. Solo JSON.",
            )
        except LLMNonConfigurato:
            return fatti, chip, "non-configurato"
        except SchemaNonRispettato:
            # il modello ha risposto, fuori schema: si scarta la prosa e si
            # tengono i fatti. Non è un guasto — il composer resta acceso.
            return fatti, chip, "schema"
        except LLMGiu:
            # degrado onesto: i fatti restano, la prosa no — e si dice
            return fatti, chip, "giu"
        proposte = [c for c in dati.get("chip", []) if c in chip]
        return str(dati.get("testo") or fatti), proposte or chip, ""

    # --- gateway -------------------------------------------------------------

    def _intent(self, domanda: str) -> tuple[str, str]:
        """NL → **enum chiuso**. Ritorna `(intent, motivo)`.

        È il punto in cui il linguaggio smette di essere linguaggio: da qui in
        poi il codice sa quale pipeline invocare, e nessun testo libero arriva
        a un agente per sbaglio (P-A).

        Senza modello, o con una risposta fuori schema, si cade sull'euristica
        deterministica — che è debole ma dice cose vere sulle frasi tipiche.
        Ciò che **non** si fa mai è il vecchio `else`: mandare tutto a
        Scheduling faceva rispondere il pianificatore a «ciao!», e a un
        dipendente arrivava la risposta svuotata dall'authz (map P1 §P0.2).
        """
        if not domanda:
            return "sconosciuto", ""
        try:
            dati, _ = llm().genera_json(
                prompt=(
                    "Classifica la richiesta di chi lavora in un supermercato in UNA "
                    f"di queste categorie: {', '.join(INTENT)}.\n"
                    "- preferenza: dichiara un vincolo personale («giovedì ho lezione»)\n"
                    "- turni_miei: chiede i propri turni o orari\n"
                    "- saldi: chiede ferie, permessi, residui\n"
                    "- copri: chiede chi copre un buco, chi lavora, scambi, riposi, regole\n"
                    "- comando_ciclo: chiede di generare/pubblicare/aprire il tabellone\n"
                    "- saluto: saluta o ringrazia, senza chiedere niente\n"
                    "- sconosciuto: tutto il resto\n"
                    f"richiesta: {allowlist.blocco_dati(domanda)}"
                ),
                schema=SCHEMA_INTENT,
                sistema="copilot: classificatore di intent. Solo JSON.",
            )
        except LLMNonConfigurato:
            return self._intent_det(domanda.lower()), "non-configurato"
        except SchemaNonRispettato:
            return self._intent_det(domanda.lower()), "schema"
        except LLMGiu:
            return self._intent_det(domanda.lower()), "giu"
        intent = str(dati.get("intent") or "")
        return (intent if intent in INTENT else "sconosciuto"), ""

    def _intent_det(self, basso: str) -> str:
        """L'euristica: fallback debole, mai il percorso principale.

        Ordine = specificità. Un comando è un comando anche se contiene la
        parola «turni»; un saluto vale solo se non chiede nient'altro.

        I pattern sono **prefissi**, con il confine solo davanti: `\\bturn`
        prende «turni» e «turno», `\\bturn\\b` non prende nessuno dei due. Con
        l'`else` su Scheduling l'errore non si vedeva — la domanda finiva
        comunque al pianificatore.
        """
        if self._comando(basso):
            return "comando_ciclo"
        if self._è_preferenza(basso):
            return "preferenza"
        if re.search(r"\b(?:ferie|permess|residu|montante|rol\b)", basso):
            return "saldi"
        if re.search(r"\b(?:turn|quando lavor|orari|doman|oggi|settimana)", basso):
            return "turni_miei"
        if re.search(
            r"\b(?:copr|coperto|sostitu|scambi|chi (?:fa|lavora|c'è)|manca|buco|"
            r"riposo|complian|viola|ccnl|negozio sa|memoria|di solito|abitudin)",
            basso,
        ):
            return "copri"
        if re.search(r"\b(?:ciao|salve|buongiorno|buonasera|grazie|ehi|hey|hola)", basso):
            return "saluto"
        return "sconosciuto"

    def _chip_utili(self, attore: Attore) -> list[str]:
        """Chip vere, non un `consulta` nudo che non fa niente (Book A1)."""
        return ["apri-scheda", "apri-tabellone"] if attore.manager else ["apri-scheda"]

    # --- ingresso ------------------------------------------------------------

    def rispondi(self, testo: str, attore: Attore, contesto: Contesto) -> Risposta:
        domanda = (testo or "").strip()
        basso = domanda.lower()
        widget: list[dict[str, Any]] = []
        proposta: Proposta | None = None
        comando = ""
        fatti = ""
        chip: list[str] = ["consulta"]

        bersaglio = self._bersaglio(domanda, attore)
        intent, motivo_intent = self._intent(domanda)

        # 0. saluto e sconosciuto: si risponde da soli, con quello che si sa
        #    fare. Nessun agente invocato, nessuna prosa generata — un «ciao»
        #    non vale un secondo giro di modello (`02` Loop P1).
        if intent in ("saluto", "sconosciuto"):
            return Risposta(
                turno=vista.copilot_turn(
                    SALUTO if intent == "saluto" else NON_HO_CAPITO,
                    self._chip_utili(attore),
                    motivo=motivo_intent,
                    generata=False,
                ),
                degradato=bool(motivo_intent),
                motivo=motivo_intent,
            )

        # 1. comandi di ciclo: il Copilot li traduce, non li esegue (`01` §4.4.4)
        comando = self._comando(basso) if intent == "comando_ciclo" else ""
        if comando:
            fatti = f"Comando riconosciuto: {comando}. Lo esegui tu con la chip."
            chip = [comando]
            testo_copy, chip_copy, motivo = self._copy(domanda, fatti, chip)
            turno = vista.copilot_turn(testo_copy, chip_copy, motivo=motivo)
            return Risposta(
                turno=turno, widget=widget, comando=comando, degradato=bool(motivo), motivo=motivo
            )

        # 2. preferenza («giovedì pomeriggio ho pianoforte»)
        if intent == "preferenza":
            preview = self._prepara_preferenza(attore, attore.slug, domanda)
            widget.append(preview)
            fatti = (
                f"Preparata la modifica di scheda: vincolo «{preview['vincolo']}». "
                "Non ho scritto niente: conferma tu."
            )
            chip = ["salva-preferenza"]
            testo_copy, chip_copy, motivo = self._copy(domanda, fatti, chip)
            turno = vista.copilot_turn(testo_copy, chip_copy, motivo=motivo)
            return Risposta(turno=turno, widget=widget, degradato=bool(motivo), motivo=motivo)

        # 3. saldi
        if intent == "saldi":
            try:
                saldi = self._mostra_saldi(attore, bersaglio)
            except Negato:
                return Risposta(turno=vista.copilot_turn(RIFIUTO_ALTRUI, ["consulta"]))
            widget.append(saldi)
            if saldi["vuoto"]:
                fatti = (
                    "Non ho ancora un saldo caricato per te: niente numero finché non arriva "
                    "l'import dello studio o il collegamento a Gamma."
                )
            else:
                voci = ", ".join(
                    f"{ETICHETTE.get(v['tipo'], v['tipo'])} {v['residuo_ore']:g}h" for v in saldi["voci"]
                )
                stale = " (non in tempo reale)" if saldi.get("stale") else ""
                fatti = f"{voci}{stale}. Fonte: {saldi['fonte']}, aggiornato {saldi['aggiornato_at']}."
            testo_copy, chip_copy, motivo = self._copy(domanda, fatti, chip)
            turno = vista.copilot_turn(testo_copy, chip_copy, motivo=motivo)
            return Risposta(turno=turno, widget=widget, degradato=bool(motivo), motivo=motivo)

        # 4. turni
        if intent == "turni_miei":
            try:
                turni = self._mostra_turni(attore, bersaglio)
            except Negato:
                return Risposta(turno=vista.copilot_turn(RIFIUTO_ALTRUI, ["consulta"]))
            widget.append(turni)
            adesso = turni["adesso"]
            fatti = (
                f"Adesso: {adesso['orario']}." if adesso else "Adesso non sei in turno."
            ) + f" Prossimi {len(turni['prossimi'])} turni, {turni['ore_periodo']:g}h nel periodo."
            testo_copy, chip_copy, motivo = self._copy(domanda, fatti, chip)
            turno = vista.copilot_turn(testo_copy, chip_copy, motivo=motivo)
            return Risposta(turno=turno, widget=widget, degradato=bool(motivo), motivo=motivo)

        # 5. `copri`: domanda di dominio sul piano. È l'unico intent che apre
        #    il roster degli agenti, e lo apre **solo** a chi fa i turni.
        if "consulta_scheduling" not in self.tool_per(attore):
            # niente path deterministico sicuro per un dipendente: si dice cosa
            # si può fare invece di far girare il pianificatore a vuoto
            return Risposta(
                turno=vista.copilot_turn(
                    COPRI_NON_MIO, self._chip_utili(attore), motivo=motivo_intent, generata=False
                ),
                degradato=bool(motivo_intent),
                motivo=motivo_intent,
            )

        # Dentro `copri` la scelta dell'agente resta deterministica: l'enum non
        # ha un valore per «rompe un riposo?» o «cosa sa il negozio», e
        # inventarne uno vorrebbe dire riaprire `01`.
        if re.search(r"\b(riposo|compliance|viola|ccnl)\b", basso):
            proposta = self._consulta_compliance(attore, domanda, contesto)
        elif re.search(r"\b(negozio sa|memoria|di solito|abitudine)\b", basso):
            proposta = self._consulta_secondo(attore, domanda, contesto)
        else:
            proposta = self._consulta_scheduling(attore, domanda, contesto)

        widget.append(vista.rationale(proposta.rationale, proposta.fonti, proposta.confidenza))
        for slug in proposta.payload.get("persone", [])[:5]:
            try:
                widget.append(self._mostra_turni(attore, slug))
            except Negato:
                continue
        fatti = proposta.rationale
        testo_copy, chip_copy, motivo = self._copy(domanda, fatti, chip)
        turno = vista.copilot_turn(testo_copy, chip_copy, motivo=motivo)
        return Risposta(
            turno=turno, widget=widget, proposta=proposta, degradato=bool(motivo), motivo=motivo
        )

    # --- riconoscimento ------------------------------------------------------

    def _comando(self, basso: str) -> str:
        if re.search(r"\b(genera|prepara|fammi).{0,20}\b(bozza|turni|settimana)\b", basso):
            return "genera-bozza"
        if re.search(r"\b(apri|mostra).{0,12}\btabellone\b", basso):
            return "apri-tabellone"
        if re.search(r"\bcollega.{0,12}(google|calendario)\b", basso):
            return "collega-google"
        if re.search(r"\bscollega.{0,12}(google|calendario)\b", basso):
            return "scollega-google"
        if re.search(r"\bpubblic", basso):
            return "pubblica"
        return ""

    def _è_preferenza(self, basso: str) -> bool:
        return bool(
            re.search(
                r"\b(?:ho (?:lezione|corso|pianoforte|scuola)|non posso|preferisc|no chiusura|"
                r"vorrei (?:non|evitare)|sono impegnat)",
                basso,
            )
        )

    def _bersaglio(self, domanda: str, attore: Attore) -> str:
        """«i turni di Anna» → anna-mondora, se l'authz lo permette."""
        for persona in kb_persone.tutte():
            primo = persona.nome.split()[0].lower()
            if re.search(rf"\b{re.escape(primo)}\b", domanda.lower()):
                return persona.slug
        return attore.slug

    # --- interfaccia agente --------------------------------------------------

    def nel_ciclo(self, contesto: Contesto, **fase) -> Proposta:
        raise RuntimeError("il Copilot sta fuori dal ciclo: traduce, non avanza lo stato")

    def consulta(self, domanda: str, contesto: Contesto, **extra) -> Proposta:
        attore: Attore = extra["attore"]
        risposta = self.rispondi(domanda, attore, contesto)
        return risposta.proposta or Proposta(
            agente=self.id,
            tipo="risposta",
            payload={"domanda": domanda, "turno": risposta.turno},
            rationale=risposta.turno.get("testo", ""),
        )


AGENTE = registra(Copilot())


def spento(motivo: str = "giu") -> dict[str, Any]:
    """Ciò che si vede quando il backend non risponde: onesto, non un finto 200."""
    return vista.copilot_turn(
        COPILOTA_GIU if motivo == "giu" else COPILOTA_ASSENTE, [], motivo=motivo
    )


def oggi() -> dt.date:
    return dt.date.today()
