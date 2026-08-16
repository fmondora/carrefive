"""Attivazione invite-only e login (`07`).

Nessuno si iscrive da solo. Emilio (ruolo `attivatore`) attiva una persona che
**esiste già** in `kb/persone/`; lei completa con uid/password **oppure** con
Google. Il token è a uso singolo, scade in 7 giorni, è legato a persona+email,
e nello store se ne tiene solo l'hash.

Messaggio unico su token invalido/scaduto/usato e su credenziali sbagliate:
nessun canale di enumerazione (L3, L9).
"""

from __future__ import annotations

import datetime as dt
import re
import secrets
import time
from dataclasses import dataclass, field

from ..kb import persone as kb_persone
from ..security import audit
from ..security.authz import Attore, esigi_attivatore
from . import password as pwd
from . import store
from .oidc import IdentitaGoogle, verificatore
from .sessioni import REGISTRO, Sessione

DURATA_INVITO_GIORNI = 7
BYTE_TOKEN = 32  # 256 bit ≥ 128 richiesti
MESSAGGIO_INVITO_NON_VALIDO = (
    "Questo link non è più valido. Chiedi un nuovo invito a Emilio."
)
MESSAGGIO_CREDENZIALI = "Uid o password non corretti."

_UID = re.compile(r"^[a-z0-9._-]{3,32}$")


class AttivazioneNegata(Exception):
    pass


class TroppiTentativi(Exception):
    pass


# --- rate limit / lockout ----------------------------------------------------


@dataclass(slots=True)
class Limitatore:
    finestra: float = 300.0
    massimo: int = 8
    tentativi: dict[str, list[float]] = field(default_factory=dict)

    def consenti(self, chiave: str) -> None:
        adesso = time.monotonic()
        recenti = [t for t in self.tentativi.get(chiave, []) if adesso - t < self.finestra]
        if len(recenti) >= self.massimo:
            self.tentativi[chiave] = recenti
            raise TroppiTentativi("troppi tentativi, riprova più tardi")
        recenti.append(adesso)
        self.tentativi[chiave] = recenti

    def azzera(self, chiave: str | None = None) -> None:
        if chiave is None:
            self.tentativi.clear()
        else:
            self.tentativi.pop(chiave, None)


LIMITATORE = Limitatore()


# --- Emilio attiva -----------------------------------------------------------


@dataclass(slots=True)
class Invitata:
    slug: str
    nome: str
    email: str
    stato: str


def non_ancora_entrate(attore: Attore) -> list[Invitata]:
    """Lista di Emilio: solo slug, nome e (se c'è) email. Niente saldi, niente preferenze."""
    esigi_attivatore(attore, "attivazione/lista")
    fuori: list[Invitata] = []
    for persona in kb_persone.tutte():
        a = store.account(persona.slug)
        if a and a.attiva:
            continue
        fuori.append(
            Invitata(
                slug=persona.slug,
                nome=persona.nome,
                email=(a.email if a else "") or persona.email,
                stato=a.stato if a else "non-invitata",
            )
        )
    return fuori


def _crea_token(persona: str, email: str, via: str) -> str:
    store.revoca_inviti(persona)  # un secondo `mostra-qr` ruota il token (`07` §4.2)
    token = secrets.token_urlsafe(BYTE_TOKEN)
    adesso = dt.datetime.now(dt.UTC)
    store.salva_invito(
        store.Invito(
            token_hash=store.impronta(token),
            persona=persona,
            email=(email or "").strip().lower(),
            via=via,
            creato_at=adesso.isoformat(),
            scade_at=(adesso + dt.timedelta(days=DURATA_INVITO_GIORNI)).isoformat(),
        )
    )
    conto = store.account(persona) or store.Account(persona=persona)
    conto.email = (email or conto.email or "").strip().lower()
    if conto.stato != "attiva":
        conto.stato = "invitata"
    store.salva_account(conto)
    kb_persone.imposta_blocco(
        persona,
        "account",
        {
            "stato": conto.stato,
            "email": conto.email or "—",
            "da": dt.date.today().isoformat(),
            "via": via,
        },
    )
    audit.decisione(proposta_id="-", esito=f"invito-{via}", da="attivatore", motivo=persona)
    return token


def invia_attivazione(attore: Attore, persona: str, email: str, base_url: str = "") -> dict:
    """Chip `invia-attivazione`. Il corpo della mail non contiene turni (`05`)."""
    esigi_attivatore(attore, "attivazione/invia")
    if not kb_persone.esiste(persona):
        raise AttivazioneNegata("questa persona non ha una scheda in kb/persone")
    token = _crea_token(persona, email, "email")
    link = f"{base_url.rstrip('/')}/attiva?t={token}"
    return {
        "persona": persona,
        "email": email,
        "link": link,
        "oggetto": "I tuoi turni — Le Rocce",
        "corpo": (
            "Ciao, Emilio ti ha attivata su TIME MACHINE.\n"
            f"Apri questo link per entrare: {link}\n"
            "Il link vale 7 giorni e funziona una volta sola."
        ),
    }


def mostra_qr(attore: Attore, persona: str, base_url: str = "", email: str = "") -> dict:
    """Chip `mostra-qr`. Stesso URL del link mail (L6)."""
    esigi_attivatore(attore, "attivazione/qr")
    if not kb_persone.esiste(persona):
        raise AttivazioneNegata("questa persona non ha una scheda in kb/persone")
    token = _crea_token(persona, email, "qr")
    link = f"{base_url.rstrip('/')}/attiva?t={token}"
    return {"persona": persona, "link": link, "qr_svg": qr_svg(link)}


