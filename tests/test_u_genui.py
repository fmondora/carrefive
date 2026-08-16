"""Evals U1–U9 di `specs/02-genui.md` §6.

Il gate ricorrente: **la casa è la persona**. Il tabellone non è nel landing,
non lo sceglie il Copilot, e chiuderlo riporta ai propri turni.
"""

from __future__ import annotations

from timemachine.domain import catalogo
from timemachine.kb import persone as kb_persone
from timemachine.orchestrator import ciclo as orchestratore

from .conftest import OGGI, SETTIMANA_PROSSIMA


def test_u1_landing_di_anna_e_i_suoi_turni(client, sessione_di):
    sessione_di("anna-mondora")
    r = client.get("/home")
    assert r.status_code == 200
    html = r.text
    assert 'data-tipo="person-shifts"' in html
    assert 'data-tipo="person-balances"' in html
    assert "Anna Mondora" in html
    assert "14–20" in html  # lunedì 29/06
    assert "41h" in html
    assert "week-grid" not in html
    assert "<table" not in html


def test_u2_matteo_vede_la_sua_riga_non_le_trenta(client, sessione_di):
    sessione_di("matteo")
    html = client.get("/home").text
    assert "Matteo" in html
    assert "6–14" in html
    assert "week-grid" not in html
    for altro in ("Debora", "Cesare", "Jessica"):
        assert altro not in html


def test_u3_la_bozza_si_vede_come_persone_toccate(client, sessione_di, manager):
    sessione_di("francesco")
    r = client.post("/chip/genera-bozza", follow_redirects=True)
    assert r.status_code == 200
    html = r.text
    assert 'data-tipo="proposal-pack"' in html
    assert 'data-tipo="person-shifts"' in html
    assert 'data-tipo="week-grid"' not in html
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    assert ciclo.bozza is not None
    assert ciclo.stato == "attesa_umano"


def test_u4_compliance_blocca_e_pubblica_sparisce(client, sessione_di, manager):
    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    assert ciclo.bozza is not None and not ciclo.bozza.pubblicabile  # Matteo a 52h
    html = client.get("/home").text
    assert 'data-tipo="compliance-block"' in html or "Non pubblicabile" in html
    assert 'value="pubblica"' not in html
    assert ">pubblica<" not in html


def test_u5_preferenza_mostra_la_preview_e_non_scrive(client, sessione_di):
    sessione_di("anna-mondora")
    prima = kb_persone.percorso("anna-mondora").read_text(encoding="utf-8")
    r = client.post(
        "/copilota", data={"testo": "giovedì pomeriggio ho pianoforte"}, follow_redirects=True
    )
    html = r.text
    assert 'data-tipo="scheda-preview"' in html
    assert "no_pomeriggio: gio" in html
    assert 'data-tipo="person-shifts"' in html  # il widget persona resta a schermo
    assert kb_persone.percorso("anna-mondora").read_text(encoding="utf-8") == prima

    r = client.post(
        "/chip/salva-preferenza",
        data={
            "persona": "anna-mondora",
            "vincolo": "no_pomeriggio: gio",
            "storia": "lezione di pianoforte",
            "conferma": "1",
        },
        follow_redirects=True,
    )
    persona = kb_persone.leggi("anna-mondora")
    assert any(p.vincolo == "no_pomeriggio: gio" for p in persona.preferenze)


def test_u6_tipo_fuori_catalogo_si_droppa():
    tenuti, scartati = catalogo.filtra_widget(
        [{"tipo": "person-shifts"}, {"tipo": "foo-widget"}, {"tipo": None}]
    )
    assert [w["tipo"] for w in tenuti] == ["person-shifts"]
    assert "foo-widget" in scartati
    assert not catalogo.widget_valido("foo-widget")
    tenute, buttate = catalogo.filtra_chip(["pubblica", "cancella-tutto"])
    assert tenute == ["pubblica"] and buttate == ["cancella-tutto"]


def test_u6_bis_il_renderer_ignora_un_tipo_sconosciuto():
    from timemachine.web.app import template

    macro = template.get_template("widget.html").module
    assert macro.render({"tipo": "foo-widget"}).strip() == ""
    assert "person-shifts" in macro.render(
        {
            "tipo": "person-shifts",
            "persona": "anna-mondora",
            "nome": "Anna",
            "punto_vendita": "Le Rocce",
            "adesso": None,
            "prossimi": [],
            "ore_periodo": 0,
            "contratto_ore": 40,
            "overlay": "pubblicato",
            "diff": [],
            "calendario": None,
            "fonti": [],
        }
    )


