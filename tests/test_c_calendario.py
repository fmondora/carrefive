"""Evals C1–C9 di `specs/03-calendario-google.md` §6."""

from __future__ import annotations

import datetime as dt

import pytest

from timemachine.calendario import collega, scollega
from timemachine.calendario import store as token_store
from timemachine.calendario import sync
from timemachine.calendario.client import SCOPE
from timemachine.domain.modelli import Spezzone, Turno
from timemachine.kb import persone as kb_persone
from timemachine.kb import turni as kb_turni
from timemachine.kb.paths import kb_root

from .conftest import SETTIMANA

MER = SETTIMANA + dt.timedelta(days=2)
SAB = SETTIMANA + dt.timedelta(days=5)


def _collega(anna, calendario_finto):
    return collega(
        anna,
        "anna-mondora",
        access_token="ya29.finto",
        refresh_token="1//refresh-finto",
        email="anna@example.com",
    )


def _ripubblica(piano):
    piano.stato = "pubblicato"
    kb_turni.scrivi(piano)
    return sync.dopo_pubblicazione(piano)


# --- C1 ----------------------------------------------------------------------


def test_c1_primo_sync_solo_i_suoi_spezzoni_futuri(anna, calendario_finto):
    esito = _collega(anna, calendario_finto)
    eventi = calendario_finto.eventi_di("anna-mondora")
    assert esito["creati"] == len(eventi) == 7  # lun, mer, gio + 2 sab + 2 dom

    giorni = {e.inizio.date() for e in eventi}
    assert SETTIMANA + dt.timedelta(days=4) not in giorni  # venerdì è `R`
    assert all("Le Rocce" in e.summary for e in eventi)
    assert calendario_finto.eventi_di("debora") == []
    assert kb_persone.leggi("anna-mondora").calendario["stato"] == "collegato"


def test_c1_bis_ferie_e_riposi_non_diventano_eventi():
    piano = kb_turni.leggi(SETTIMANA)
    turno_r = piano.turno("anna-mondora", SETTIMANA + dt.timedelta(days=4))
    assert turno_r.riposo
    assert sync.eventi_da_turno(turno_r, SETTIMANA) == []
    turno_f = piano.turno("armando", SETTIMANA)
    assert turno_f.ferie
    assert sync.eventi_da_turno(turno_f, SETTIMANA) == []


# --- C2 ----------------------------------------------------------------------


def test_c2_spezzato_due_eventi_chiavi_distinte(calendario_finto):
    from timemachine.security.authz import Attore

    cesare = Attore("cesare", ("dipendente",))
    collega(cesare, "cesare", access_token="t", refresh_token="r", email="cesare@example.com")
    lunedi = [e for e in calendario_finto.eventi_di("cesare") if e.inizio.date() == SETTIMANA]
    assert len(lunedi) == 2
    assert len({e.shift_key for e in lunedi}) == 2
    assert (lunedi[0].inizio.hour, lunedi[0].fine.hour) == (7, 12)
    assert (lunedi[1].inizio.hour, lunedi[1].fine.hour) == (16, 20)
    assert "Casse" in lunedi[0].summary and "Bar" in lunedi[1].summary


# --- C3 ----------------------------------------------------------------------


def test_c3_ripubblicare_sposta_senza_doppioni(anna, calendario_finto):
    _collega(anna, calendario_finto)
    prima = [e for e in calendario_finto.eventi_di("anna-mondora") if e.inizio.date() == MER]
    assert len(prima) == 1 and prima[0].inizio.hour == 12

    piano = kb_turni.leggi(SETTIMANA)
    piano.imposta(
        Turno(
            persona="anna-mondora",
            data=MER,
            spezzoni=(Spezzone(dt.time(7), dt.time(16), ("pizze",)),),
        )
    )
    _ripubblica(piano)

    dopo = [e for e in calendario_finto.eventi_di("anna-mondora") if e.inizio.date() == MER]
    assert len(dopo) == 1
    assert dopo[0].inizio.hour == 7 and dopo[0].fine.hour == 16


# --- C4 ----------------------------------------------------------------------


def test_c4_togliere_un_turno_cancella_solo_quello(anna, calendario_finto):
    _collega(anna, calendario_finto)
    assert [e for e in calendario_finto.eventi_di("anna-mondora") if e.inizio.date() == SAB]

    piano = kb_turni.leggi(SETTIMANA)
    piano.imposta(Turno(persona="anna-mondora", data=SAB, badge="R"))
    _ripubblica(piano)

    eventi = calendario_finto.eventi_di("anna-mondora")
    assert not [e for e in eventi if e.inizio.date() == SAB]
    assert [e for e in eventi if e.inizio.date() == MER]
    assert len(eventi) == 5


# --- C5 ----------------------------------------------------------------------


