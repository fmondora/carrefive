"""La knowledge si legge senza perdere pezzi, e si riscrive senza rovinarla."""

from __future__ import annotations

import datetime as dt

from timemachine.domain.modelli import Preferenza
from timemachine.kb import persone as kb_persone
from timemachine.kb import saldi as kb_saldi
from timemachine.kb import secondo as kb_secondo
from timemachine.kb import turni as kb_turni
from timemachine.kb.celle import parse_cella

from .conftest import SETTIMANA


def test_cella_singolo_spezzone():
    spezzoni, badge, _ = parse_cella("6-14")
    assert badge is None
    assert len(spezzoni) == 1
    assert spezzoni[0].ore == 8


def test_cella_spezzata_con_mansioni_diverse():
    spezzoni, _, _ = parse_cella("7-12 C / 12-16 M")
    assert [s.mansioni for s in spezzoni] == [("casse",), ("macelleria",)]


def test_cella_badge_e_mezzore():
    assert parse_cella("R")[1] == "R"
    assert parse_cella("F")[1] == "F"
    assert parse_cella("No")[1] == "No"
    assert parse_cella("")[1] is None
    spezzoni, _, _ = parse_cella("8-11:30")
    assert spezzoni[0].ore == 3.5


def test_cella_etichetta_prima_dellorario():
    spezzoni, _, _ = parse_cella("Inventario 7-16")
    assert spezzoni[0].mansioni == ("inventario",)


def test_cella_token_sconosciuto_resta_nota_non_mansione():
    spezzoni, _, _ = parse_cella("12-20 SIST NEGOZIO")
    assert spezzoni[0].mansioni == ("sistemazione",)
    assert "NEGOZIO" in spezzoni[0].note


def test_piano_pubblicato_completo():
    piano = kb_turni.leggi(SETTIMANA)
    assert piano is not None
    assert len(piano.persone()) == 30
    assert piano.note_settimana[dt.date(2026, 7, 2)].startswith("SHOOTING")
    anna = piano.della_persona("anna-mondora")
    assert [t.etichetta() for t in anna][:3] == ["14–20", "No", "12–20"]
    assert sum(t.ore for t in anna) == 41


def test_mansioni_dalla_scheda():
    anna = kb_persone.leggi("anna-mondora")
    assert anna.ha_mansione("pizze")
    assert not anna.ha_mansione("macelleria")
    cesare = kb_persone.leggi("cesare")
    assert {"casse", "bar", "pizze"} <= set(cesare.nomi_mansioni())


def test_salva_preferenza_conserva_il_resto_della_scheda():
    prima = kb_persone.percorso("anna-mondora").read_text(encoding="utf-8")
    kb_persone.salva_preferenza(
        "anna-mondora",
        Preferenza(vincolo="no_pomeriggio: gio", storia="lezione di pianoforte", origine="confermata"),
    )
    dopo = kb_persone.percorso("anna-mondora").read_text(encoding="utf-8")
    assert "## Mansioni" in dopo and "PIZZE POME" in dopo
    assert "no_pomeriggio: gio" in dopo
    assert len(dopo) > len(prima) - 200
    persona = kb_persone.leggi("anna-mondora")
    assert any(p.vincolo == "no_pomeriggio: gio" for p in persona.preferenze)


def test_dimentica_storia_tiene_il_vincolo():
    kb_persone.salva_preferenza(
        "anna-mondora", Preferenza(vincolo="no_pomeriggio: gio", storia="pianoforte")
    )
    kb_persone.dimentica_storia("anna-mondora", "no_pomeriggio: gio")
    persona = kb_persone.leggi("anna-mondora")
    pref = [p for p in persona.preferenze if p.vincolo == "no_pomeriggio: gio"][0]
    assert pref.storia == ""
    assert "pianoforte" not in kb_persone.percorso("anna-mondora").read_text(encoding="utf-8")


def test_scrivere_un_segreto_in_scheda_e_un_errore():
    import pytest

    with pytest.raises(kb_persone.SegretoInKb):
        kb_persone.imposta_blocco(
            "anna-mondora", "calendario", {"refresh_token": "1//abcdefghijklmno"}
        )


def test_saldi_letti_dal_file():
    saldi = kb_saldi.leggi("anna-mondora")
    assert {s.tipo: s.residuo for s in saldi} == {"ferie": 96, "permessi": 24}
    assert saldi[0].fonte == "file"


def test_secondo_e_append_only_e_non_giudica():
    import pytest

    kb_secondo.append("sabati", "i sabati di dicembre vogliono due teste in più al bar")
    kb_secondo.append("sabati", "il lunedì di luglio basta una persona in cassa")
    assert len(kb_secondo.note()) == 2
    with pytest.raises(kb_secondo.NotaValutativa):
        kb_secondo.append("persone", "Anna è lenta in cassa")


def test_serializza_e_rilegge_un_piano():
    piano = kb_turni.leggi(SETTIMANA)
    assert piano is not None
    piano.settimana = dt.date(2026, 7, 6)
    for slug in list(piano.turni):
        piano.turni[slug] = {
            d + dt.timedelta(days=7): t for d, t in piano.turni[slug].items()
        }
    kb_turni.scrivi(piano)
    riletto = kb_turni.leggi(dt.date(2026, 7, 6))
    assert riletto is not None
    assert len(riletto.persone()) == len(piano.persone())
    assert sum(t.ore for t in riletto.della_persona("anna-mondora")) == 41
