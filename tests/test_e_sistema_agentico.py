"""Evals E1–E8 di `specs/01-sistema-agentico.md` §6."""

from __future__ import annotations

import datetime as dt

import pytest

from timemachine.agents import base as agenti
from timemachine.agents.compliance import Compliance
from timemachine.agents.llm import BackendFake, LLMGiu, imposta_llm
from timemachine.domain.bozza import piano_da_celle
from timemachine.domain.grounding import Gate
from timemachine.domain.modelli import Preferenza, Spezzone, Turno
from timemachine.domain.proposta import Proposta, PropostaInvalida
from timemachine.kb import persone as kb_persone
from timemachine.kb import turni as kb_turni
from timemachine.orchestrator import ciclo as orchestratore
from timemachine.orchestrator import contesto as ctx

from .conftest import OGGI, SETTIMANA, SETTIMANA_PROSSIMA


def _bozza(manager, varianti=1):
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    ciclo.genera_bozza(manager, varianti=varianti)
    return ciclo


# --- E1 ----------------------------------------------------------------------


def test_e1_ogni_cella_ha_persona_e_mansione_esistenti(manager, contesto):
    proposta = agenti.agente("scheduling").nel_ciclo(contesto)
    gate = Gate.da_kb()
    assert proposta.payload["celle"]
    for cella in proposta.payload["celle"]:
        assert gate.persona_esiste(cella["persona"]), cella
        for mansione in cella["mansioni"]:
            assert gate.mansione_di(cella["persona"], mansione), cella


# --- E2 ----------------------------------------------------------------------


def test_e2_le_pizze_le_fa_chi_ha_la_mansione_pizze(manager, contesto):
    piano = piano_da_celle(
        agenti.agente("scheduling").nel_ciclo(contesto).payload["celle"], SETTIMANA_PROSSIMA
    )
    schede = kb_persone.per_slug()
    con_pizze = {s for s, p in schede.items() if p.ha_mansione("pizze")}
    assert {"anna-mondora", "debora", "rolando", "mara"} <= con_pizze

    fasce_pizze = 0
    for slug in piano.persone():
        for turno in piano.della_persona(slug):
            if "pizze" in turno.mansioni:
                fasce_pizze += 1
                assert slug in con_pizze, f"{slug} in pizze senza mansione"
    assert fasce_pizze > 0, "una settimana di Le Rocce senza nessuna fascia pizze è sospetta"


# --- E3 ----------------------------------------------------------------------


def test_e3_preferenza_onorata_o_spiegata(manager):
    kb_persone.salva_preferenza(
        "anna-mondora",
        Preferenza(vincolo="no_pomeriggio: gio", storia="lezione di pianoforte", origine="confermata"),
    )
    contesto = ctx.carica(SETTIMANA_PROSSIMA)
    proposta = agenti.agente("scheduling").nel_ciclo(contesto)
    piano = piano_da_celle(proposta.payload["celle"], SETTIMANA_PROSSIMA)
    giovedi = SETTIMANA_PROSSIMA + dt.timedelta(days=3)
    turno = piano.turno("anna-mondora", giovedi)

    pomeriggio = turno is not None and any(12 <= s.inizio.hour < 18 for s in turno.spezzoni)
    if pomeriggio:
        testo = " ".join(proposta.payload["note"])
        assert "no_pomeriggio: gio" in testo and "anna-mondora" in testo, (
            "se la preferenza non è onorata, la rationale deve dirlo"
        )


def test_e3_bis_il_prompt_non_contiene_la_storia(manager):
    kb_persone.salva_preferenza(
        "anna-mondora",
        Preferenza(vincolo="no_pomeriggio: gio", storia="lezione di pianoforte"),
    )
    contesto = ctx.carica(SETTIMANA_PROSSIMA)
    per_prompt = contesto.per_prompt("scheduling")
    testo = str(per_prompt)
    assert "no_pomeriggio: gio" in testo
    assert "pianoforte" not in testo


# --- E4 ----------------------------------------------------------------------


