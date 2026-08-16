"""Evals U1–U9 di `specs/02-genui.md` §6.

Il gate ricorrente: **la casa è la persona**. Il tabellone non è nel landing,
non lo sceglie il Copilot, e chiuderlo riporta ai propri turni.
"""

from __future__ import annotations

import re

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
    """U8: la chip apre il foglio, chiuderlo riporta a casa.

    Si genera la bozza prima perché il tabellone punta alla settimana del
    ciclo: senza piano per quella settimana la vista dice «non c'è» invece di
    ripiegare su un'altra settimana (slice 5).
    """
    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    assert 'data-tipo="week-grid"' not in client.get("/home").text

    r = client.post("/chip/apri-tabellone", follow_redirects=True)
    assert 'data-tipo="week-grid"' in r.text
    assert "Tabellone" in r.text
    assert 'href="/home"' in r.text  # chiudi torna alla casa persona

    assert 'data-tipo="week-grid"' not in client.get("/home").text


def test_u_settimana_ciclo(client, sessione_di, manager):
    """U-settimana-ciclo: il foglio è quello che si sta pianificando."""
    sessione_di("francesco")
    client.post("/chip/genera-bozza")

    html = client.get("/tabellone").text
    assert SETTIMANA_PROSSIMA.isoformat() in html  # 06/07, non 29/06
    assert OGGI.isoformat() not in html.split("</h2>")[0]
    assert "bozza" in html  # è la griglia della bozza, ed è detto

    # `?settimana=` resta l'override esplicito
    html = client.get(f"/tabellone?settimana={OGGI.isoformat()}").text
    assert OGGI.isoformat() in html


def test_il_tabellone_non_ripiega_su_unaltra_settimana(client, sessione_di, manager):
    """Senza piano per la settimana del ciclo: card onesta, non il 29/06.

    Mostrare un'altra settimana sotto il titolo «Tabellone» è il modo più
    rapido per far pianificare sui dati sbagliati (Book 07).
    """
    sessione_di("francesco")  # ciclo idle: nessun piano per il 06/07
    html = client.get("/tabellone").text
    assert 'data-tipo="week-grid"' not in html
    assert "Nessun piano per la settimana" in html
    assert SETTIMANA_PROSSIMA.isoformat() in html


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


# --- canary slice A (Book 07) ------------------------------------------------


def test_u_composer_det(client, sessione_di, llm_finto):
    """U-composer-det: prosa fuori schema ≠ guasto — l'input resta acceso.

    Il modello **ha** risposto: si butta la prosa e si tengono i fatti. Spegnere
    il composer qui vorrebbe dire che dopo «giovedì ho pianoforte» non si può
    più scrivere niente (Book 08, riga «Composer spento»).
    """
    llm_finto.risposte = ["non è json", "nemmeno questo"]
    sessione_di("anna-mondora")
    r = client.post(
        "/copilota", data={"testo": "giovedì pomeriggio ho pianoforte"}, follow_redirects=True
    )
    html = r.text
    assert 'data-tipo="scheda-preview"' in html  # i fatti ci sono
    assert "no_pomeriggio: gio" in html
    assert "disabled" not in html.split('class="composer"')[1]
    assert "Copilota non disponibile" not in html


def test_u_composer_det_unita(anna, contesto, llm_finto):
    from timemachine.agents import copilot as agente_copilot

    llm_finto.risposte = ["non è json", "nemmeno questo"]
    risposta = agente_copilot.AGENTE.rispondi("giovedì ho pianoforte", anna, contesto)
    assert risposta.motivo == "schema"
    assert risposta.spento is False