def test_c5_google_giu_la_pubblicazione_riesce_lo_stesso(anna, calendario_finto, manager):
    _collega(anna, calendario_finto)
    calendario_finto.guasto = 503

    piano = kb_turni.leggi(SETTIMANA)
    piano.imposta(Turno(persona="anna-mondora", data=MER, badge="R"))
    piano.stato = "pubblicato"
    kb_turni.scrivi(piano)  # il piano è scritto: la pubblicazione non dipende da Google
    jobs = sync.dopo_pubblicazione(piano)

    assert kb_turni.leggi(SETTIMANA).turno("anna-mondora", MER).riposo
    assert jobs and jobs[0].stato == "fallito"
    assert jobs[0].tentativi >= 2  # ha ritentato
    assert kb_persone.leggi("anna-mondora").calendario["stato"] == "in-errore"

    stato = sync.stato_widget("anna-mondora")
    assert stato["stato"] == "in-errore"
    assert "riprova" in stato["chip"]

    from timemachine import vista

    w = vista.person_shifts("anna-mondora", anna, oggi=SETTIMANA)
    assert w["ore_periodo"] > 0  # i turni nel widget restano


# --- C6 ----------------------------------------------------------------------


def test_c6_scollegare_pulisce_tutto_il_nostro(anna, calendario_finto):
    _collega(anna, calendario_finto)
    assert token_store.leggi("anna-mondora") is not None

    scollega(anna, "anna-mondora")

    assert calendario_finto.eventi_di("anna-mondora") == []
    assert calendario_finto.calendari == {}
    assert token_store.leggi("anna-mondora") is None
    assert "anna-mondora" in calendario_finto.revocati
    scheda = kb_persone.leggi("anna-mondora")
    assert scheda.calendario["stato"] == "scollegato"
    assert "email" not in scheda.calendario


# --- C7 ----------------------------------------------------------------------


def test_c7_una_bozza_non_tocca_il_calendario(anna, calendario_finto, manager):
    from timemachine.orchestrator import ciclo as orchestratore

    from .conftest import SETTIMANA_PROSSIMA

    _collega(anna, calendario_finto)
    calendario_finto.chiamate.clear()

    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    ciclo.genera_bozza(manager)
    ciclo.accetta(manager)  # accettata ma **non** pubblicata

    assert calendario_finto.chiamate == []


def test_c7_bis_sul_calendario_va_solo_il_pubblicato():
    piano = kb_turni.leggi(SETTIMANA)
    piano.stato = "bozza"
    with pytest.raises(ValueError):
        sync.dopo_pubblicazione(piano)


# --- C8 ----------------------------------------------------------------------


def test_c8_nessun_token_finisce_in_kb(anna, calendario_finto):
    _collega(anna, calendario_finto)
    sospetti = ("ya29.", "1//refresh", "refresh_token", "access_token", "Bearer ")
    for percorso in kb_root().rglob("*.md"):
        testo = percorso.read_text(encoding="utf-8")
        for s in sospetti:
            assert s not in testo, f"{s} trovato in {percorso}"
    # il token c'è, ma nello store cifrato fuori da kb/
    assert token_store.leggi("anna-mondora").refresh_token == "1//refresh-finto"
    assert not str(token_store._file()).startswith(str(kb_root()))
    assert b"1//refresh-finto" not in token_store._file().read_bytes()


# --- C9 ----------------------------------------------------------------------


def test_c9_scope_minimo():
    from timemachine.auth.oidc import SCOPE_IDENTITA
    from timemachine.calendario import url_consenso

    assert SCOPE == ("https://www.googleapis.com/auth/calendar.events",)
    url = url_consenso("anna-mondora", "https://tm/callback", "stato")
    assert "gmail" not in url
    assert "calendar.readonly" not in url
    assert "calendar.events" in url
    # identità e calendario sono due consensi distinti (`07` §4.5)
    assert "calendar" not in " ".join(SCOPE_IDENTITA)


# --- idempotenza -------------------------------------------------------------


def test_sync_e_idempotente(anna, calendario_finto):
    _collega(anna, calendario_finto)
    prima = len(calendario_finto.eventi_di("anna-mondora"))
    esito = sync.sincronizza("anna-mondora")
    assert esito["creati"] == 0 and esito["aggiornati"] == prima
    assert len(calendario_finto.eventi_di("anna-mondora")) == prima


def test_il_manager_non_collega_google_al_posto_di_anna(manager, calendario_finto):
    from timemachine.security.authz import Negato

    with pytest.raises(Negato):
        collega(manager, "anna-mondora", access_token="t")


def test_il_passato_non_si_tocca(anna, calendario_finto):
    _collega(anna, calendario_finto)
    eventi = calendario_finto.eventi_di("anna-mondora")
    assert all(e.inizio.date() >= SETTIMANA for e in eventi)
    # la settimana del 22/06 è in archivio: nessun evento
    assert not [e for e in eventi if e.inizio.date() < SETTIMANA]