def qr_svg(url: str) -> str:
    try:
        import io

        import segno

        buf = io.BytesIO()
        segno.make(url, error="m").save(
            buf, kind="svg", scale=4, dark="#1C1915", light=None, xmldecl=False
        )
        return buf.getvalue().decode("utf-8")
    except Exception:
        return ""  # senza QR resta il link: si degrada, non si finge


def revoca_invito(attore: Attore, persona: str) -> int:
    esigi_attivatore(attore, "attivazione/revoca")
    return store.revoca_inviti(persona)


# --- la persona completa -----------------------------------------------------


def apri_invito(token: str) -> store.Invito:
    LIMITATORE.consenti(f"attiva:{store.impronta(token)[:8]}")
    invito = store.invito(token or "")
    if invito is None or not invito.valido():
        raise AttivazioneNegata(MESSAGGIO_INVITO_NON_VALIDO)
    return invito


def nome_per_invito(token: str) -> str:
    persona = kb_persone.leggi(apri_invito(token).persona)
    return persona.nome if persona else ""


def _consuma(invito: store.Invito) -> None:
    invito.usato = True
    store.aggiorna_invito(invito)


def _attiva(persona: str, email: str, via: str) -> None:
    kb_persone.imposta_blocco(
        persona,
        "account",
        {
            "stato": "attiva",
            "email": email or "—",
            "da": dt.date.today().isoformat(),
            "via": via,
        },
    )


def crea_account_password(token: str, uid: str, password_chiara: str) -> Sessione:
    invito = apri_invito(token)
    uid = (uid or invito.email or "").strip().lower()
    if not _UID.match(uid) and "@" not in uid:
        raise AttivazioneNegata("uid non valido: 3–32 caratteri fra a-z 0-9 . _ -")
    esistente = store.per_uid(uid)
    if esistente and esistente.persona != invito.persona:
        raise AttivazioneNegata("uid già in uso")
    pwd.valida(password_chiara, email=invito.email, uid=uid)

    conto = store.account(invito.persona) or store.Account(persona=invito.persona)
    conto.uid = uid
    conto.email = invito.email or conto.email
    conto.password_hash = pwd.hash_password(password_chiara)
    conto.stato = "attiva"
    conto.creato_at = conto.creato_at or dt.datetime.now(dt.UTC).isoformat()
    store.salva_account(conto)
    _consuma(invito)
    _attiva(invito.persona, conto.email, invito.via)
    audit.accesso(invito.persona, "attivazione/password", "ok")
    return REGISTRO.apri(invito.persona)


def crea_account_google(token: str, code: str, redirect_uri: str = "") -> Sessione:
    invito = apri_invito(token)
    identita: IdentitaGoogle = verificatore().scambia(code, redirect_uri)
    email = (identita.email or "").lower()
    if invito.email and email != invito.email:
        # niente account orfano: questo Google non è quello su cui è stata attivata
        raise AttivazioneNegata(
            "Questo account Google non è quello su cui Emilio ti ha attivata."
        )
    altro = store.per_google_sub(identita.sub)
    if altro and altro.persona != invito.persona:
        raise AttivazioneNegata("questo Google è già legato a un'altra persona")

    conto = store.account(invito.persona) or store.Account(persona=invito.persona)
    conto.google_sub = identita.sub
    conto.email = email or conto.email
    conto.uid = conto.uid or conto.email
    conto.stato = "attiva"
    conto.creato_at = conto.creato_at or dt.datetime.now(dt.UTC).isoformat()
    store.salva_account(conto)
    _consuma(invito)
    _attiva(invito.persona, conto.email, invito.via)
    audit.accesso(invito.persona, "attivazione/google", "ok")
    return REGISTRO.apri(invito.persona)


# --- login -------------------------------------------------------------------


def login_password(uid: str, password_chiara: str, sessione_corrente: str | None = None) -> Sessione:
    LIMITATORE.consenti(f"login:{(uid or '').lower()}")
    conto = store.per_uid(uid)
    ok = pwd.verifica(password_chiara, conto.password_hash if conto else None)
    if not conto or not conto.attiva or not ok:
        audit.accesso(uid or "anonimo", "login", "403")
        raise AttivazioneNegata(MESSAGGIO_CREDENZIALI)
    conto.ultimo_login = dt.datetime.now(dt.UTC).isoformat()
    store.salva_account(conto)
    LIMITATORE.azzera(f"login:{(uid or '').lower()}")
    audit.accesso(conto.persona, "login", "ok")
    return REGISTRO.ruota(sessione_corrente, conto.persona)


def login_google(code: str, redirect_uri: str = "", sessione_corrente: str | None = None) -> Sessione:
    identita = verificatore().scambia(code, redirect_uri)
    conto = store.per_google_sub(identita.sub) or store.per_uid(identita.email)
    if not conto or not conto.attiva:
        audit.accesso(identita.email or "anonimo", "login-google", "403")
        raise AttivazioneNegata(MESSAGGIO_CREDENZIALI)
    if not conto.google_sub:
        conto.google_sub = identita.sub
    conto.ultimo_login = dt.datetime.now(dt.UTC).isoformat()
    store.salva_account(conto)
    audit.accesso(conto.persona, "login-google", "ok")
    return REGISTRO.ruota(sessione_corrente, conto.persona)


def imposta_password_dopo(persona: str, uid: str, password_chiara: str) -> None:
    """«Aggiungi una password» dalla scheda. Sempre lei, mai Emilio (`07` §4.3)."""
    conto = store.account(persona)
    if conto is None or not conto.attiva:
        raise AttivazioneNegata("account non attivo")
    pwd.valida(password_chiara, email=conto.email, uid=uid or conto.uid)
    conto.uid = (uid or conto.uid or conto.email).lower()
    conto.password_hash = pwd.hash_password(password_chiara)
    store.salva_account(conto)
