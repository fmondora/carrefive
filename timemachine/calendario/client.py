"""Client Google Calendar (`03`).

Scope minimo: si scrive su un **calendario dedicato che creiamo noi**
(`Le Rocce — Turni`). Niente `calendar.readonly` globale, niente Gmail: la vita
privata della persona sul suo calendario non ci riguarda.

Il client vero e quello finto implementano lo stesso protocollo: gli eval C1–C7
girano senza rete.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Protocol

NOME_CALENDARIO = "Le Rocce — Turni"
SCOPE = ("https://www.googleapis.com/auth/calendar.events",)
SCOPE_IDENTITA = ("openid", "email", "profile")
SORGENTE = "timemachine"
FUSO = "Europe/Rome"


class ErroreGoogle(Exception):
    def __init__(self, messaggio: str, stato: int = 0) -> None:
        super().__init__(messaggio)
        self.stato = stato

    @property
    def ritentabile(self) -> bool:
        return self.stato in (429, 500, 502, 503, 504) or self.stato == 0


class ErroreAutorizzazione(ErroreGoogle):
    """401/403 persistente: token revocato lato Google → da ricollegare."""


@dataclass(slots=True)
class Evento:
    shift_key: str
    summary: str
    inizio: dt.datetime
    fine: dt.datetime
    location: str = "Le Rocce, Poggiridenti"
    description: str = ""
    id: str = ""

    def come_google(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "location": self.location,
            "description": self.description,
            "start": {"dateTime": self.inizio.isoformat(), "timeZone": FUSO},
            "end": {"dateTime": self.fine.isoformat(), "timeZone": FUSO},
            "transparency": "opaque",
            "attendees": [],
            "extendedProperties": {
                "private": {"shift_key": self.shift_key, "source": SORGENTE}
            },
        }


class ClientCalendario(Protocol):
    def assicura_calendario(self, persona: str) -> str: ...

    def elenca_nostri(self, calendario_id: str, da: dt.datetime) -> list[Evento]: ...

    def upsert(self, calendario_id: str, evento: Evento) -> Evento: ...

    def cancella(self, calendario_id: str, evento_id: str) -> None: ...

    def cancella_calendario(self, calendario_id: str) -> None: ...

    def revoca(self, persona: str) -> None: ...


@dataclass(slots=True)
class ClientFinto:
    """Dev e test. Tiene gli eventi in memoria, con le stesse regole."""

    calendari: dict[str, dict[str, Evento]] = field(default_factory=dict)
    per_persona: dict[str, str] = field(default_factory=dict)
    revocati: list[str] = field(default_factory=list)
    guasto: int = 0  # se >0, alza ErroreGoogle con quello stato
    chiamate: list[str] = field(default_factory=list)

    def _check(self) -> None:
        if self.guasto:
            raise ErroreGoogle(f"google finto in errore {self.guasto}", self.guasto)

    def assicura_calendario(self, persona: str) -> str:
        self._check()
        self.chiamate.append(f"assicura:{persona}")
        cid = self.per_persona.get(persona)
        if cid is None or cid not in self.calendari:
            cid = f"cal-{persona}"
            self.per_persona[persona] = cid
            self.calendari[cid] = {}
        return cid

    def elenca_nostri(self, calendario_id: str, da: dt.datetime) -> list[Evento]:
        self._check()
        self.chiamate.append(f"elenca:{calendario_id}")
        return [e for e in self.calendari.get(calendario_id, {}).values() if e.inizio >= da]

    def upsert(self, calendario_id: str, evento: Evento) -> Evento:
        self._check()
        self.chiamate.append(f"upsert:{evento.shift_key}")
        eventi = self.calendari.setdefault(calendario_id, {})
        precedente = eventi.get(evento.shift_key)
        evento.id = precedente.id if precedente else f"ev-{len(eventi) + 1}-{evento.shift_key}"
        eventi[evento.shift_key] = evento
        return evento

    def cancella(self, calendario_id: str, evento_id: str) -> None:
        self._check()
        self.chiamate.append(f"cancella:{evento_id}")
        eventi = self.calendari.get(calendario_id, {})
        for chiave, e in list(eventi.items()):
            if e.id == evento_id or chiave == evento_id:
                del eventi[chiave]
                return

    def cancella_calendario(self, calendario_id: str) -> None:
        self._check()
        self.chiamate.append(f"cancella-calendario:{calendario_id}")
        self.calendari.pop(calendario_id, None)
        for p, c in list(self.per_persona.items()):
            if c == calendario_id:
                del self.per_persona[p]

    def revoca(self, persona: str) -> None:
        self.chiamate.append(f"revoca:{persona}")
        self.revocati.append(persona)

    # aiuto per i test
    def eventi_di(self, persona: str) -> list[Evento]:
        cid = self.per_persona.get(persona)
        return sorted(self.calendari.get(cid, {}).values(), key=lambda e: e.inizio) if cid else []


@dataclass(slots=True)
class ClientHTTP:
    """Client reale. Il token si legge dallo store cifrato, non dal contesto LLM."""

    timeout: float = 10.0
    base: str = "https://www.googleapis.com/calendar/v3"

    def _token(self, persona: str) -> str:
        from . import store

        t = store.leggi(persona)
        if t is None:
            raise ErroreAutorizzazione("nessun token per questa persona", 401)
        return t.access_token

    def _chiama(self, metodo: str, url: str, persona: str, **kw) -> Any:
        import httpx

        try:
            r = httpx.request(
                metodo,
                url,
                headers={"Authorization": f"Bearer {self._token(persona)}"},
                timeout=self.timeout,
                **kw,
            )
        except Exception as e:
            raise ErroreGoogle(str(e), 0) from e
        if r.status_code in (401, 403):
            raise ErroreAutorizzazione(r.text[:200], r.status_code)
        if r.status_code >= 400:
            raise ErroreGoogle(r.text[:200], r.status_code)
        return r.json() if r.content else {}

    def assicura_calendario(self, persona: str) -> str:
        from . import store

        token = store.leggi(persona)
        if token and token.calendario_id:
            try:
                self._chiama("GET", f"{self.base}/calendars/{token.calendario_id}", persona)
                return token.calendario_id
            except ErroreGoogle:
                pass  # cancellato dall'utente: si ricrea al giro dopo
        dati = self._chiama(
            "POST", f"{self.base}/calendars", persona,
            json={"summary": NOME_CALENDARIO, "timeZone": FUSO},
        )
        cid = dati["id"]
        store.aggiorna_calendario(persona, cid)
        return cid

    def elenca_nostri(self, calendario_id: str, da: dt.datetime) -> list[Evento]:
        persona = _persona_da_calendario(calendario_id)
        dati = self._chiama(
            "GET", f"{self.base}/calendars/{calendario_id}/events", persona,
            params={
                "privateExtendedProperty": f"source={SORGENTE}",
                "timeMin": da.isoformat(),
                "maxResults": 2500,
                "singleEvents": "true",
            },
        )
        fuori = []
        for e in dati.get("items", []):
            priv = (e.get("extendedProperties") or {}).get("private") or {}
            fuori.append(
                Evento(
                    shift_key=priv.get("shift_key", ""),
                    summary=e.get("summary", ""),
                    inizio=dt.datetime.fromisoformat(e["start"]["dateTime"]),
                    fine=dt.datetime.fromisoformat(e["end"]["dateTime"]),
                    location=e.get("location", ""),
                    description=e.get("description", ""),
                    id=e.get("id", ""),
                )
            )
        return fuori

    def upsert(self, calendario_id: str, evento: Evento) -> Evento:
        persona = _persona_da_calendario(calendario_id)
        if evento.id:
            dati = self._chiama(
                "PUT", f"{self.base}/calendars/{calendario_id}/events/{evento.id}", persona,
                json=evento.come_google(),
            )
        else:
            dati = self._chiama(
                "POST", f"{self.base}/calendars/{calendario_id}/events", persona,
                json=evento.come_google(),
            )
        evento.id = dati.get("id", evento.id)
        return evento

    def cancella(self, calendario_id: str, evento_id: str) -> None:
        persona = _persona_da_calendario(calendario_id)
        self._chiama("DELETE", f"{self.base}/calendars/{calendario_id}/events/{evento_id}", persona)

    def cancella_calendario(self, calendario_id: str) -> None:
        persona = _persona_da_calendario(calendario_id)
        self._chiama("DELETE", f"{self.base}/calendars/{calendario_id}", persona)

    def revoca(self, persona: str) -> None:
        import httpx

        from . import store

        token = store.leggi(persona)
        if token is None:
            return
        try:
            httpx.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": token.refresh_token or token.access_token},
                timeout=self.timeout,
            )
        except Exception:
            pass  # la revoca lato nostro avviene comunque: si cancella il token


def _persona_da_calendario(calendario_id: str) -> str:
    from . import store

    for p in store.collegate():
        t = store.leggi(p)
        if t and t.calendario_id == calendario_id:
            return p
    raise ErroreAutorizzazione("calendario non associato a nessuna persona", 401)


_client: ClientCalendario | None = None


def client() -> ClientCalendario:
    global _client
    if _client is None:
        import os

        _client = ClientHTTP() if os.environ.get("TM_GOOGLE") == "http" else ClientFinto()
    return _client


def imposta_client(c: ClientCalendario | None) -> None:
    global _client
    _client = c
