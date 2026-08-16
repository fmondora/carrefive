"""Grounding gate (P-I, `01` §4.2, `02` §4.4).

Ogni `persona` e ogni `mansione` che escono da un agente devono esistere in
`kb/`. Se non esistono, la riga si **scarta con motivo**: non si inventa un
nome, non si renderizza, non si persiste.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from ..kb import persone as kb_persone
from .modelli import Persona, normalizza_mansione
from .proposta import Scarto


@dataclass(slots=True)
class Gate:
    schede: dict[str, Persona]

    @classmethod
    def da_kb(cls) -> "Gate":
        return cls(schede=kb_persone.per_slug())

    # --- verifiche atomiche --------------------------------------------------

    def persona_esiste(self, slug: str) -> bool:
        return slug in self.schede

    def mansione_di(self, slug: str, mansione: str) -> bool:
        persona = self.schede.get(slug)
        if persona is None:
            return False
        return persona.ha_mansione(mansione)

    def fonte_valida(self, path: str) -> bool:
        return path.startswith("kb/") and not path.endswith("/")

    # --- gate su una cella di bozza -----------------------------------------

    def valida_cella(self, cella: dict) -> tuple[dict | None, Scarto | None]:
        """Una cella di `bozza-turni`: persona × giorno → fascia + mansione."""
        slug = str(cella.get("persona", "")).strip()
        if not self.persona_esiste(slug):
            return None, Scarto(cosa=slug or "(vuoto)", motivo="persona non in kb/persone")

        data = cella.get("data")
        try:
            giorno = dt.date.fromisoformat(str(data))
        except (TypeError, ValueError):
            return None, Scarto(cosa=f"{slug} {data}", motivo="data non valida")

        mansioni_ok: list[str] = []
        for m in cella.get("mansioni", []) or []:
            nome = normalizza_mansione(str(m))
            if not nome:
                continue
            if not self.mansione_di(slug, nome):
                return None, Scarto(
                    cosa=f"{slug} {giorno} {nome}",
                    motivo=f"{slug} non ha la mansione «{nome}» in scheda",
                )
            mansioni_ok.append(nome)

        pulita = dict(cella)
        pulita["persona"] = slug
        pulita["data"] = giorno.isoformat()
        pulita["mansioni"] = mansioni_ok
        return pulita, None

    def valida_celle(self, celle: list[dict]) -> tuple[list[dict], list[Scarto]]:
        tenute: list[dict] = []
        scarti: list[Scarto] = []
        for cella in celle:
            ok, scarto = self.valida_cella(cella)
            if ok is not None:
                tenute.append(ok)
            elif scarto is not None:
                scarti.append(scarto)
        return tenute, scarti

    def persone_con_mansione(self, mansione: str) -> list[str]:
        nome = normalizza_mansione(mansione)
        return sorted(s for s, p in self.schede.items() if p.ha_mansione(nome))
