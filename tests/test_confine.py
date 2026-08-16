"""Il confine di fiducia come **proprietà del codice**, non come buona intenzione.

`00` §5.2: «motore di calcolo ore/maggiorazioni, registro timbrature, export
paghe = zero AI». Se un modulo deterministico importasse il layer LLM, la
frase resterebbe vera solo finché qualcuno non scrive una riga distratta.
Qui la si verifica.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACCHETTO = Path(__file__).resolve().parents[1] / "timemachine"

#: moduli che non possono dipendere dagli agenti né dal backend LLM
DETERMINISTICI = [
    "domain/ore.py",
    "domain/modelli.py",
    "domain/saldi.py",
    "domain/bozza.py",
    "domain/catalogo.py",
    "kb/celle.py",
    "kb/persone.py",
    "kb/turni.py",
    "kb/saldi.py",
    "kb/secondo.py",
    "saldi/adapter_file.py",
    "saldi/adapter_gamma.py",
    "saldi/importer.py",
    "calendario/sync.py",
    "calendario/store.py",
    "calendario/client.py",
    "auth/attivazione.py",
    "auth/password.py",
    "auth/sessioni.py",
    "auth/oidc.py",
    "security/authz.py",
    "security/privacy.py",
    "security/diritti.py",
    "security/audit.py",
    "tempo.py",
    "vista.py",
]


def _import_di(percorso: Path) -> set[str]:
    albero = ast.parse(percorso.read_text(encoding="utf-8"))
    fuori: set[str] = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            fuori.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            punti = "." * (nodo.level or 0)
            fuori.add(f"{punti}{nodo.module or ''}")
    return fuori


@pytest.mark.parametrize("relativo", DETERMINISTICI)
def test_il_deterministico_non_importa_gli_agenti(relativo):
    moduli = _import_di(PACCHETTO / relativo)
    vietati = [m for m in moduli if "agents" in m or m.endswith("llm")]
    assert not vietati, f"{relativo} importa {vietati}: il calcolo non passa dal modello"


def test_il_motore_ore_e_puro():
    """Nessuna rete, nessun file, nessun orologio: solo aritmetica sui turni."""
    moduli = _import_di(PACCHETTO / "domain" / "ore.py")
    assert moduli <= {"datetime", "__future__", ".modelli"}


def test_compliance_non_importa_il_backend_llm():
    moduli = _import_di(PACCHETTO / "agents" / "compliance.py")
    assert not any(m.endswith("llm") for m in moduli)


def test_il_catalogo_selezionabile_dal_modello_e_sottoinsieme_del_renderer():
    from timemachine.domain import catalogo

    assert set(catalogo.WIDGET_SELEZIONABILI_LLM) <= set(catalogo.WIDGET)
    assert "week-grid" not in catalogo.WIDGET_SELEZIONABILI_LLM


def test_il_renderer_copre_tutto_il_catalogo():
    """Enum del modello ⊆ Renderer (`02` §3): niente tipo senza macro."""
    from timemachine.domain import catalogo

    sorgente = (PACCHETTO / "web" / "templates" / "widget.html").read_text(encoding="utf-8")
    for tipo in catalogo.WIDGET:
        assert f'w.tipo == "{tipo}"' in sorgente, f"il renderer non conosce {tipo}"


def test_tutte_le_chip_del_guscio_sono_nel_catalogo():
    from timemachine.domain import catalogo
    from timemachine.orchestrator.ciclo import CHIP_PER_STATO

    for chip in {c for chips in CHIP_PER_STATO.values() for c in chips} | {"pubblica"}:
        assert catalogo.chip_valida(chip), chip


def test_il_roster_e_chiuso():
    from timemachine.agents import base

    assert set(base.roster()) == set(base.ID_AGENTI)
    with pytest.raises(base.AgenteSconosciuto):
        base.agente("agente-ombra")


def test_un_solo_agente_parla_con_lumano():
    """P-L: solo il Copilot emette widget e chip; gli altri emettono dominio."""
    from timemachine.agents import base

    for id_agente, agente in base.roster().items():
        sorgente = (PACCHETTO / "agents" / f"{id_agente.replace('-', '_')}.py").read_text(
            encoding="utf-8"
        )
        if id_agente == "copilot":
            assert "vista.copilot_turn" in sorgente
        else:
            assert "copilot_turn" not in sorgente, f"{id_agente} sta emettendo widget"


def test_solo_il_gate_pubblica_scrive_i_turni():
    """`kb_turni.scrivi` è l'atto finale: lo chiama solo `pubblica` (più la CLI/test)."""
    chiamanti = []
    for percorso in PACCHETTO.rglob("*.py"):
        testo = percorso.read_text(encoding="utf-8")
        if "kb_turni.scrivi(" in testo or "turni.scrivi(" in testo:
            chiamanti.append(percorso.relative_to(PACCHETTO).as_posix())
    assert set(chiamanti) <= {"orchestrator/ciclo.py", "kb/turni.py"}, chiamanti


def test_lorologio_finto_e_davvero_fermo(monkeypatch):
    """Regressione: `TM_OGGI` deve pinnare data **e** ora.

    Mescolare una data finta con l'orologio reale rendeva il sync del
    calendario dipendente dall'ora in cui giravano i test.
    """
    import datetime as dt

    from timemachine import tempo

    monkeypatch.setenv("TM_OGGI", "2026-06-29")
    assert tempo.adesso() == dt.datetime(2026, 6, 29, 0, 0)
    assert tempo.adesso() == tempo.adesso()

    monkeypatch.setenv("TM_OGGI", "2026-06-29T14:05")
    assert tempo.adesso() == dt.datetime(2026, 6, 29, 14, 5)
    assert tempo.oggi() == dt.date(2026, 6, 29)
    assert tempo.lunedi_di() == dt.date(2026, 6, 29)