def test_e4_bozza_che_rompe_un_riposo_non_e_pubblicabile(manager):
    ciclo = _bozza(manager)
    assert ciclo.bozza is not None
    # sette giorni lavorati di fila: il riposo settimanale salta
    for giorno in ciclo.bozza.piano.giorni:
        ciclo.bozza.piano.imposta(
            Turno(
                persona="anna-mondora",
                data=giorno,
                spezzoni=(Spezzone(dt.time(9), dt.time(13), ("pizze",)),),
            )
        )
    proposta = Compliance().verifica(ciclo.bozza.piano)
    assert proposta.payload["pubblicabile"] is False
    regole = {v["regola"] for v in proposta.payload["violazioni"]}
    assert "riposo-settimanale" in regole

    ciclo.bozza.pubblicabile = False
    ciclo.bozza.accettata = True
    assert "pubblica" not in ciclo.chip()
    with pytest.raises(orchestratore.CicloBloccato):
        ciclo.pubblica(manager)


# --- E5 ----------------------------------------------------------------------


def test_e5_consulta_e_senza_side_effect(manager, contesto):
    prima = kb_turni.percorso(SETTIMANA).read_text(encoding="utf-8")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    stato_prima = ciclo.stato

    proposta = agenti.consult(
        "scheduling", "chi copre giovedì pomeriggio senza straordinario?", contesto
    )
    assert isinstance(proposta, Proposta)
    assert proposta.tipo == "risposta"
    assert proposta.fonti and all(f.startswith("kb/") for f in proposta.fonti)
    assert ciclo.stato == stato_prima
    assert kb_turni.percorso(SETTIMANA).read_text(encoding="utf-8") == prima


# --- E6 ----------------------------------------------------------------------


def test_e6_ai_giu_niente_bozza_ma_i_turni_restano(manager, anna):
    from timemachine import vista

    imposta_llm(BackendFake(giu=True))
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)

    turni = vista.person_shifts("anna-mondora", anna, oggi=OGGI)
    assert turni["ore_periodo"] == 41
    assert turni["adesso"]["orario"] == "14–20"

    # forecast e scheduling reggono senza LLM (le note libere si perdono, i turni no)
    job = ciclo.genera_bozza(manager)
    assert job.stato in ("fatto", "fallito")
    if job.stato == "fallito":
        assert ciclo.bozza is None and ciclo.stato == "idle"
        assert "non disponibili" in ciclo.errore or ciclo.errore == ""


def test_e6_bis_backend_giu_alza_llmgiu_non_ritorna_finto():
    backend = BackendFake(giu=True)
    with pytest.raises(LLMGiu):
        backend.genera("qualsiasi cosa")


# --- E7 ----------------------------------------------------------------------


def test_e7_modifica_piu_approva_finisce_in_kb_e_nel_secondo(manager):
    from timemachine.kb import secondo as kb_secondo

    ciclo = _bozza(manager)
    assert ciclo.bozza is not None
    matteo_prima = ciclo.bozza.piano.turno("matteo", SETTIMANA_PROSSIMA)
    assert matteo_prima is not None

    ciclo.sposta_turno(manager, "matteo", SETTIMANA_PROSSIMA, "6-12")
    ciclo.sposta_turno(manager, "matteo", SETTIMANA_PROSSIMA + dt.timedelta(days=6), "R")
    # tolto lo straordinario, il piano torna pubblicabile
    assert ciclo.bozza.pubblicabile, ciclo.bozza.violazioni

    ciclo.accetta(manager)
    piano = ciclo.pubblica(manager)

    scritto = kb_turni.leggi(SETTIMANA_PROSSIMA)
    assert scritto is not None
    assert scritto.turno("matteo", SETTIMANA_PROSSIMA).etichetta() == "6–12"
    assert scritto.stato == "pubblicato"
    assert kb_secondo.note(), "il secondo del PV impara dalla decisione umana"
    assert all("Matteo è" not in n for n in kb_secondo.note())
    assert piano.settimana == SETTIMANA_PROSSIMA


# --- E8 ----------------------------------------------------------------------


