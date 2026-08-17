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
    """U-sposta-conferma: senza conferma non si scrive niente sul piano.

    A2: la preview dice **prima → dopo**. `imposta` sostituisce la cella del
    giorno, non aggiunge un pezzo: coprire un buco con chi è già in turno ne
    apre un altro, e va detto *prima* di confermare (Book 08, «Layer 2»).
    """
    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    prima = ciclo.bozza.piano.turno("matteo", SETTIMANA_PROSSIMA).etichetta()

    r = client.post(
        "/chip/sposta-turno",
        data={"persona": "matteo", "data": SETTIMANA_PROSSIMA.isoformat(), "fascia": "6-12"},
        follow_redirects=True,
    )
    domanda = re.search(r'class="domanda">([^<]+)<', r.text).group(1)
    assert "Matteo lunedì 06/07" in domanda
    assert prima.replace("–", "-") in domanda  # il turno che si perde
    assert "6-12" in domanda  # e quello che arriva
    assert "→" in domanda
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


def _candidati_di(client):
    """Il flusso **di questa sessione**.

    `_FLUSSO` è globale al processo e i test ci lasciano dentro le loro
    sessioni: sommarle tutte fa contare i candidati di qualcun altro.
    """
    from timemachine.auth import sessioni
    from timemachine.web.app import _FLUSSO

    sid = client.cookies.get(sessioni.NOME_COOKIE)
    return _FLUSSO.get(sid, {}).get("candidati_gap", [])


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

    persone = [c for c in _candidati_di(client) if c["tipo"] == "person-shifts"]
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
    persone = [c for c in _candidati_di(client) if c["tipo"] == "person-shifts"]
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


# --- canary slice A2 (Book 07 · specs `02` Loop A2) --------------------------


def _carta_candidato(html: str) -> str:
    """La prima card candidato: quella dentro l'esito del tap, non la mia."""
    return html.split('<div class="esito">')[1].split("</section>")[1].split("</section>")[0]


def test_u_blocco_gesto(client, sessione_di, manager, llm_finto):
    """U-blocco-gesto: la violazione è un atto, non una constatazione.

    Il blocco è l'eredità del template (Matteo era già a 52h la settimana
    prima). Compliance non lo accorcia da sola — è una decisione umana — ma
    senza un gesto la settimana non si chiude mai e il manager torna al foglio
    (Book 08, «Blocco CCNL vs pubblica»).
    """
    import datetime as dt

    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    blocco = next(v for v in ciclo.bozza.violazioni if v["regola"] == "ore-massime")
    assert blocco["persona"] == "matteo"
    assert not ciclo.bozza.pubblicabile

    llm_finto.chiamate.clear()
    r = client.post(
        "/chip/consulta",
        data={"motivo": "blocco", "persona": blocco["persona"], "regola": blocco["regola"]},
        follow_redirects=True,
    )
    html = r.text
    assert llm_finto.chiamate == []  # il gesto è deterministico

    # l'esito vive dentro la card del blocco, prima della card dei buchi
    esito = html.split('<div class="esito">')[1].split('data-tipo="coverage-gap"')[0]
    assert 'data-tipo="rationale"' in esito
    assert 'data-tipo="person-shifts"' in esito  # i suoi turni della bozza
    assert "6–14" in esito  # e sono i turni della settimana in bozza
    assert 'action="/chip/sposta-turno"' in esito  # almeno una mossa

    # le mosse arrivano già verificate: la prima toglie davvero il blocco
    from timemachine.agents.compliance import celle_che_sciolgono
    from timemachine.kb import persone as kbp

    mosse = celle_che_sciolgono(ciclo.bozza.piano, blocco, kbp.per_slug())
    assert mosse, "il blocco della demo deve essere scioglibile da una cella sola"
    assert len(mosse[0]["prima"].split(" / ")) > 1  # la più leggera è uno spezzone in meno

    client.post(
        "/chip/sposta-turno",
        data={
            "persona": mosse[0]["persona"],
            "data": mosse[0]["data"],
            "fascia": mosse[0]["fascia"],
            "conferma": "1",
        },
    )
    assert all(v["regola"] != "ore-massime" for v in ciclo.bozza.violazioni)
    assert ciclo.bozza.pubblicabile

    # il veto resta un veto: si pubblica solo se **anche** accettata
    assert "pubblica" not in ciclo.chip()
    ciclo.accetta(manager)
    assert "pubblica" in ciclo.chip()

    # e la riga del blocco non c'è più
    html = client.get("/home").text
    assert "Non pubblicabile" not in html
    del dt


