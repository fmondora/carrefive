"""Catalogo GenUI — **chiuso e versionato** (`02` §4.2).

L'AI sceglie *tipi*, non markup (P-A). L'enum del modello è ⊆ del Renderer:
un tipo fuori catalogo si droppa, la UI resta invariata (U6 / E8).
"""

from __future__ import annotations

from typing import Final

VERSIONE_CATALOGO: Final = "1.0.0"

# --- atomi -------------------------------------------------------------------

ATOMI: Final = ("orario", "etichetta-mansione", "badge-stato", "nome-persona", "giorno")

# --- widget ------------------------------------------------------------------

WIDGET: Final = (
    "person-shifts",
    "person-balances",
    "coverage-gap",
    "compliance-block",
    "proposal-pack",
    "rationale",
    "diff-edit",
    "scheda-preview",
    "secondo-note",
    "copilot-turn",
    "week-grid",
)

#: ciò che il Copilot può *scegliere* di mostrare. `week-grid` non è qui:
#: si monta solo con la chip `apri-tabellone` (`02` §4.2).
WIDGET_SELEZIONABILI_LLM: Final = (
    "person-shifts",
    "person-balances",
    "coverage-gap",
    "compliance-block",
    "proposal-pack",
    "rationale",
    "diff-edit",
    "scheda-preview",
    "secondo-note",
    "copilot-turn",
)

#: contenuto deterministico: la forma e i fatti non li scrive un LLM
WIDGET_DETERMINISTICI: Final = (
    "person-shifts",
    "person-balances",
    "coverage-gap",
    "compliance-block",
    "diff-edit",
    "secondo-note",
    "week-grid",
)

# --- chip --------------------------------------------------------------------

CHIP: Final = (
    "consulta",
    "salva-preferenza",
    "apri-scheda",
    "genera-bozza",
    "accetta-bozza",
    "scegli-variante",
    "rifiuta-bozza",
    "pubblica",
    "sposta-turno",
    "apri-tabellone",
    "collega-google",
    "scollega-google",
    "riprova",
    "aggiorna-saldi",
    "invia-attivazione",
    "mostra-qr",
    "revoca-invito",
)

#: chip che richiedono una conferma esplicita (approval card, `06` §4.3)
CHIP_CON_CONFERMA: Final = (
    "salva-preferenza",
    "accetta-bozza",
    "rifiuta-bozza",
    "pubblica",
    "scollega-google",
)

#: chip che scrivono. Solo endpoint firmati le eseguono (`05` §4.4)
CHIP_DI_WRITE: Final = (
    "salva-preferenza",
    "pubblica",
    "sposta-turno",
    "collega-google",
    "scollega-google",
    "accetta-bozza",
    "rifiuta-bozza",
    "invia-attivazione",
    "revoca-invito",
)

#: chip riservate al ruolo manager / attivatore
CHIP_MANAGER: Final = (
    "genera-bozza",
    "accetta-bozza",
    "scegli-variante",
    "rifiuta-bozza",
    "pubblica",
    "sposta-turno",
    "apri-tabellone",
)
CHIP_ATTIVATORE: Final = ("invia-attivazione", "mostra-qr", "revoca-invito")


def widget_valido(tipo: str) -> bool:
    return tipo in WIDGET


def chip_valida(nome: str) -> bool:
    return nome in CHIP


def filtra_widget(candidati: list[dict]) -> tuple[list[dict], list[str]]:
    """Registry unico prima dello stream: tiene i noti, riporta gli scartati."""
    tenuti: list[dict] = []
    scartati: list[str] = []
    for w in candidati:
        tipo = (w or {}).get("tipo")
        if isinstance(tipo, str) and tipo in WIDGET_SELEZIONABILI_LLM:
            tenuti.append(w)
        else:
            scartati.append(str(tipo))
    return tenuti, scartati


def filtra_chip(candidate: list[str]) -> tuple[list[str], list[str]]:
    tenute = [c for c in candidate if c in CHIP]
    scartate = [c for c in candidate if c not in CHIP]
    return tenute, scartate
