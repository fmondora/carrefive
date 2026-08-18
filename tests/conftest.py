"""Fixture comuni.

Ogni test gira su una **copia** di `kb/`: la knowledge del pilota è archivio di
dati personali, non un banco di prova (`05` §3). Lo stato applicativo
(`.stato/`) è un tmp per test, così token e sessioni non sopravvivono.

La data «oggi» è fissata al lunedì 29/06/2026 — la settimana pubblicata che sta
in `kb/turni/` e che le spec usano in tutti gli use case.
"""

from __future__ import annotations

import datetime as dt
import shutil
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))

OGGI = dt.date(2026, 6, 29)
SETTIMANA = dt.date(2026, 6, 29)
SETTIMANA_PROSSIMA = dt.date(2026, 7, 6)


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    """kb copiata, stato isolato, singleton azzerati, backend finti."""
    kb = tmp_path / "kb"
    shutil.copytree(RADICE / "kb", kb)
    monkeypatch.setenv("TM_KB", str(kb))
    monkeypatch.setenv("TM_STATO", str(tmp_path / "stato"))
    monkeypatch.setenv("TM_FINDINGS", str(tmp_path / "findings"))
    monkeypatch.setenv("TM_OGGI", OGGI.isoformat())
    monkeypatch.setenv("SALDI_FONTE", "file")
    monkeypatch.setenv("TM_LLM", "fake")
    monkeypatch.delenv("TM_GOOGLE", raising=False)
    monkeypatch.delenv("TM_OIDC", raising=False)

    from timemachine import saldi as porta_saldi
    from timemachine.agents import llm as modulo_llm
    from timemachine.auth import sessioni, store as auth_store
    from timemachine.calendario import modulo_client as modulo_calendario
    from timemachine.auth import attivazione, oidc
    from timemachine.orchestrator import ciclo as orchestratore
    from timemachine.orchestrator.jobs import CODA
    from timemachine.security import authz

    porta_saldi.imposta_porta(None)
    modulo_llm.imposta_llm(None)
    modulo_calendario.imposta_client(modulo_calendario.ClientFinto())
    oidc.imposta_verificatore(oidc.VerificatoreFinto())
    orchestratore.azzera()
    CODA.svuota()
    sessioni.REGISTRO.svuota()
    authz.REGISTRO.svuota()
    from timemachine.auth import stato_oauth

    stato_oauth.REGISTRO.svuota()
    attivazione.LIMITATORE.azzera()
    auth_store.svuota()
    yield kb
    porta_saldi.imposta_porta(None)
    modulo_llm.imposta_llm(None)
    modulo_calendario.imposta_client(None)
    oidc.imposta_verificatore(None)


@pytest.fixture
def kb(ambiente) -> Path:
    return ambiente


@pytest.fixture
def manager():
    """Il manager di Le Rocce, che è anche l'attivatore (Emilio, `07` §7)."""
    from timemachine.kb import persone as kb_persone
    from timemachine.security.authz import Attore

    kb_persone.imposta_ruoli("francesco", ["manager", "attivatore"])
    return Attore(slug="francesco", ruoli=("dipendente", "manager", "attivatore"))


@pytest.fixture
def anna():
    from timemachine.security.authz import Attore

    return Attore(slug="anna-mondora", ruoli=("dipendente",))


@pytest.fixture
def jessica():
    from timemachine.security.authz import Attore

    return Attore(slug="jessica", ruoli=("dipendente",))


@pytest.fixture
def calendario_finto():
    from timemachine.calendario import modulo_client as modulo

    finto = modulo.ClientFinto()
    modulo.imposta_client(finto)
    return finto


@pytest.fixture
def llm_finto():
    """Backend scriptabile. Di default alza LLMGiu: gli agenti devono reggere."""
    from timemachine.agents import llm as modulo

    finto = modulo.BackendFake()
    modulo.imposta_llm(finto)
    return finto


@pytest.fixture
def client():
    """TestClient su https: i cookie di sessione sono `secure`."""
    from fastapi.testclient import TestClient

    from timemachine.web.app import app

    with TestClient(app, base_url="https://testserver") as c:
        yield c


@pytest.fixture
def sessione_di(client):
    """Apre una sessione per uno slug senza passare dal login (test di superficie)."""
    from timemachine.auth import sessioni

    def apri(slug: str):
        s = sessioni.REGISTRO.apri(slug)
        client.cookies.set(sessioni.NOME_COOKIE, s.id)
        return s

    return apri


@pytest.fixture
def contesto():
    from timemachine.orchestrator import contesto as ctx

    return ctx.carica(SETTIMANA_PROSSIMA)
