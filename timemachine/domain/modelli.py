"""Modelli di dominio — turni, persone, saldi.

Zero AI qui dentro: sono i fatti. Le ore si calcolano in `domain.ore`.
Vocabolario condiviso fra kb (`01` §4.5), catalogo GenUI (`02`) e calendario (`03`).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Literal

# --- badge di cella (non sono turni lavorati) --------------------------------

RIPOSO = "R"
FERIE = "F"
ASSENTE = "No"

BADGE_NOTI = {RIPOSO, FERIE, ASSENTE}

GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]


@dataclass(frozen=True, slots=True)
class Spezzone:
    """Un pezzo continuo di turno. Uno spezzato = due spezzoni."""

    inizio: dt.time
    fine: dt.time
    mansioni: tuple[str, ...] = ()
    note: str = ""

    @property
    def ore(self) -> float:
        a = self.inizio.hour * 60 + self.inizio.minute
        b = self.fine.hour * 60 + self.fine.minute
        if b < a:  # turno oltre mezzanotte: non previsto nel pilota, ma non esplode
            b += 24 * 60
        return round((b - a) / 60, 2)

    def etichetta_orario(self) -> str:
        def f(t: dt.time) -> str:
            return f"{t.hour}:{t.minute:02d}" if t.minute else str(t.hour)

        return f"{f(self.inizio)}–{f(self.fine)}"

    def __str__(self) -> str:  # pragma: no cover - display
        return self.etichetta_orario()


@dataclass(frozen=True, slots=True)
class Turno:
    """La cella di una persona in un giorno."""

    persona: str  # slug kb
    data: dt.date
    spezzoni: tuple[Spezzone, ...] = ()
    badge: str | None = None  # R | F | No | BORMIO | ...
    note: str = ""
    grezzo: str = ""

    @property
    def ore(self) -> float:
        return round(sum(s.ore for s in self.spezzoni), 2)

    @property
    def lavorato(self) -> bool:
        return bool(self.spezzoni)

    @property
    def riposo(self) -> bool:
        return self.badge == RIPOSO

    @property
    def ferie(self) -> bool:
        return self.badge == FERIE

    @property
    def mansioni(self) -> tuple[str, ...]:
        out: list[str] = []
        for s in self.spezzoni:
            for m in s.mansioni:
                if m not in out:
                    out.append(m)
        return tuple(out)

    @property
    def giorno(self) -> str:
        return GIORNI[self.data.weekday()]

    def etichetta(self) -> str:
        if self.spezzoni:
            return " / ".join(s.etichetta_orario() for s in self.spezzoni)
        return self.badge or ""


@dataclass(slots=True)
class Piano:
    """Una settimana di un punto vendita. `kb/turni/YYYY-MM-DD.md` (lunedì)."""

    settimana: dt.date  # lunedì
    punto_vendita: str = ""
    stato: Literal["pubblicato", "bozza"] = "pubblicato"
    note_settimana: dict[dt.date, str] = field(default_factory=dict)
    turni: dict[str, dict[dt.date, Turno]] = field(default_factory=dict)
    fonte: str = ""

    @property
    def giorni(self) -> list[dt.date]:
        return [self.settimana + dt.timedelta(days=i) for i in range(7)]

    def persone(self) -> list[str]:
        return list(self.turni)

    def turno(self, persona: str, data: dt.date) -> Turno | None:
        return self.turni.get(persona, {}).get(data)

    def della_persona(self, persona: str) -> list[Turno]:
        return [t for _, t in sorted(self.turni.get(persona, {}).items())]

    def imposta(self, turno: Turno) -> None:
        self.turni.setdefault(turno.persona, {})[turno.data] = turno


# --- persone -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Mansione:
    """Vincolo di assegnazione. `esplicito` = scritto sul foglio."""

    nome: str  # slug: pizze, casse, bar, gastronomia...
    qualifica: str = ""  # "pomeriggio", ...
    origine: str = "esplicito"  # esplicito | inferito | confermato
    nota: str = ""


@dataclass(frozen=True, slots=True)
class Preferenza:
    """Vincolo morbido.

    `05` §4.2 regola della storia: il *vincolo* va al manager e al modello,
    la *storia* resta alla persona.
    """

    vincolo: str  # forma operativa: "no_pomeriggio: gio"
    storia: str = ""  # l'aneddoto: "lezione di pianoforte"
    origine: str = "dichiarata"  # dichiarata | confermata | da-confermare
    data: str = ""

    def operativa(self) -> str:
        return self.vincolo


@dataclass(slots=True)
class Persona:
    slug: str
    nome: str
    punto_vendita: str = ""
    contratto_ore_settimanali: float | None = None
    ore_giorno: float | None = None
    gruppo: str = ""
    email: str = ""
    ruoli: tuple[str, ...] = ()
    mansioni: list[Mansione] = field(default_factory=list)
    preferenze: list[Preferenza] = field(default_factory=list)
    account: dict[str, str] = field(default_factory=dict)
    calendario: dict[str, str] = field(default_factory=dict)
    note: str = ""
    minore: bool = False

    def ha_mansione(self, nome: str) -> bool:
        n = normalizza_mansione(nome)
        return any(m.nome == n for m in self.mansioni)

    def nomi_mansioni(self) -> list[str]:
        return [m.nome for m in self.mansioni]


# --- normalizzazione mansioni (abbreviazioni del tabellone) ------------------

ABBREVIAZIONI = {
    "c": "casse",
    "cassa": "casse",
    "casse": "casse",
    "b": "bar",
    "bar": "bar",
    "e": "enoteca",
    "eno": "enoteca",
    "enoteca": "enoteca",
    "g": "gastronomia",
    "gastro": "gastronomia",
    "gastronomia": "gastronomia",
    "m": "macelleria",
    "macel": "macelleria",
    "macelleria": "macelleria",
    "pizze": "pizze",
    "pizza": "pizze",
    "cucina": "cucina",
    "frutta": "frutta",
    "fru": "frutta",
    "frut": "frutta",
    "fresco": "fresco",
    "fresc": "fresco",
    "fres": "fresco",
    "pulizie": "pulizie",
    "puliz": "pulizie",
    "sist": "sistemazione",
    "sistemazione": "sistemazione",
    "apert": "apertura",
    "apertura": "apertura",
    "scat": "scatolame",
    "scatolame": "scatolame",
    "pane": "panetteria",
    "panetteria": "panetteria",
    "inventario": "inventario",
}

#: token che sul foglio qualificano la fascia, non la mansione
QUALIFICHE = {"pome", "pomeriggio", "matt", "mattina", "sera"}


def normalizza_mansione(testo: str) -> str:
    """Riporta un'etichetta umana al vocabolario delle mansioni.

    Se non è riconoscibile **non si inventa** una mansione nota: si tiene
    l'etichetta intera slugificata. Meglio una mansione che non matcha nulla
    che una persona messa in pizze perché la sua scheda diceva «primo turno».
    """
    t = re.sub(r"[^a-zà-ù0-9]+", " ", testo.lower()).strip()
    if not t:
        return ""
    if t in ABBREVIAZIONI:
        return ABBREVIAZIONI[t]
    for token in t.split():
        if len(token) > 1 and token in ABBREVIAZIONI:
            return ABBREVIAZIONI[token]
    return re.sub(r"\s+", "-", t)


def slug_persona(nome: str) -> str:
    t = nome.strip().lower()
    t = t.replace("à", "a").replace("è", "e").replace("é", "e").replace("ì", "i")
    t = t.replace("ò", "o").replace("ù", "u")
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t
