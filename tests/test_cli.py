"""La CLI `tm`: gli atti deterministici, quelli che non passano da un modello."""

from __future__ import annotations

import json

from timemachine.cli import main
from timemachine.kb import persone as kb_persone
from timemachine.kb import saldi as kb_saldi

CSV = """persona,tipo,maturato_ore,goduto_ore,prenotato_ore,residuo_ore
Debora,ferie,160,80,0,80
"""


def test_import_saldi(tmp_path, capsys):
    f = tmp_path / "studio.csv"
    f.write_text(CSV, encoding="utf-8")
    assert main(["import-saldi", "--file", str(f), "--at", "2026-08-16"]) == 0
    assert kb_saldi.leggi("debora")[0].residuo == 80
    assert "importate: 1" in capsys.readouterr().out


def test_ruolo_e_invito(capsys):
    assert main(["ruolo", "francesco", "--aggiungi", "manager", "attivatore"]) == 0
    assert set(kb_persone.leggi("francesco").ruoli) == {"manager", "attivatore"}

    assert main(["invita", "anna-mondora", "--da", "francesco", "--email", "anna@example.com"]) == 0
    out = capsys.readouterr().out
    assert "I tuoi turni — Le Rocce" in out
    assert "/attiva?t=" in out
    assert "14-20" not in out  # nessun turno nella mail


def test_invito_qr_salva_lo_svg(tmp_path, capsys):
    main(["ruolo", "francesco", "--aggiungi", "attivatore"])
    svg = tmp_path / "tiziana.svg"
    assert main(["invita", "tiziana", "--da", "francesco", "--qr", "--svg", str(svg)]) == 0
    assert "<svg" in svg.read_text(encoding="utf-8")


def test_bozza_headless_non_pubblica(capsys):
    import datetime as dt

    from timemachine.kb import turni as kb_turni

    main(["ruolo", "francesco", "--aggiungi", "manager"])
    assert main(["bozza", "--settimana", "2026-07-06", "--da", "francesco"]) == 0
    out = capsys.readouterr().out
    assert "pubblicabile:" in out
    assert kb_turni.leggi(dt.date(2026, 7, 6)) is None  # la pubblicazione è umana


def test_scan_registra_i_finding(capsys):
    assert main(["scan"]) == 0
    riepilogo = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert set(riepilogo) == {"nuovi", "aperti", "risolti"}


def test_gdpr_export_e_cancella(capsys):
    assert main(["gdpr", "export", "anna-mondora"]) == 0
    percorso = capsys.readouterr().out.strip()
    dati = json.loads(open(percorso, encoding="utf-8").read())
    assert dati["persona"] == "anna-mondora" and dati["turni_pubblicati"]

    assert main(["gdpr", "cancella", "anna-mondora"]) == 0
    esito = json.loads(capsys.readouterr().out)
    assert esito["turni_storici"].startswith("conservati")
    assert kb_saldi.leggi("anna-mondora") == []


def test_purga_log(capsys):
    assert main(["purga-log"]) == 0
    assert "purgati" in capsys.readouterr().out
