"""Adapter `gamma` — TeamSystem, tempo reale (`04` §4.3).

Pull on read + cache corta. Ogni lettura riuscita materializza lo snapshot in
`kb/saldi/` — è il **fallback** quando Gamma è giù, non una seconda verità.
5xx / timeout → ultimo snapshot + `stale: true`. Mai un 200 con zeri inventati.

Il contratto HTTP esatto si chiude con lo studio (`04` §7 aperto): qui è
isolato in `ClientGamma`, che in test si sostituisce con un finto.
"""

from __future__ import annotations

import datetime as dt
import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..domain.saldi import TIPI_SALDO, Saldo
from ..kb import saldi as kb_saldi


class ErroreGamma(Exception):
    pass


class ClientGamma(Protocol):
    def residui(self, id_dipendente: str) -> list[dict[str, Any]]: ...


@dataclass(slots=True)
class ClientGammaHTTP:
    """Client reale. Credenziali **solo** come nome di env (`05` §4.5)."""

    base_url: str = field(default_factory=lambda: os.environ.get("GAMMA_BASE_URL", ""))
    env_token: str = "GAMMA_TOKEN"
    timeout: float = 5.0

    def residui(self, id_dipendente: str) -> list[dict[str, Any]]:
        import httpx  # import locale: il path file non deve dipendere dalla rete

        token = os.environ.get(self.env_token, "")
        if not self.base_url or not token:
            raise ErroreGamma("Gamma non configurato (base url o token assenti)")
        try:
            r = httpx.get(
                f"{self.base_url.rstrip('/')}/dipendenti/{id_dipendente}/residui",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
            r.raise_for_status()
            dati = r.json()
        except Exception as e:  # rete, 5xx, json rotto: tutto è «Gamma giù»
            raise ErroreGamma(str(e)) from e
        return dati.get("residui", dati if isinstance(dati, list) else [])


@dataclass(slots=True)
class AdapterGamma:
    client: ClientGamma
    mappa: dict[str, str] = field(default_factory=dict)  # slug -> id dipendente Gamma
    ttl: float = 30.0
    nome: str = "gamma"
    _cache: dict[str, tuple[float, list[Saldo]]] = field(default_factory=dict)
    _stale: set[str] = field(default_factory=set)

    def _id(self, persona: str) -> str:
        return self.mappa.get(persona, persona)

    def _mappa_voce(self, persona: str, voce: dict[str, Any]) -> Saldo | None:
        tipo = str(voce.get("tipo", "")).strip().lower()
        if tipo not in TIPI_SALDO:
            return None  # tipo sconosciuto: si scarta con log, non si inventa
        def num(chiave: str) -> float:
            try:
                return float(voce.get(chiave) or 0)
            except (TypeError, ValueError):
                return 0.0

        return Saldo(
            persona=persona,
            tipo=tipo,
            maturato=num("maturato_ore"),
            goduto=num("goduto_ore"),
            prenotato_fonte=num("prenotato_ore"),
            residuo=num("residuo_ore"),
            aggiornato_at=str(voce.get("aggiornato_at") or dt.date.today().isoformat()),
            fonte="gamma",
            fonte_ref=str(voce.get("id_movimento") or self._id(persona)),
        )

    def di(self, persona: str) -> list[Saldo]:
        adesso = time.monotonic()
        cache = self._cache.get(persona)
        if cache and adesso - cache[0] < self.ttl:
            return cache[1]
        try:
            grezzi = self.client.residui(self._id(persona))
        except Exception:
            self._stale.add(persona)
            return kb_saldi.leggi(persona)  # ultimo snapshot, senza cifre nuove
        saldi = [s for s in (self._mappa_voce(persona, v) for v in grezzi) if s is not None]
        if not saldi:
            self._stale.add(persona)
            return kb_saldi.leggi(persona)
        self._stale.discard(persona)
        self._cache[persona] = (adesso, saldi)
        kb_saldi.scrivi(persona, saldi)
        return saldi

    def aggiornati_at(self, persona: str) -> str | None:
        saldi = self.di(persona)
        return saldi[0].aggiornato_at if saldi else None

    def stale(self, persona: str) -> bool:
        return persona in self._stale

    def invalida(self, persona: str | None = None) -> None:
        """Chip `aggiorna-saldi`: forza il pull al prossimo read."""
        if persona is None:
            self._cache.clear()
        else:
            self._cache.pop(persona, None)

    def precarica(self, persone: list[str]) -> None:
        """Job periodico: il landing non aspetta Gamma (`04` §4.3 punto 5)."""
        for p in persone:
            try:
                self.di(p)
            except Exception:
                continue
