"""Evals D1–D6 di `specs/06-design-system.md` §6.

Non è un test di gusto: sono le poche cose del design che si possono
verificare a macchina — token in un posto solo, contrasto, font, e il fatto
che il landing sia due card e non un tabellone.
"""

from __future__ import annotations

import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "timemachine" / "web" / "static"
TOKENS = (BASE / "tokens.css").read_text(encoding="utf-8")
APP = (BASE / "app.css").read_text(encoding="utf-8")


def _senza_commenti(css: str) -> str:
    """I commenti spiegano le scelte: si nominano anche i font che NON usiamo."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _hex(nome: str) -> str:
    m = re.search(rf"--{nome}:\s*(#[0-9a-fA-F]{{3,8}})", TOKENS)
    assert m, f"token --{nome} assente"
    return m.group(1)


def _luminanza(colore: str) -> float:
    colore = colore.lstrip("#")
    canali = [int(colore[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lineari = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canali]
    return 0.2126 * lineari[0] + 0.7152 * lineari[1] + 0.0722 * lineari[2]


def _contrasto(a: str, b: str) -> float:
    la, lb = sorted((_luminanza(a), _luminanza(b)))
    return (lb + 0.05) / (la + 0.05)


# --- D1 ----------------------------------------------------------------------


def test_d1_landing_di_anna_e_due_card_su_carta(client, sessione_di):
    sessione_di("anna-mondora")
    html = client.get("/home").text
    assert html.count('class="card') >= 2
    assert 'data-tipo="week-grid"' not in html
    assert "adesso" in html.lower()
    assert "/static/tokens.css" in html and "/static/app.css" in html
    assert _hex("carta").lower() == "#f6f1e8"


def test_d1_bis_lora_grande_e_in_fraunces():
    blocco = re.search(r"\.adesso\s*\{[^}]*\}", APP).group(0)
    assert "var(--font-display)" in blocco
    assert re.search(r"--font-display:\s*\"Fraunces\"", TOKENS)


# --- D2 ----------------------------------------------------------------------


def test_d2_overlay_bozza_e_albicocca_e_il_diff_e_a_righe(client, sessione_di, manager):
    sessione_di("francesco")
    html = client.post("/chip/genera-bozza", follow_redirects=True).text
    assert "card--bozza" in html
    assert 'data-tipo="diff-edit"' in html
    assert "<table" not in html  # il diff è una lista di turni, non una tabella 30×7
    assert "card--bozza" in APP and "--albicocca" in APP


# --- D3 ----------------------------------------------------------------------


def test_d3_salva_preferenza_e_una_approval_card(client, sessione_di):
    sessione_di("anna-mondora")
    html = client.post(
        "/copilota", data={"testo": "giovedì pomeriggio ho pianoforte"}, follow_redirects=True
    ).text
    assert 'data-tipo="scheda-preview"' in html
    assert "Salvo questa preferenza" in html
    assert "Conferma" in html and "Annulla" in html
    assert "alert(" not in html and "confirm(" not in html


# --- D4 ----------------------------------------------------------------------


def test_d4_il_job_mostra_il_tempo_trascorso(client, sessione_di, manager):
    from timemachine.orchestrator.jobs import Coda

    coda = Coda(sincrona=True)
    job = coda.accoda("prova", lambda: 1)
    assert job.come_dict()["elapsed"] >= 0
    assert "elapsed" in job.come_dict()

    sessione_di("francesco")
    client.post("/chip/genera-bozza")
    stato = client.get("/api/stato-ciclo").json()
    assert "elapsed" in stato["job"]
    assert ".job" in APP and "@keyframes pulsa" in APP


# --- D5 ----------------------------------------------------------------------


def test_d5_contrasto_wcag_aa():
    assert _contrasto(_hex("inchiostro"), _hex("carta")) >= 4.5
    assert _contrasto(_hex("inchiostro"), _hex("carta-alta")) >= 4.5
    assert _contrasto(_hex("inchiostro-muto"), _hex("carta")) >= 4.5
    assert _contrasto(_hex("foglia"), _hex("carta-alta")) >= 3.0
    assert _contrasto(_hex("rosso-blocco"), _hex("carta-alta")) >= 4.5


# --- D6 ----------------------------------------------------------------------


def test_d6_niente_font_da_template_ai():
    dichiarazioni = _senza_commenti(TOKENS)
    for vietato in ("Inter", "Space Grotesk", "system-ui", "-apple-system"):
        assert vietato not in dichiarazioni, vietato
    assert "Fraunces" in TOKENS and "Source Sans 3" in TOKENS and "IBM Plex Mono" in TOKENS


def test_d6_bis_niente_viola_gradient_ne_glassmorphism():
    testo = _senza_commenti(TOKENS + APP)
    assert "backdrop-filter" not in testo
    for viola in ("#6b46c1", "#7c3aed", "#8b5cf6", "purple", "indigo"):
        assert viola not in testo.lower()


# --- token in un posto solo --------------------------------------------------


def test_i_colori_vivono_solo_nel_file_dei_token():
    sorgenti = list((BASE.parent / "templates").glob("*.html")) + [BASE / "app.css"]
    for percorso in sorgenti:
        testo = percorso.read_text(encoding="utf-8")
        hex_sparsi = [
            h
            for h in re.findall(r"#[0-9a-fA-F]{6}\b", testo)
            if h.lower() not in ("#1c1915",)  # unico consentito: il dark del QR
        ]
        assert not hex_sparsi, f"{percorso.name}: {hex_sparsi}"


def test_accessibilita_di_base():
    assert "min-height: 44px" in APP  # chip ≥ 44px touch
    assert "prefers-reduced-motion" in TOKENS
    assert ":focus-visible" in APP


def test_mobile_first():
    assert "max-width: 720px" in APP
    assert "guscio--largo" in APP  # il manager può allargare, non il contrario