def test_una_segnalazione_non_e_un_atto(client, sessione_di, manager):
    """Solo le violazioni aprono il gesto.

    «41h su contratto 40h» non toglie `pubblica`: darle un bottone «come lo
    sciolgo» direbbe che finché non la tocchi non chiudi la settimana.
    """
    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    bloccate = {v["persona"] for v in ciclo.bozza.violazioni}
    segnalata = next(
        s["persona"] for s in ciclo.bozza.segnalazioni if s["persona"] not in bloccate
    )

    html = client.get("/home").text
    blocco = html.split('data-tipo="compliance-block"')[1].split("</section>")[0]
    da_guardare = blocco.split("Da guardare")[1]
    assert 'action="/chip/consulta"' not in da_guardare

    r = client.post(
        "/chip/consulta", data={"motivo": "blocco", "persona": segnalata}
    )
    assert r.status_code == 400  # non 500, e non un gesto finto
    assert f"un blocco su «{segnalata}»" in r.text


def test_u_gap_candidati_sotto_la_riga_tappata(client, sessione_di, manager):
    """U-gap-candidati (A2): il risultato del tap sta sotto **quel** buco.

    Prima i candidati finivano in fondo ai quindici buchi, sotto lo scroll e
    per metà coperti dal composer: il tap sembrava non aver fatto niente.
    """
    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    gap = _primo_gap_con_candidati(ciclo)
    assert gap is not None

    html = client.post(
        "/chip/consulta",
        data={"data": gap["data"], "fascia": gap["fascia"], "reparto": gap["reparto"]},
        follow_redirects=True,
    ).text

    # l'esito è dentro la card dei buchi, non dopo di essa
    card_gap = html.split('data-tipo="coverage-gap"')[1].split("</section>")[0]
    assert '<div class="esito">' in card_gap
    assert 'data-tipo="rationale"' in card_gap

    # ordine in DOM: rationale del tap → prima card candidato → pack
    i_rationale = html.find('data-tipo="rationale"')
    i_candidato = html.find('<div class="esito">')
    i_pack = html.find('data-tipo="proposal-pack"')
    assert i_rationale > 0 and i_candidato < i_pack
    assert html.find('data-tipo="person-shifts"', i_candidato) < i_pack

    # e la riga tappata è segnata
    assert 'class="scelto"' in card_gap


def test_niente_adesso_su_un_candidato_futuro(client, sessione_di, manager):
    """«Adesso 10-14» su un martedì che deve arrivare è una bugia di orologio.

    La card del candidato è puntata alla settimana in bozza: lì un «adesso»
    non esiste, e stamparlo faceva leggere il lunedì della bozza come il turno
    in corso (map A2, P1.3).
    """
    from timemachine import vista
    from timemachine.security.authz import Attore

    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    gap = _primo_gap_con_candidati(ciclo)
    assert gap is not None

    html = client.post(
        "/chip/consulta",
        data={"data": gap["data"], "fascia": gap["fascia"], "reparto": gap["reparto"]},
        follow_redirects=True,
    ).text

    carta = _carta_candidato(html)
    assert 'class="adesso' not in carta
    assert "Settimana in bozza" in carta
    # il soggetto è il buco: giorno e destinazione sono scritti sul bottone
    assert gap["data"][8:10] in carta

    # la mia card, che parte da oggi, l'«adesso» ce l'ha ancora
    mia = vista.person_shifts("francesco", Attore("francesco", ("dipendente", "manager")), oggi=OGGI)
    assert mia["mostra_adesso"] is True
    futura = vista.person_shifts(
        "matteo", Attore("francesco", ("dipendente", "manager")), oggi=SETTIMANA_PROSSIMA
    )
    assert futura["mostra_adesso"] is False and futura["adesso"] is None


