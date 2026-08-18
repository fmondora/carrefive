"""Il backend astratto: scelta, degrado, validazione al confine (`01` §3).

Nessun test qui tocca la rete: `api` e `cli` si esercitano solo nella parte di
*scelta* e di gestione errori, mai chiamandoli davvero.
"""

from __future__ import annotations

import pytest

from timemachine.agents import llm as modulo
from timemachine.agents.llm import (
    LLM,
    BackendFake,
    LLMGiu,
    LLMNonConfigurato,
    SchemaNonRispettato,
    scelta_automatica,
)

SCHEMA = {
    "type": "object",
    "required": ["testo"],
    "properties": {"testo": {"type": "string"}},
}


# --- scelta del backend ------------------------------------------------------


def test_con_una_chiave_in_env_si_usa_lapi(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-finta")
    assert scelta_automatica() == "api"


def test_con_un_auth_token_si_usa_lapi(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "oat-finto")
    assert scelta_automatica() == "api"


def test_senza_chiave_ma_con_la_cli_si_usa_la_cli(monkeypatch):
    """Il caso di sviluppo: autenticato con Claude Code, nessuna chiave in env."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(modulo.shutil, "which", lambda c: None if c == "ant" else f"/bin/{c}")
    assert scelta_automatica() == "cli"


def test_senza_niente_non_ce_modello(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(modulo.shutil, "which", lambda c: None)
    assert scelta_automatica() == "fake"


def test_tm_llm_esplicito_vince_sulla_scelta_automatica(monkeypatch):
    monkeypatch.setenv("TM_LLM", "fake")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-finta")
    modulo.imposta_llm(None)
    assert modulo.llm().nome == "fake"


def test_il_comando_della_cli_e_configurabile(monkeypatch):
    """Chi sviluppa può puntare la CLI a un modello più rapido — scelta sua."""
    monkeypatch.setenv("TM_LLM_CLI", "claude -p --model haiku")
    assert modulo.BackendCLI().comando == ["claude", "-p", "--model", "haiku"]
    monkeypatch.delenv("TM_LLM_CLI")
    assert modulo.BackendCLI().comando == ["claude", "-p"]


def test_il_modello_di_default_e_opus_5(monkeypatch):
    monkeypatch.delenv("TM_MODELLO", raising=False)
    assert modulo.BackendAPI().modello == "claude-opus-5"
    monkeypatch.setenv("TM_MODELLO", "claude-sonnet-5")
    assert modulo.BackendAPI().modello == "claude-sonnet-5"


def test_lapi_non_legge_la_chiave_a_mano():
    """La catena di credenziali è dell'SDK: env, profilo `ant`, federazione.

    Leggerla a mano vorrebbe dire farla passare dal nostro codice — e romperebbe
    il caso «autenticato con `ant auth login`, nessuna chiave in env».
    """
    sorgente = (modulo.__file__).replace(".pyc", ".py")
    with open(sorgente, encoding="utf-8") as f:
        testo = f.read()
    corpo_api = testo.split("class BackendAPI:")[1].split("# --- confine")[0]
    assert 'os.environ.get("ANTHROPIC_API_KEY")' not in corpo_api
    assert "anthropic.Anthropic()" in corpo_api


# --- degrado e validazione ---------------------------------------------------


def test_backend_senza_copione_e_non_configurato_non_giu():
    with pytest.raises(LLMNonConfigurato):
        BackendFake().genera("qualsiasi cosa")


def test_backend_marcato_giu_e_un_guasto():
    with pytest.raises(LLMGiu) as e:
        BackendFake(giu=True).genera("qualsiasi cosa")
    assert not isinstance(e.value, LLMNonConfigurato)


def test_json_valido_passa_al_primo_colpo():
    llm = LLM(backend=BackendFake(risposte=[{"testo": "ciao"}]))
    dati, scarti = llm.genera_json("prompt", SCHEMA)
    assert dati["testo"] == "ciao" and scarti == []


def test_json_dentro_un_fence_si_estrae():
    llm = LLM(backend=BackendFake(risposte=['Ecco:\n```json\n{"testo": "ok"}\n```']))
    dati, _ = llm.genera_json("prompt", SCHEMA)
    assert dati["testo"] == "ok"


def test_primo_tentativo_fuori_schema_poi_buono():
    llm = LLM(backend=BackendFake(risposte=['{"altro": 1}', '{"testo": "ok"}']), retry=1)
    dati, scarti = llm.genera_json("prompt", SCHEMA)
    assert dati["testo"] == "ok"
    assert len(scarti) == 1 and "obbligatorio" in scarti[0]


def test_dopo_i_retry_si_rinuncia_con_motivo():
    llm = LLM(backend=BackendFake(risposte=['{"altro": 1}', "non è json"]), retry=1)
    with pytest.raises(SchemaNonRispettato):
        llm.genera_json("prompt", SCHEMA)