def test_u7_ai_giu_il_pubblicato_resta_e_il_copilota_lo_dice(client, sessione_di, llm_finto):
    llm_finto.giu = True
    sessione_di("anna-mondora")
    r = client.post("/copilota", data={"testo": "chi copre giovedì?"}, follow_redirects=True)
    html = r.text
    assert 'data-tipo="person-shifts"' in html
    assert "14–20" in html
    assert "41h" in html
    # il copilota si spegne in modo onesto, non finge una risposta
    assert "Copilota non disponibile" in html or "non disponibile" in html


def test_u8_il_tabellone_si_apre_solo_con_la_chip_e_si_chiude(client, sessione_di, manager):
    sessione_di("francesco")
    assert 'data-tipo="week-grid"' not in client.get("/home").text

    r = client.post("/chip/apri-tabellone", follow_redirects=True)
    assert 'data-tipo="week-grid"' in r.text
    assert "Tabellone" in r.text

    assert 'data-tipo="week-grid"' not in client.get("/home").text


def test_u8_bis_il_tabellone_e_del_manager(client, sessione_di):
    sessione_di("anna-mondora")
    assert client.get("/tabellone").status_code == 403


def test_u9_genera_bozza_non_naviga_via_e_mostra_lo_stato_del_job(client, sessione_di, manager):
    sessione_di("francesco")
    r = client.post("/chip/genera-bozza", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/home"

    stato = client.get("/api/stato-ciclo").json()
    assert stato["stato"] == "attesa_umano"
    assert stato["job"]["nome"] == "genera-bozza"
    assert stato["job"]["stato"] == "fatto"
    assert "elapsed" in stato["job"]

    html = client.get("/home").text
    assert 'data-tipo="week-grid"' not in html
    assert 'data-tipo="person-shifts"' in html


def test_apri_scheda_e_una_vista_deterministica_della_md(client, sessione_di):
    """Chip `apri-scheda`: il file così com'è, senza una riga generata."""
    sessione_di("anna-mondora")
    html = client.post("/chip/apri-scheda", follow_redirects=True).text
    assert "kb/persone/anna-mondora.md" in html
    assert "PIZZE POME" in html
    assert 'class="card generata"' not in html


def test_la_storia_di_una_preferenza_non_si_vede_dalla_scheda_altrui(client, sessione_di, manager):
    from timemachine.domain.modelli import Preferenza

    kb_persone.salva_preferenza(
        "anna-mondora",
        Preferenza(vincolo="no_pomeriggio: gio", storia="lezione di pianoforte", origine="confermata"),
    )
    sessione_di("francesco")
    html = client.get("/scheda/anna-mondora").text
    assert "no_pomeriggio: gio" in html
    assert "pianoforte" not in html

    sessione_di("anna-mondora")
    assert "pianoforte" in client.get("/scheda/anna-mondora").text


def test_la_scheda_di_un_collega_e_403_per_un_dipendente(client, sessione_di):
    sessione_di("jessica")
    assert client.get("/scheda/anna-mondora").status_code == 403


def test_il_secondo_compare_solo_se_ha_qualcosa_da_dire(client, sessione_di):
    """`02` §4.5: retrieval del secondo, niente spam proattivo."""
    from timemachine.kb import secondo as kb_secondo

    sessione_di("anna-mondora")
    assert 'data-tipo="secondo-note"' not in client.get("/home").text

    kb_secondo.append(
        "sabati", "a giugno il banco pizze del sabato vuole due teste", quando="2026-06-01"
    )
    html = client.get("/home").text
    assert 'data-tipo="secondo-note"' in html
    assert "banco pizze del sabato" in html


def test_il_landing_anonimo_non_mostra_turni(client):
    html = client.get("/", follow_redirects=False).text
    assert "person-shifts" not in html
    assert "Anna" not in html


def test_person_shifts_include_riposi_e_ferie_come_turni_di_vita(client, sessione_di):
    from timemachine import vista
    from timemachine.security.authz import Attore

    w = vista.person_shifts("anna-mondora", Attore("anna-mondora"), oggi=OGGI)
    badge = [t["badge"] for t in w["prossimi"]]
    assert "R" in badge and "No" in badge