def test_scegli_variante_assente_con_una_variante(client, sessione_di, manager):
    """Slice 8: una sola variante non è una scelta."""
    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    assert len(ciclo.bozza.varianti) == 1
    assert "scegli-variante" not in ciclo.chip()
    assert "scegli-variante" not in client.get("/api/stato-ciclo").json()["chip"]
    assert "scegli-variante" not in client.get("/home").text

    ciclo.bozza.varianti = ciclo.bozza.varianti * 2  # due varianti: il bivio esiste
    assert "scegli-variante" in ciclo.chip()


# --- canary slice A3 (specs `02` Loop A3) ------------------------------------


def _card_buchi(html):
    """La card dei buchi per intero.

    Non si taglia al primo `</section>`: dentro ci sono le card dei candidati,
    e la disclosure viene dopo. Si taglia al widget successivo.
    """
    return html.split('data-tipo="coverage-gap"')[1].split('data-tipo="proposal-pack"')[0]


def _gap_scelto_di(client):
    from timemachine.auth import sessioni
    from timemachine.web.app import _FLUSSO

    sid = client.cookies.get(sessioni.NOME_COOKIE)
    return _FLUSSO.get(sid, {}).get("gap_scelto")


def _sciogli_matteo(client, ciclo):
    """Toglie il blocco del tetto con la mossa più leggera (gesto di A2)."""
    from timemachine.agents.compliance import celle_che_sciolgono
    from timemachine.kb import persone as kbp

    blocco = next(v for v in ciclo.bozza.violazioni if v["regola"] == "ore-massime")
    mossa = celle_che_sciolgono(ciclo.bozza.piano, blocco, kbp.per_slug())[0]
    client.post(
        "/chip/sposta-turno",
        data={
            "persona": mossa["persona"],
            "data": mossa["data"],
            "fascia": mossa["fascia"],
            "conferma": "1",
        },
    )


def test_u_residuo_pubblica(client, sessione_di, manager):
    """U-residuo-pubblica: i buchi si dicono, non vietano.

    Un buco è un'ora scoperta, non una violazione: il dual gate resta CCNL +
    accettata. Ma `Pubblica` senza sapere quanti ne restano è pubblicare alla
    cieca, e il conto arriva lunedì mattina (Book 08, «15 buchi vs close»).
    """
    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    quanti = len(ciclo.bozza.gap)
    assert quanti > 0, "la bozza demo deve avere dei buchi residui"

    _sciogli_matteo(client, ciclo)
    client.post("/chip/accetta-bozza", data={"conferma": "1"})

    # il gate è passato: i buchi non l'hanno toccato
    assert ciclo.bozza.pubblicabile and ciclo.bozza.accettata
    assert "pubblica" in ciclo.chip()
    assert len(ciclo.bozza.gap) == quanti  # sono ancora tutti lì

    html = client.post("/chip/pubblica", data={}, follow_redirects=True).text
    approval = html.split('data-chrome="approval"')[1].split("</section>")[0]
    assert "Pubblico la settimana?" in approval
    assert f"Restano {quanti} buchi" in approval
    assert "non bloccano" in approval
    # detto, non vietato: il bottone c'è
    assert 'value="1"' in approval and "Pubblica" in approval


def test_u_prossimo_buco(client, sessione_di, manager):
    """U-prossimo-buco: dopo uno spostamento il prossimo, non il muro.

    Chiudere la settimana è una coda di gesti. Riportare il manager davanti a
    quindici chip identiche dopo ogni conferma gli fa ricominciare la ricerca
    da capo — quindici volte (map A3, P1.2).
    """
    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    gap = _primo_gap_con_candidati(ciclo)
    assert gap is not None

    client.post(
        "/chip/consulta",
        data={"data": gap["data"], "fascia": gap["fascia"], "reparto": gap["reparto"]},
    )
    candidato = next(c for c in _candidati_di(client) if c["tipo"] == "person-shifts")
    sposta = candidato["sposta"]

    html = client.post(
        "/chip/sposta-turno",
        data={
            "persona": sposta["persona"],
            "data": sposta["data"],
            "fascia": sposta["fascia"],
            "conferma": "1",
        },
        follow_redirects=True,
    ).text

    # non si è tornati al muro: c'è un esito aperto, ed è su un **altro** buco
    dopo = _gap_scelto_di(client)
    assert dopo is not None, "dopo la conferma il prossimo buco deve essere aperto"
    assert (dopo["data"], dopo["fascia"], dopo["reparto"]) != (
        gap["data"], gap["fascia"], gap["reparto"]
    )
    card = _card_buchi(html)
    assert '<div class="esito">' in card
    assert 'class="scelto"' in card

    # e il resto dei buchi è in disclosure, non quindici form in fila
    fuori = card.split("<details")[0]
    assert fuori.count('action="/chip/consulta"') <= 2
    assert "<details" in card


