"""Evals L1–L10 di `specs/07-landing-attivazione.md` §6.

Il tema: **nessuno si iscrive da solo**, e la landing non dà indizi su chi
esiste. Emilio attiva, la persona completa, il link muore dopo un uso.
"""

from __future__ import annotations

import datetime as dt
import re

import pytest

from timemachine.auth import attivazione, store
from timemachine.auth.attivazione import AttivazioneNegata
from timemachine.auth.oidc import IdentitaGoogle, VerificatoreFinto, imposta_verificatore
from timemachine.kb import persone as kb_persone
from timemachine.kb.paths import kb_root


def _token_da_link(link: str) -> str:
    return re.search(r"t=([A-Za-z0-9_-]+)", link).group(1)


def _invita(manager, persona="anna-mondora", email="anna@example.com"):
    esito = attivazione.invia_attivazione(manager, persona, email, "https://tm.example")
    return _token_da_link(esito["link"])


# --- L1 ----------------------------------------------------------------------


def test_l1_landing_anonima_non_dice_niente_di_nessuno(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.text
    assert "I tuoi turni" in html
    assert "Registrati" not in html
    for nome in ("Anna", "Matteo", "Debora", "Jessica"):
        assert nome not in html
    assert "14–20" not in html and "person-shifts" not in html


# --- L2 ----------------------------------------------------------------------


def test_l2_niente_account_senza_token(client):
    prima = len(store.tutti_account())
    r = client.post(
        "/attiva",
        data={"t": "", "uid": "furbo", "password": "unapasswordlunga", "password2": "unapasswordlunga"},
    )
    assert r.status_code >= 400
    assert len(store.tutti_account()) == prima

    r = client.post(
        "/attiva",
        data={"t": "inventato", "uid": "furbo", "password": "unapasswordlunga", "password2": "unapasswordlunga"},
    )
    assert r.status_code >= 400
    assert attivazione.MESSAGGIO_INVITO_NON_VALIDO in r.text
    assert len(store.tutti_account()) == prima


# --- L3 / L5 -----------------------------------------------------------------


def test_l3_token_scaduto_o_riusato_dice_sempre_la_stessa_cosa(client, manager):
    token = _invita(manager)
    invito = store.invito(token)
    invito.scade_at = (dt.datetime.now(dt.UTC) - dt.timedelta(days=1)).isoformat()
    store.aggiorna_invito(invito)

    r = client.get(f"/attiva?t={token}")
    assert attivazione.MESSAGGIO_INVITO_NON_VALIDO in r.text
    r2 = client.get("/attiva?t=mai-esistito")
    assert attivazione.MESSAGGIO_INVITO_NON_VALIDO in r2.text
    # messaggio unico: nessun canale di enumerazione
    assert ("scaduto" not in r.text.lower()) and ("già usato" not in r.text.lower())


def test_l5_lo_stesso_token_non_funziona_due_volte(client, manager):
    token = _invita(manager)
    r = client.post(
        "/attiva",
        data={"t": token, "uid": "anna@example.com", "password": "settelune2026", "password2": "settelune2026"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    conto = store.account("anna-mondora")
    assert conto.attiva

    r2 = client.post(
        "/attiva",
        data={"t": token, "uid": "altra", "password": "settelune2026", "password2": "settelune2026"},
    )
    assert r2.status_code >= 400
    assert store.account("anna-mondora").uid == "anna@example.com"  # il primo resta


# --- L4 ----------------------------------------------------------------------


def test_l4_emilio_invita_anna_e_anna_entra(client, manager):
    token = _invita(manager)
    r = client.get(f"/attiva?t={token}")
    assert "Ciao Anna Mondora" in r.text

    r = client.post(
        "/attiva",
        data={"t": token, "uid": "anna@example.com", "password": "settelune2026", "password2": "settelune2026"},
        follow_redirects=True,
    )
    assert "Anna Mondora" in r.text and 'data-tipo="person-shifts"' in r.text

    scheda = kb_persone.leggi("anna-mondora")
    assert scheda.account["stato"] == "attiva"
    conto = store.account("anna-mondora")
    assert conto.password_hash.startswith("$2")
    for percorso in kb_root().rglob("*.md"):
        assert "$2b$" not in percorso.read_text(encoding="utf-8")

    client.get("/logout")
    r = client.post(
        "/login", data={"uid": "anna@example.com", "password": "settelune2026"}, follow_redirects=True
    )
    assert 'data-tipo="person-shifts"' in r.text and "Anna Mondora" in r.text


# --- L6 ----------------------------------------------------------------------


def test_l6_il_qr_e_lo_stesso_url_del_link(manager):
    esito_qr = attivazione.mostra_qr(manager, "tiziana", "https://tm.example")
    assert esito_qr["link"].startswith("https://tm.example/attiva?t=")
    assert esito_qr["qr_svg"].startswith("<?xml") or "<svg" in esito_qr["qr_svg"]
    token = _token_da_link(esito_qr["link"])
    assert store.invito(token).via == "qr"

    # un secondo `mostra-qr` ruota il token: il vecchio muore
    nuovo = attivazione.mostra_qr(manager, "tiziana", "https://tm.example")
    assert not store.invito(token).valido()
    assert store.invito(_token_da_link(nuovo["link"])).valido()


# --- L7 ----------------------------------------------------------------------


def test_l7_google_con_email_diversa_non_crea_un_account(manager):
    token = _invita(manager, email="anna@example.com")
    imposta_verificatore(
        VerificatoreFinto({"code-x": IdentitaGoogle(sub="g-1", email="altra@gmail.com")})
    )
    with pytest.raises(AttivazioneNegata):
        attivazione.crea_account_google(token, "code-x")
    assert not (store.account("anna-mondora") or store.Account(persona="x")).attiva
    assert store.invito(token).valido()  # il token non è stato bruciato


def test_l7_bis_senza_email_in_scheda_il_primo_google_la_fissa(manager):
    esito = attivazione.mostra_qr(manager, "tiziana", "https://tm.example")
    token = _token_da_link(esito["link"])
    imposta_verificatore(
        VerificatoreFinto({"code-t": IdentitaGoogle(sub="g-t", email="tiziana@gmail.com")})
    )
    sessione = attivazione.crea_account_google(token, "code-t")
    assert sessione.persona == "tiziana"
    assert store.account("tiziana").email == "tiziana@gmail.com"
    assert kb_persone.leggi("tiziana").account["stato"] == "attiva"


# --- L8 ----------------------------------------------------------------------


def test_l8_login_google_non_tocca_il_calendario(client, manager, calendario_finto):
    token = _invita(manager, email="anna@example.com")
    imposta_verificatore(
        VerificatoreFinto({"code-a": IdentitaGoogle(sub="g-anna", email="anna@example.com")})
    )
    attivazione.crea_account_google(token, "code-a")
    assert calendario_finto.chiamate == []

    sessione = attivazione.login_google("code-a")
    assert sessione.persona == "anna-mondora"
    assert calendario_finto.chiamate == []
    from timemachine.calendario import store as token_store

    assert token_store.leggi("anna-mondora") is None  # identità ≠ calendario


# --- L9 ----------------------------------------------------------------------


def test_l9_credenziali_sbagliate_dicono_sempre_la_stessa_cosa(client, manager):
    token = _invita(manager)
    client.post(
        "/attiva",
        data={"t": token, "uid": "anna@example.com", "password": "settelune2026", "password2": "settelune2026"},
    )
    client.get("/logout")

    r_esiste = client.post("/login", data={"uid": "anna@example.com", "password": "sbagliata!!"})
    r_non_esiste = client.post("/login", data={"uid": "chi.non.esiste", "password": "sbagliata!!"})
    assert r_esiste.status_code == r_non_esiste.status_code == 401
    assert attivazione.MESSAGGIO_CREDENZIALI in r_esiste.text
    assert attivazione.MESSAGGIO_CREDENZIALI in r_non_esiste.text
    assert r_esiste.text == r_non_esiste.text


def test_l9_bis_rate_limit_sul_login(manager):
    for _ in range(attivazione.LIMITATORE.massimo):
        with pytest.raises(AttivazioneNegata):
            attivazione.login_password("anna@example.com", "sbagliata")
    with pytest.raises(attivazione.TroppiTentativi):
        attivazione.login_password("anna@example.com", "sbagliata")


# --- L10 ---------------------------------------------------------------------


def test_l10_jessica_non_e_attivatrice(client, sessione_di, jessica):
    from timemachine.security.authz import Negato

    with pytest.raises(Negato):
        attivazione.non_ancora_entrate(jessica)
    with pytest.raises(Negato):
        attivazione.invia_attivazione(jessica, "anna-mondora", "x@y.z")

    sessione_di("jessica")
    assert client.get("/attivatore").status_code == 403
    assert "invia-attivazione" not in client.get("/home").text


def test_l10_bis_emilio_vede_la_lista_senza_saldi_ne_preferenze(client, sessione_di, manager):
    sessione_di("francesco")
    html = client.get("/attivatore").text
    assert "Anna Mondora" in html
    assert "96" not in html and "pianoforte" not in html
    assert "invia attivazione" in html


# --- password dimenticata (`07` §4.4) ----------------------------------------


def test_password_dimenticata_non_crea_persone_e_non_rivela_nulla(client, manager):
    prima = len(store.tutti_account())

    r_ignoto = client.post("/password-dimenticata", data={"uid": "chi.non.esiste@x.it"})
    assert r_ignoto.status_code == 200
    assert len(store.tutti_account()) == prima  # non è un'attivazione: non crea persone

    token = _invita(manager)
    client.post(
        "/attiva",
        data={"t": token, "uid": "anna@example.com", "password": "settelune2026", "password2": "settelune2026"},
    )
    client.get("/logout")
    r_noto = client.post("/password-dimenticata", data={"uid": "anna@example.com"})
    assert r_noto.text == r_ignoto.text  # stessa pagina: nessun oracolo su chi esiste

    esito = attivazione.password_dimenticata("anna@example.com", "https://tm")
    nuovo = _token_da_link(esito["link"])
    client.post(
        "/attiva",
        data={"t": nuovo, "uid": "anna@example.com", "password": "altralunga2026", "password2": "altralunga2026"},
    )
    assert attivazione.login_password("anna@example.com", "altralunga2026").persona == "anna-mondora"
    assert store.account("anna-mondora").attiva


# --- CSRF sui callback OAuth (`05` §4.6) -------------------------------------


def test_il_callback_di_login_rifiuta_uno_state_non_nostro(client):
    """Login CSRF: un callback che nessuno ha iniziato non apre una sessione."""
    from timemachine.auth import sessioni
    from timemachine.auth.oidc import IdentitaGoogle, VerificatoreFinto, imposta_verificatore

    imposta_verificatore(
        VerificatoreFinto({"code-attaccante": IdentitaGoogle(sub="g-x", email="evil@gmail.com")})
    )
    r = client.get(
        "/login/google/callback?code=code-attaccante&state=inventato", follow_redirects=False
    )
    assert r.status_code == 400
    assert sessioni.NOME_COOKIE not in r.cookies
    assert not sessioni.REGISTRO.sessioni


def test_lo_state_e_opaco_a_uso_singolo_e_legato_allo_scopo(client):
    from timemachine.auth import stato_oauth

    r = client.get("/login/google", follow_redirects=False)
    state = re.search(r"state=([A-Za-z0-9_%-]+)", r.headers["location"]).group(1)
    assert state != "login" and len(state) >= 32  # niente valore parlante

    assert stato_oauth.REGISTRO.consuma(state, "login")
    with pytest.raises(stato_oauth.StatoNonValido):
        stato_oauth.REGISTRO.consuma(state, "login")  # replay: brucia una volta sola

    altro = stato_oauth.REGISTRO.crea("calendario", dati="anna-mondora")
    with pytest.raises(stato_oauth.StatoNonValido):
        stato_oauth.REGISTRO.consuma(altro, "login")  # scopo diverso


def test_il_token_di_invito_non_viaggia_nello_state(client, manager):
    from timemachine.auth import store as auth_store

    token = _invita(manager)
    r = client.get(f"/attiva/google?t={token}", follow_redirects=False)
    assert token not in r.headers["location"]

    # e un callback con uno state inventato non attiva nessuno
    r = client.get("/attiva/google/callback?code=x&state=inventato")
    assert r.status_code == 400
    assert not (auth_store.account("anna-mondora") or auth_store.Account(persona="x")).attiva


# --- extra: la mail non contiene turni --------------------------------------


def test_la_mail_di_invito_non_contiene_turni(manager):
    esito = attivazione.invia_attivazione(manager, "anna-mondora", "anna@example.com", "https://tm")
    assert esito["oggetto"] == "I tuoi turni — Le Rocce"
    assert "14-20" not in esito["corpo"] and "pizze" not in esito["corpo"].lower()


def test_il_token_ha_entropia_e_scadenza(manager):
    token = _invita(manager)
    assert len(token) >= 32  # 256 bit in base64url
    invito = store.invito(token)
    scadenza = dt.datetime.fromisoformat(invito.scade_at) - dt.datetime.fromisoformat(invito.creato_at)
    assert scadenza.days == attivazione.DURATA_INVITO_GIORNI
    # nello store c'è solo l'hash
    assert token not in (store._file().read_bytes().decode("latin-1"))


def test_password_debole_rifiutata():
    from timemachine.auth.password import PasswordDebole, valida

    for debole in ("corta", "LeRocce2026", "aaaaaaaaaaaa", "password123"):
        with pytest.raises(PasswordDebole):
            valida(debole, email="anna@example.com")
    valida("settelune2026", email="anna@example.com")