def test_u_annulla(client, sessione_di, manager):
    """U-annulla: Annulla torna a `/home` e la domanda non ricompare."""
    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    client.post("/chip/accetta-bozza", data={})  # apre la conferma

    r = client.post("/chip/accetta-bozza", data={"conferma": "0"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/home"

    html = client.get("/home").text
    assert "Accetto questa bozza?" not in html


def test_approval_e_inline_sulla_home_non_unaltra_casa(client, sessione_di, manager):
    """Book 02: la conferma è chrome sulla home, non una destinazione."""
    sessione_di("francesco")
    client.post("/chip/genera-bozza")

    r = client.post("/chip/accetta-bozza", data={}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/home"

    html = client.get("/home").text
    assert 'data-chrome="approval"' in html
    assert "Accetto questa bozza?" in html
    assert 'data-tipo="person-shifts"' in html  # la casa persona resta sotto


def test_u_sposta_400(client, sessione_di, manager):
    """U-sposta-400: POST nudo non fa cadere il server — 400, e resta a casa."""
    sessione_di("francesco")
    client.post("/chip/genera-bozza")

    r = client.post("/chip/sposta-turno", data={})
    assert r.status_code == 400  # non 500
    assert "Manca il bersaglio" in r.text
    assert 'data-tipo="person-shifts"' in r.text  # è la home, non una pagina d'errore

    r = client.post(
        "/chip/sposta-turno", data={"persona": "matteo", "data": "boh", "fascia": "6-12"}
    )
    assert r.status_code == 400 and "non è una data valida" in r.text

    r = client.post(
        "/chip/sposta-turno",
        data={"persona": "matteo", "data": SETTIMANA_PROSSIMA.isoformat(), "fascia": "###"},
    )
    assert r.status_code == 400 and "non è una fascia" in r.text


def test_u_sposta_conferma(client, sessione_di, manager):
    """U-sposta-conferma: senza conferma non si scrive niente sul piano."""
    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    prima = ciclo.bozza.piano.turno("matteo", SETTIMANA_PROSSIMA).etichetta()

    r = client.post(
        "/chip/sposta-turno",
        data={"persona": "matteo", "data": SETTIMANA_PROSSIMA.isoformat(), "fascia": "6-12"},
        follow_redirects=True,
    )
    assert "Metto Matteo lunedì 06/07 in 6-12?" in r.text
    assert ciclo.bozza.piano.turno("matteo", SETTIMANA_PROSSIMA).etichetta() == prima


def test_u_sposta_ok(client, sessione_di, manager):
    """U-sposta-ok: con conferma il turno è sul piano e Compliance ricalcola."""
    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)

    client.post(
        "/chip/sposta-turno",
        data={
            "persona": "matteo",
            "data": SETTIMANA_PROSSIMA.isoformat(),
            "fascia": "6-12",
            "conferma": "1",
        },
    )
    assert ciclo.bozza.piano.turno("matteo", SETTIMANA_PROSSIMA).etichetta() == "6–12"
    assert ciclo.stato == "attesa_umano"
    # Compliance ha rigirato: 52h di Matteo non sono più il blocco di prima
    assert all(
        v["regola"] != "ore-massime" or v["persona"] != "matteo"
        for v in ciclo.bozza.violazioni
    ) or ciclo.bozza.violazioni


def _primo_gap_con_candidati(ciclo):
    from timemachine.agents.scheduling import candidati_per_gap
    from timemachine.kb import persone as kbp
    import datetime as dt

    schede = kbp.per_slug()
    for g in ciclo.bozza.gap:
        data = dt.date.fromisoformat(g["data"])
        if candidati_per_gap(ciclo.bozza.piano, data, g["fascia"], g["reparto"], schede):
            return g
    return None


def test_u_gap_candidati(client, sessione_di, manager, llm_finto):
    """U-gap-candidati: dal buco alle persone, senza LLM e senza riposi."""
    import datetime as dt

    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    gap = _primo_gap_con_candidati(ciclo)
    assert gap is not None, "la bozza demo deve avere almeno un buco copribile"

    llm_finto.chiamate.clear()
    r = client.post(
        "/chip/consulta",
        data={"data": gap["data"], "fascia": gap["fascia"], "reparto": gap["reparto"]},
        follow_redirects=True,
    )
    html = r.text
    assert llm_finto.chiamate == []  # zero LLM sul path del tap

    schede_card = html.count('data-tipo="person-shifts"')
    assert schede_card >= 2  # la mia + almeno un candidato
    assert 'data-tipo="rationale"' in html
    assert gap["reparto"] in html
    assert "sposta-turno" in html  # il bersaglio è già nel form

    # il form porta un **orario**, non il nome della fascia: «pomeriggio» sul
    # piano diventerebbe un badge da zero ore invece di un turno
    from timemachine.kb.celle import parse_cella

    fasce_form = re.findall(
        r'action="/chip/sposta-turno".*?name="fascia" value="([^"]+)"', html, re.S
    )
    assert fasce_form
    for f in fasce_form:
        spezzoni, _, _ = parse_cella(f)
        assert spezzoni and spezzoni[0].ore > 0, f"«{f}» non è un turno"

    # nessun candidato in riposo o ferie, e tetto rispettato
    from timemachine.agents.scheduling import MAX_CANDIDATI
    from timemachine.web.app import _FLUSSO

    candidati = [c for f in _FLUSSO.values() for c in f.get("candidati_gap", [])]
    persone = [c for c in candidati if c["tipo"] == "person-shifts"]
    assert 0 < len(persone) <= MAX_CANDIDATI
    data = dt.date.fromisoformat(gap["data"])
    for card in persone:
        turno = ciclo.bozza.piano.turno(card["persona"], data)
        assert turno is None or not (turno.riposo or turno.ferie)


def test_u_gap_vuoto(client, sessione_di, manager):
    """U-gap-vuoto: nessun candidato → testo onesto, non colleghi a caso."""
    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)

    r = client.post(
        "/chip/consulta",
        data={
            "data": SETTIMANA_PROSSIMA.isoformat(),
            "fascia": "mattina",
            "reparto": "macelleria",  # nessuno la copre libero quel giorno
        },
        follow_redirects=True,
    )
    from timemachine.web.app import _FLUSSO

    candidati = [c for f in _FLUSSO.values() for c in f.get("candidati_gap", [])]
    persone = [c for c in candidati if c["tipo"] == "person-shifts"]
    if not persone:
        assert "Nessuno con la mansione" in r.text
        assert "riposi e le ferie non entrano" in r.text


def test_u_gap_solo_manager(client, sessione_di):
    sessione_di("jessica")
    r = client.post(
        "/chip/consulta",
        data={"data": SETTIMANA_PROSSIMA.isoformat(), "fascia": "mattina", "reparto": "pizze"},
    )
    assert r.status_code == 403


def test_e_candidati_fn():
    """E-candidati-fn: la funzione è deterministica, non tocca la rete.

    Layer 1 vuoto **è** il caso normale dopo `genera-bozza` (Scheduling ha già
    assegnato chi poteva): senza layer 2 il gesto sarebbe morto (Book 08).
    """
    import datetime as dt

    from timemachine.agents.scheduling import _candidati, _movibili, candidati_per_gap
    from timemachine.kb import persone as kbp
    from timemachine.kb import turni as kbt

    piano = kbt.leggi(dt.date(2026, 6, 29))
    schede = kbp.per_slug()
    lunedi = dt.date(2026, 6, 29)

    tutti = candidati_per_gap(piano, lunedi, "pomeriggio", "pizze", schede)
    assert tutti == candidati_per_gap(piano, lunedi, "pomeriggio", "pizze", schede)  # stabile
    assert len(tutti) <= 8

    for slug in tutti:
        assert schede[slug].ha_mansione("pizze")
        turno = piano.turno(slug, lunedi)
        assert turno is None or not (turno.riposo or turno.ferie)

    # layer 2 non propone chi è già in quella fascia e reparto
    if not _candidati(piano, lunedi, "pizze", schede):
        assert set(tutti) <= set(_movibili(piano, lunedi, "pomeriggio", "pizze", schede))


def test_u_me_senza_overlay_altra_settimana(client, sessione_di, manager):
    """U-me-senza-overlay-altra-settimana: la mia settimana è la mia.

    Francesco pianifica il 06/07 ma vive il 29/06: il suo widget in cima alla
    home mostra il pubblicato, senza badge bozza. L'overlay vive nel pack e sui
    candidati, dove la bozza è il soggetto.
    """
    from timemachine.security.authz import Attore

    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    assert ciclo.bozza.settimana != OGGI  # settimane diverse: è il caso da coprire

    w = __import__("timemachine.vista", fromlist=["x"]).person_shifts(
        "francesco", Attore("francesco", ("dipendente", "manager")), oggi=OGGI, bozza=ciclo.bozza
    )
    assert w["overlay"] == "pubblicato"
    assert all(t["overlay"] != "bozza" for t in w["prossimi"])

    html = client.get("/home").text
    prima_card = html.split('data-tipo="person-shifts"')[1].split("</section>")[0]
    assert "proposta in bozza" not in prima_card


def test_la_chip_nuda_sposta_turno_non_e_nel_guscio(manager):
    """Una chip senza campi non è un'affordance: è un 500 che aspetta."""
    from timemachine.orchestrator.ciclo import CHIP_PER_STATO

    assert "sposta-turno" not in CHIP_PER_STATO["attesa_umano"]
    assert "sposta-turno" in catalogo.CHIP_CON_CONFERMA
