"""Google come **identità** (`07` §4.5) — non come calendario.

Scope: `openid email profile`. Mai `calendar.*`: quello è un secondo consenso
esplicito, in `03`. Un login Google non scrive un evento (L8).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlencode

SCOPE_IDENTITA = ("openid", "email", "profile")


@dataclass(frozen=True, slots=True)
class IdentitaGoogle:
    sub: str
    email: str
    nome: str = ""
    email_verificata: bool = True


class VerificatoreOIDC(Protocol):
    def scambia(self, code: str, redirect_uri: str) -> IdentitaGoogle: ...


@dataclass(slots=True)
class VerificatoreFinto:
    """Test e dev: mappa code → identità, senza rete."""

    identita: dict[str, IdentitaGoogle] = field(default_factory=dict)
    scope_richiesti: list[str] = field(default_factory=list)

    def scambia(self, code: str, redirect_uri: str) -> IdentitaGoogle:
        if code not in self.identita:
            raise PermissionError("code OIDC sconosciuto")
        return self.identita[code]


@dataclass(slots=True)
class VerificatoreGoogle:
    timeout: float = 10.0

    def scambia(self, code: str, redirect_uri: str) -> IdentitaGoogle:
        import httpx

        r = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=self.timeout,
        )
        r.raise_for_status()
        id_token = r.json().get("id_token", "")
        info = httpx.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
            timeout=self.timeout,
        )
        info.raise_for_status()
        d = info.json()
        return IdentitaGoogle(
            sub=d.get("sub", ""),
            email=(d.get("email") or "").lower(),
            nome=d.get("name", ""),
            email_verificata=str(d.get("email_verified", "true")).lower() == "true",
        )


_verificatore: VerificatoreOIDC | None = None


def verificatore() -> VerificatoreOIDC:
    global _verificatore
    if _verificatore is None:
        _verificatore = (
            VerificatoreGoogle() if os.environ.get("TM_OIDC") == "google" else VerificatoreFinto()
        )
    return _verificatore


def imposta_verificatore(v: VerificatoreOIDC | None) -> None:
    global _verificatore
    _verificatore = v


def url_login(redirect_uri: str, state: str) -> str:
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPE_IDENTITA),  # zero scope calendario
            "state": state,
        }
    )