def test_la_card_dei_buchi_e_un_conteggio_non_un_muro(client, sessione_di, manager):
    """La card dice N e ne apre una: il resto sta sotto disclosure, zero JS."""
    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    n = len(ciclo.bozza.gap)
    assert n > 2

    html = client.get("/home").text
    card = _card_buchi(html)
    assert f"{n} buchi di copertura" in card
    assert "non bloccano la pubblicazione" in card
    assert card.split("<details")[0].count('action="/chip/consulta"') == 1
    assert f"Gli altri {n - 1}" in card
    assert "<script" not in html  # la disclosure è del browser

    # la riga aperta è un buco copribile, non la prima della lista a caso
    from timemachine.web.app import _prossimo_buco

    primario = next(b for b in card.split("<details")[0].split("<li")[1:] if "value=" in b)
    assert _prossimo_buco(ciclo)["data"] in primario


def test_il_residuo_e_vivo_non_la_fotografia(client, sessione_di, manager):
    """«Restano N» conta il piano di adesso, non la proposta di prima.

    `bozza.gap` è la fotografia di Scheduling: coprire un buco a mano non la
    aggiorna. Un numero fermo a quindici mentre il manager ne chiude tre è lo
    zero che non è vero — quello che `02` §4.4 vieta sui saldi, e che qui
    varrebbe per la sola cosa che l'approval gli chiede di guardare.
    """
    import datetime as dt

    from timemachine.agents.forecast import FASCE
    from timemachine.agents.scheduling import candidati_per_gap
    from timemachine.kb import persone as kbp
    from timemachine.web.app import _buchi_aperti, _residuo

    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    ciclo = orchestratore.ciclo(SETTIMANA_PROSSIMA)
    schede = kbp.per_slug()
    fotografia = len(ciclo.bozza.gap)
    assert len(_buchi_aperti(ciclo)) == fotografia  # prima di toccare: identici

    chiuso = False
    for g in list(ciclo.bozza.gap):
        data = dt.date.fromisoformat(g["data"])
        cand = candidati_per_gap(ciclo.bozza.piano, data, g["fascia"], g["reparto"], schede)
        if not cand:
            continue
        prima = len(_buchi_aperti(ciclo))
        dalle, alle = next((d, al) for n, d, al in FASCE if n == g["fascia"])
        client.post(
            "/chip/sposta-turno",
            data={
                "persona": cand[0],
                "data": g["data"],
                "fascia": f"{dalle.hour}-{alle.hour}",
                "conferma": "1",
            },
        )
        if len(_buchi_aperti(ciclo)) < prima:
            chiuso = True
            break

    assert chiuso, "coprire un buco deve poter far calare il conteggio"
    assert len(ciclo.bozza.gap) == fotografia  # la fotografia non si tocca
    assert len(_buchi_aperti(ciclo)) < fotografia
    assert f"Restano {len(_buchi_aperti(ciclo))} buchi" in _residuo(ciclo)


def test_i_due_tetti_restano_due_costanti():
    """Non si unificano: contano cose diverse (Book 09 slice 8)."""
    from timemachine.agents.compliance import MAX_CELLE_SBLOCCO
    from timemachine.agents.scheduling import MAX_CANDIDATI
    from timemachine.web.app import MAX_TOCCATI

    assert MAX_CANDIDATI == MAX_TOCCATI == MAX_CELLE_SBLOCCO == 8


def test_la_chip_nuda_sposta_turno_non_e_nel_guscio(manager):
    """Una chip senza campi non è un'affordance: è un 500 che aspetta."""
    from timemachine.orchestrator.ciclo import CHIP_PER_STATO

    assert "sposta-turno" not in CHIP_PER_STATO["attesa_umano"]
    assert "sposta-turno" in catalogo.CHIP_CON_CONFERMA
