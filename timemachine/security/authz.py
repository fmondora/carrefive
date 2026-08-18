"""Chi può vedere cosa (`05` §4.3).

Regole dure:

- Ogni read ha un `caller_id`.
- Il dipendente vede **sé**: turni propri (+ overlay se toccato), scheda propria,
  saldi propri. Un fetch su un altro slug = 403 e log (G2 / S4).
- Il manager vede il piano del PV e la scheda *operativa*; i saldi di un collega
  **solo** con un grant effimero legato alla consulta / all'overlay (G3).
- `attivatore` è un ruolo a parte (`07`): vede la lista «non ancora entrate».
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field

from . import audit

RUOLI = ("dipendente", "manager", "attivatore")


class Negato(PermissionError):
    """403. Non si «aiuta» aggirando l'authz (UC-14)."""


@dataclass(frozen=True, slots=True)
class Attore:
    slug: str
    ruoli: tuple[str, ...] = ("dipendente",)

    @property
    def manager(self) -> bool:
        return "manager" in self.ruoli

    @property
    def attivatore(self) -> bool:
        return "attivatore" in self.ruoli

    def anonimo(self) -> bool:
        return not self.slug


ANONIMO = Attore(slug="", ruoli=())


@dataclass(slots=True)
class Grant:
    """Permesso **effimero**: dura la consulta / l'overlay, non è un ruolo."""

    id: str
    a: str  # slug del manager
    su: str  # slug della persona
    scopo: str  # "saldi" | "scheda"
    scade_at: dt.datetime

    def valido(self, adesso: dt.datetime | None = None) -> bool:
        return (adesso or dt.datetime.now(dt.UTC)) < self.scade_at


@dataclass(slots=True)
class RegistroGrant:
    durata_minuti: int = 30
    _grant: dict[str, Grant] = field(default_factory=dict)

    def concedi(self, a: str, su: str, scopo: str = "saldi") -> Grant:
        g = Grant(
            id=uuid.uuid4().hex[:12],
            a=a,
            su=su,
            scopo=scopo,
            scade_at=dt.datetime.now(dt.UTC) + dt.timedelta(minutes=self.durata_minuti),
        )
        self._grant[g.id] = g
        return g

    def revoca(self, grant_id: str) -> None:
        """Chiuso l'overlay, il grant cade (G3)."""
        self._grant.pop(grant_id, None)

    def attivo(self, a: str, su: str, scopo: str = "saldi") -> bool:
        for g in list(self._grant.values()):
            if not g.valido():
                self._grant.pop(g.id, None)
                continue
            if g.a == a and g.su == su and g.scopo == scopo:
                return True
        return False

    def svuota(self) -> None:
        self._grant.clear()


REGISTRO = RegistroGrant()


def _controlla(ok: bool, attore: Attore, risorsa: str) -> None:
    audit.accesso(attore.slug or "anonimo", risorsa, "ok" if ok else "403")
    if not ok:
        raise Negato(f"{attore.slug or 'anonimo'} non può accedere a {risorsa}")


def puo_vedere_saldi(attore: Attore, persona: str) -> bool:
    if attore.slug and attore.slug == persona:
        return True
    return attore.manager and REGISTRO.attivo(attore.slug, persona, "saldi")


def esigi_saldi(attore: Attore, persona: str) -> None:
    _controlla(puo_vedere_saldi(attore, persona), attore, f"saldi/{persona}")


def puo_vedere_turni(attore: Attore, persona: str) -> bool:
    if attore.anonimo():
        return False
    return attore.slug == persona or attore.manager


def esigi_turni(attore: Attore, persona: str) -> None:
    _controlla(puo_vedere_turni(attore, persona), attore, f"turni/{persona}")


def puo_vedere_scheda(attore: Attore, persona: str) -> bool:
    if attore.anonimo():
        return False
    return attore.slug == persona or attore.manager


def esigi_scheda(attore: Attore, persona: str) -> None:
    _controlla(puo_vedere_scheda(attore, persona), attore, f"persone/{persona}")


def puo_scrivere_scheda(attore: Attore, persona: str) -> bool:
    """La preferenza la conferma la persona. Il manager non parla per lei."""
    return bool(attore.slug) and attore.slug == persona


def esigi_scrittura_scheda(attore: Attore, persona: str) -> None:
    _controlla(puo_scrivere_scheda(attore, persona), attore, f"persone/{persona}:write")


def esigi_manager(attore: Attore, risorsa: str = "ciclo") -> None:
    _controlla(attore.manager, attore, risorsa)


def esigi_attivatore(attore: Attore, risorsa: str = "attivazione") -> None:
    _controlla(attore.attivatore, attore, risorsa)


def puo_collegare_calendario(attore: Attore, persona: str) -> bool:
    """Niente on-behalf: solo la persona, sul proprio account (`03` §4.2)."""
    return bool(attore.slug) and attore.slug == persona


def esigi_collegamento_calendario(attore: Attore, persona: str) -> None:
    _controlla(puo_collegare_calendario(attore, persona), attore, f"calendario/{persona}")
