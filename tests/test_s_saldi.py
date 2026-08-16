"""Evals S1–S9 di `specs/04-ferie-permessi-gamma.md` §6."""

from __future__ import annotations

import pytest

from timemachine import saldi as porta
from timemachine import vista
from timemachine.agents import copilot as agente_copilot
from timemachine.kb import saldi as kb_saldi
from timemachine.saldi.adapter_gamma import AdapterGamma, ErroreGamma
from timemachine.saldi.importer import importa
from timemachine.security.authz import Negato

CSV = """persona,tipo,maturato_ore,goduto_ore,prenotato_ore,residuo_ore
Anna Mondora,ferie,160,48,16,96
Anna Mondora,permessi,32,8,0,24
Debora,ferie,160,80,0,80
Sconosciuta Persona,ferie,10,0,0,10
Cesare,capriccio,10,0,0,10
"""


class GammaFinto:
    def __init__(self, risposte=None, esplode=False):
        self.risposte = risposte or []
        self.esplode = esplode
        self.chiamate = 0

    def residui(self, id_dipendente):
        self.chiamate += 1
        if self.esplode:
            raise ErroreGamma("503")
        return self.risposte


def _scrivi_csv(tmp_path):
    p = tmp_path / "export-studio.csv"
    p.write_text(CSV, encoding="utf-8")
    return p


# --- S1 / S2 -----------------------------------------------------------------


def test_s1_import_allinea_le_schede(tmp_path, anna):
    report = importa(_scrivi_csv(tmp_path), at="2026-08-16")
    assert set(report.importate) == {"anna-mondora", "debora"}

    saldi = kb_saldi.leggi("anna-mondora")
    assert {s.tipo: s.residuo for s in saldi} == {"ferie": 96, "permessi": 24}
    assert saldi[0].fonte == "file" and saldi[0].aggiornato_at == "2026-08-16"

    w = vista.person_balances("anna-mondora", anna)
    assert [(v["tipo"], v["residuo_ore"]) for v in w["voci"]] == [("ferie", 96), ("permessi", 24)]
    assert w["fonte"] == "file" and w["stale"] is False


def test_s2_riga_sconosciuta_finisce_nel_report_e_non_ferma_la_run(tmp_path):
    report = importa(_scrivi_csv(tmp_path), at="2026-08-16")
    motivi = " ".join(m for _, m in report.scartate)
    assert "persona non trovata" in motivi
    assert "tipo di saldo sconosciuto" in motivi
    assert "debora" in report.importate  # le altre passano
    assert not kb_saldi.percorso("sconosciuta-persona").exists()


# --- S3 ----------------------------------------------------------------------


def test_s3_senza_saldo_lo_stato_e_vuoto_non_zero(jessica):
    w = vista.person_balances("jessica", jessica)
    assert w["vuoto"] is True
    assert w["voci"] == []
    assert w["aggiornato_at"] is None
    assert "0" not in str(w["voci"])


# --- S4 ----------------------------------------------------------------------


def test_s4_jessica_non_legge_i_saldi_di_anna(jessica, client, sessione_di):
    with pytest.raises(Negato):
        vista.person_balances("anna-mondora", jessica)

    sessione_di("jessica")
    r = client.get("/api/saldi/anna-mondora")
    assert r.status_code == 403
    assert "96" not in r.text


def test_s4_bis_il_manager_vede_un_collega_solo_col_grant(manager):
    from timemachine.security.authz import REGISTRO

    with pytest.raises(Negato):
        vista.person_balances("anna-mondora", manager)

    grant = REGISTRO.concedi(manager.slug, "anna-mondora", "saldi")
    assert vista.person_balances("anna-mondora", manager)["voci"]

    REGISTRO.revoca(grant.id)  # chiuso l'overlay, il grant cade
    with pytest.raises(Negato):
        vista.person_balances("anna-mondora", manager)


# --- S5 / S6 -----------------------------------------------------------------


def test_s5_gamma_ok_mappa_e_materializza_lo_snapshot(anna):
    gamma = GammaFinto(
        [
            {"tipo": "ferie", "maturato_ore": 160, "goduto_ore": 40, "prenotato_ore": 0, "residuo_ore": 120,
             "aggiornato_at": "2026-08-16"},
            {"tipo": "sconosciuto", "residuo_ore": 5},
        ]
    )
    porta.imposta_porta(AdapterGamma(client=gamma, mappa={"anna-mondora": "A1"}))

    w = vista.person_balances("anna-mondora", anna)
    assert [(v["tipo"], v["residuo_ore"]) for v in w["voci"]] == [("ferie", 120)]
    assert w["fonte"] == "gamma" and w["stale"] is False
    assert "aggiorna-saldi" in w["chip"]
    # lo snapshot è in kb: è il fallback, non una seconda verità
    assert kb_saldi.leggi("anna-mondora")[0].residuo == 120