def test_e8_persona_o_mansione_sconosciuta_si_scarta_con_motivo():
    gate = Gate.da_kb()
    tenute, scarti = gate.valida_celle(
        [
            {"persona": "anna-mondora", "data": "2026-07-06", "mansioni": ["pizze"]},
            {"persona": "giovanni-inventato", "data": "2026-07-06", "mansioni": []},
            {"persona": "jessica", "data": "2026-07-06", "mansioni": ["macelleria"]},
        ]
    )
    assert len(tenute) == 1
    motivi = [s.motivo for s in scarti]
    assert any("non in kb/persone" in m for m in motivi)
    assert any("non ha la mansione" in m for m in motivi)


def test_e8_bis_tipo_di_proposta_sconosciuto_non_si_costruisce():
    with pytest.raises(PropostaInvalida):
        Proposta(agente="scheduling", tipo="foo-tipo")
    with pytest.raises(PropostaInvalida):
        Proposta(agente="agente-fantasma", tipo="risposta")


def test_e8_ter_output_llm_fuori_schema_si_scarta_dopo_i_retry():
    from timemachine.agents.llm import LLM, SchemaNonRispettato

    llm = LLM(backend=BackendFake(risposte=["{\"sbagliato\": 1}", "non è json"]), retry=1)
    with pytest.raises(SchemaNonRispettato):
        llm.genera_json(
            "prompt", {"type": "object", "required": ["ordine"], "properties": {}}
        )


# --- E10 ---------------------------------------------------------------------


def test_e10_ciao_non_e_consult_scheduling(anna, manager, contesto, monkeypatch):
    """E10: il gateway classifica prima di invocare (`01` Loop P1).

    Il `default → consult(scheduling)` faceva parlare il Copilot *come* il
    pianificatore: a un dipendente tornava una risposta vuota (l'authz toglie
    i turni altrui) e a chiunque tornava una consulenza mai chiesta. P-L
    storto: un agente che risponde a una domanda che non è sua.
    """
    from timemachine.agents import base
    from timemachine.agents import copilot as agente_copilot

    visti: list[str] = []
    vero = base.consult

    def spia(id_agente, domanda, contesto, **extra):
        visti.append(id_agente)
        return vero(id_agente, domanda, contesto, **extra)

    monkeypatch.setattr(base, "consult", spia)
    monkeypatch.setattr("timemachine.agents.copilot.consult", spia)

    for chi in (anna, manager):
        for frase in ("ciao!", "buongiorno", "il pesce è fresco?"):
            risposta = agente_copilot.AGENTE.rispondi(frase, chi, contesto)
            assert visti == [], f"{frase} ha invocato {visti}"
            assert risposta.proposta is None
            assert risposta.turno["chip"], "un vicolo cieco non è una risposta"
            assert risposta.spento is False

    # un dipendente non apre il roster nemmeno con una domanda di dominio
    risposta = agente_copilot.AGENTE.rispondi("chi copre giovedì?", anna, contesto)
    assert visti == []
    assert "non vedo il piano degli altri" in risposta.turno["testo"]

    # il manager sì: stessa frase, stesso gateway, agente giusto
    agente_copilot.AGENTE.rispondi("chi copre giovedì?", manager, contesto)
    assert visti == ["scheduling"]


def test_e10_bis_lallowlist_del_dipendente_e_piu_corta(anna, manager):
    from timemachine.agents.copilot import TOOL_DIPENDENTE, Copilot

    copilot = Copilot()
    assert set(copilot.tool_per(anna)) == set(TOOL_DIPENDENTE)
    assert set(copilot.tool_per(manager)) == set(copilot.tool())
    assert "consulta_scheduling" not in copilot.tool_per(anna)
    assert "genera-bozza" not in str(copilot.tool_per(anna))


# --- confine di fiducia ------------------------------------------------------


def test_orchestratore_non_pubblica_da_solo(manager):
    ciclo = _bozza(manager)
    assert ciclo.stato == "attesa_umano"
    assert kb_turni.leggi(SETTIMANA_PROSSIMA) is None
    with pytest.raises(orchestratore.CicloBloccato):
        ciclo.pubblica(manager)  # non accettata: niente pubblicazione


def test_solo_il_manager_muove_il_ciclo(anna):
    from timemachine.security.authz import Negato

    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    with pytest.raises(Negato):
        ciclo.genera_bozza(anna)


def test_compliance_non_usa_llm():
    assert Compliance().usa_llm is False
    assert agenti.agente("compliance").modello == "codice"