def test_s6_gamma_giu_mostra_lo_snapshot_marcato_stale(anna):
    kb_saldi.scrivi(
        "anna-mondora",
        [
            kb_saldi.Saldo(persona="anna-mondora", tipo="ferie", maturato=160, goduto=64,
                           residuo=96, aggiornato_at="2026-08-01", fonte="gamma"),
        ],
    )
    porta.imposta_porta(AdapterGamma(client=GammaFinto(esplode=True)))

    w = vista.person_balances("anna-mondora", anna)
    assert w["voci"][0]["residuo_ore"] == 96
    assert w["stale"] is True
    assert w["aggiornato_at"] == "2026-08-01"


def test_cache_corta_evita_un_pull_per_ogni_paint(anna):
    gamma = GammaFinto([{"tipo": "ferie", "residuo_ore": 10, "maturato_ore": 10, "goduto_ore": 0}])
    adattatore = AdapterGamma(client=gamma)
    porta.imposta_porta(adattatore)
    vista.person_balances("anna-mondora", anna)
    vista.person_balances("anna-mondora", anna)
    assert gamma.chiamate == 1
    adattatore.invalida("anna-mondora")  # chip `aggiorna-saldi`
    vista.person_balances("anna-mondora", anna)
    assert gamma.chiamate == 2


# --- S7 / S8 -----------------------------------------------------------------


def test_s7_copilot_senza_saldo_non_inventa_un_numero(jessica, contesto):
    risposta = agente_copilot.AGENTE.rispondi("quante ferie ho?", jessica, contesto)
    testo = risposta.turno["testo"]
    assert "non ho ancora un saldo" in testo.lower()
    assert not any(c.isdigit() for c in testo)


def test_s8_copilot_col_saldo_cita_il_numero_del_widget(anna, contesto):
    risposta = agente_copilot.AGENTE.rispondi("quante ferie ho?", anna, contesto)
    assert "96" in risposta.turno["testo"]
    assert "file" in risposta.turno["testo"]
    widget = [w for w in risposta.widget if w["tipo"] == "person-balances"][0]
    assert widget["voci"][0]["residuo_ore"] == 96  # stesso numero del widget


def test_copilot_non_da_i_saldi_di_un_altro(jessica, contesto):
    risposta = agente_copilot.AGENTE.rispondi("quante ferie ha Anna?", jessica, contesto)
    assert "96" not in risposta.turno["testo"]
    assert "Non posso mostrarti dati di un'altra persona" in risposta.turno["testo"]


# --- S9 ----------------------------------------------------------------------


def test_s9_ferie_oltre_il_residuo_si_segnalano_senza_bloccare(manager):
    import datetime as dt

    from timemachine.agents.compliance import Compliance
    from timemachine.agents.scheduling import Scheduling
    from timemachine.domain.modelli import Turno
    from timemachine.orchestrator import contesto as ctx

    kb_saldi.scrivi(
        "anna-mondora",
        [kb_saldi.Saldo(persona="anna-mondora", tipo="ferie", maturato=160, goduto=144,
                        residuo=16, aggiornato_at="2026-08-16", fonte="file")],
    )
    settimana = dt.date(2026, 7, 6)
    contesto = ctx.carica(settimana)
    piano, _, note, _ = Scheduling().costruisci(contesto)
    for i in range(5):
        piano.imposta(Turno(persona="anna-mondora", data=settimana + dt.timedelta(days=i), badge="F"))

    note += Scheduling()._nota_ferie(piano, __import__("timemachine.kb.persone", fromlist=["x"]).per_slug())
    testo = " ".join(note)
    assert "residuo 16h" in testo and "anna-mondora" in testo

    proposta = Compliance().verifica(piano)
    regole = {v["regola"] for v in proposta.payload["violazioni"]}
    assert "ferie-oltre-residuo" not in regole  # non è CCNL: non blocca


def test_la_porta_e_una_sola_la_ui_non_sa_quale_adapter_gira(anna):
    from timemachine.saldi import AdapterFile

    porta.imposta_porta(AdapterFile())
    a = vista.person_balances("anna-mondora", anna)
    porta.imposta_porta(
        AdapterGamma(
            client=GammaFinto([{"tipo": "ferie", "maturato_ore": 160, "goduto_ore": 64,
                                "prenotato_ore": 0, "residuo_ore": 96}])
        )
    )
    b = vista.person_balances("anna-mondora", anna)
    assert a["voci"][0]["residuo_ore"] == b["voci"][0]["residuo_ore"] == 96
    assert a["fonte"] == "file" and b["fonte"] == "gamma"
