"""Schede persona — lettura e scrittura di `kb/persone/{slug}.md`.

La scheda è markdown leggibile da un umano: la scrittura **conserva** il file
e tocca solo la sezione interessata (`01` §4.5). Niente token, niente hash,
niente segreti qui dentro (`05` §4.5).
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from ..domain.modelli import Mansione, Persona, Preferenza, normalizza_mansione
from . import paths

_META = re.compile(r"^-\s*([a-z_]+)\s*:\s*(.+?)\s*$", re.I)
_VOCE = re.compile(r"^-\s*\*\*(?P<titolo>[^*]+)\*\*\s*(?P<resto>.*)$")
_ORIGINE = re.compile(r"_([^_]+)_")
_STORIA = re.compile(r"«([^»]*)»")
_PLACEHOLDER = "Nessuna ancora"

SEGRETI_VIETATI = re.compile(
    r"(refresh_token|access_token|client_secret|bearer\s+[A-Za-z0-9._-]{10,}|AIza[0-9A-Za-z_-]{10,}|"
    r"ya29\.[0-9A-Za-z_-]{10,}|\$2[aby]\$\d{2}\$)",
    re.I,
)


# --- lettura -----------------------------------------------------------------


def _sezioni(testo: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"": []}
    corrente = ""
    for riga in testo.splitlines():
        if riga.startswith("## "):
            corrente = riga[3:].strip().lower()
            out.setdefault(corrente, [])
        else:
            out[corrente].append(riga)
    return out


def _parse_mansioni(righe: list[str]) -> list[Mansione]:
    fuori: list[Mansione] = []
    for riga in righe:
        m = _VOCE.match(riga.strip())
        if not m:
            continue
        titolo = m.group("titolo").strip()
        resto = m.group("resto")
        origine_m = _ORIGINE.search(resto)
        origine = origine_m.group(1).strip() if origine_m else "esplicito"
        nota = resto.split("—")[-1].strip() if "—" in resto else ""
        qualifica = ""
        q = re.search(r"\(([^)]+)\)", titolo)
        if q:
            qualifica = q.group(1).strip()
            titolo = titolo[: q.start()].strip()
        for pezzo in re.split(r"\s*[/,]\s*|\s+e\s+(?=pizze|casse|bar)", titolo):
            nome = normalizza_mansione(pezzo)
            if not nome:
                continue
            if any(x.nome == nome for x in fuori):
                continue
            fuori.append(Mansione(nome=nome, qualifica=qualifica, origine=origine, nota=nota))
    return fuori


def _parse_preferenze(righe: list[str]) -> list[Preferenza]:
    fuori: list[Preferenza] = []
    for riga in righe:
        testo = riga.strip()
        if not testo.startswith("-") or _PLACEHOLDER.lower() in testo.lower():
            continue
        m = _VOCE.match(testo)
        if not m:
            continue
        vincolo = m.group("titolo").strip()
        resto = m.group("resto")
        origine_m = _ORIGINE.search(resto)
        origine = origine_m.group(1).strip() if origine_m else "dichiarata"
        storia_m = _STORIA.search(resto)
        storia = storia_m.group(1).strip() if storia_m else ""
        data = ""
        d = re.search(r"(\d{4}-\d{2}-\d{2})", origine)
        if d:
            data = d.group(1)
            origine = re.sub(r"\bsolo\b", "", origine.replace(data, "")).strip()
        fuori.append(
            Preferenza(vincolo=vincolo, storia=storia, origine=origine or "dichiarata", data=data)
        )
    return fuori


def _parse_blocco(testo: str, nome: str) -> dict[str, str]:
    """Blocco `nome:` seguito da righe indentate `chiave: valore`."""
    m = re.search(rf"^{nome}:\s*$", testo, re.M)
    if not m:
        return {}
    out: dict[str, str] = {}
    for riga in testo[m.end() :].splitlines()[1:]:
        if not riga.strip():
            break
        v = re.match(r"^\s+([a-z_]+)\s*:\s*(.*)$", riga)
        if not v:
            break
        out[v.group(1)] = v.group(2).strip()
    return out


def parse(testo: str, slug: str) -> Persona:
    sez = _sezioni(testo)
    titolo = ""
    for riga in testo.splitlines():
        if riga.startswith("# "):
            titolo = riga[2:].strip()
            break
    meta: dict[str, str] = {}
    for riga in sez.get("", []):
        m = _META.match(riga.strip())
        if m:
            meta[m.group(1).lower()] = m.group(2).strip()

    def numero(chiave: str) -> float | None:
        v = meta.get(chiave)
        if not v:
            return None
        n = re.search(r"[\d.,]+", v)
        return float(n.group(0).replace(",", ".")) if n else None

    ruoli = tuple(
        r.strip().lower() for r in re.split(r"[,;]", meta.get("ruoli", "")) if r.strip()
    )
    account = _parse_blocco(testo, "account")
    calendario = _parse_blocco(testo, "calendario")
    return Persona(
        slug=slug,
        nome=titolo or slug,
        punto_vendita=meta.get("punto_vendita", ""),
        contratto_ore_settimanali=numero("contratto_ore_settimanali"),
        ore_giorno=numero("ore_giorno"),
        gruppo=meta.get("gruppo_tabellone", ""),
        email=account.get("email", meta.get("email", "")),
        ruoli=ruoli,
        mansioni=_parse_mansioni(sez.get("mansioni", [])),
        preferenze=_parse_preferenze(sez.get("preferenze", [])),
        account=account,
        calendario=calendario,
        minore=meta.get("minore", "").lower() in {"si", "sì", "true", "yes"},
    )


def percorso(slug: str) -> Path:
    return paths.dir_persone() / f"{slug}.md"


def leggi(slug: str) -> Persona | None:
    p = percorso(slug)
    if not p.exists():
        return None
    return parse(p.read_text(encoding="utf-8"), slug)


def tutte() -> list[Persona]:
    d = paths.dir_persone()
    if not d.exists():
        return []
    return [parse(f.read_text(encoding="utf-8"), f.stem) for f in sorted(d.glob("*.md"))]


def per_slug() -> dict[str, Persona]:
    return {p.slug: p for p in tutte()}


def esiste(slug: str) -> bool:
    return percorso(slug).exists()


def per_email(email: str) -> Persona | None:
    email = (email or "").strip().lower()
    if not email:
        return None
    for p in tutte():
        if p.email.strip().lower() == email:
            return p
    return None


# --- scrittura ---------------------------------------------------------------


class SegretoInKb(Exception):
    """Un token in una scheda è un incidente, non un bug (`05` §4.5, C8)."""


def _scrivi(slug: str, testo: str) -> None:
    if SEGRETI_VIETATI.search(testo):
        raise SegretoInKb(f"tentata scrittura di un segreto in kb/persone/{slug}.md")
    p = percorso(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(testo if testo.endswith("\n") else testo + "\n", encoding="utf-8")


def _sostituisci_sezione(testo: str, nome: str, corpo: str) -> str:
    righe = testo.splitlines()
    inizio = None
    fine = len(righe)
    for i, riga in enumerate(righe):
        if riga.strip().lower() == f"## {nome}".lower():
            inizio = i
        elif inizio is not None and riga.startswith("## "):
            fine = i
            break
    blocco = [f"## {nome.capitalize() if nome.islower() else nome}", "", *corpo.splitlines(), ""]
    if inizio is None:
        return "\n".join([*righe, "", *blocco])
    return "\n".join([*righe[:inizio], *blocco, *righe[fine:]])


def formatta_preferenza(pref: Preferenza) -> str:
    origine = pref.origine or "dichiarata"
    if pref.data:
        # «solo» perché la data è l'**ambito**, non la firma: senza quella
        # parola la riga si legge «confermata il 02/07», che è il vecchio
        # significato del campo e il contrario di quello nuovo (`02` P2).
        origine = f"{origine} solo {pref.data}"
    riga = f"- **{pref.vincolo}** — _{origine}_"
    if pref.storia:
        riga += f" — storia: «{pref.storia}»"
    return riga


def salva_preferenza(slug: str, pref: Preferenza) -> Persona:
    """Write di `salva-preferenza` (`02` chip). Sempre dopo conferma umana."""
    p = percorso(slug)
    testo = p.read_text(encoding="utf-8")
    persona = parse(testo, slug)
    # La chiave è vincolo **+ ambito**: «no_turno: gio solo il 02/07» e «no_turno:
    # gio ogni settimana» sono due dichiarazioni diverse, e due giovedì diversi
    # pure. Deduplicare sul solo vincolo faceva sparire la precedente (`02` P2).
    altre = [x for x in persona.preferenze if (x.vincolo, x.data) != (pref.vincolo, pref.data)]
    corpo = "\n".join(formatta_preferenza(x) for x in [*altre, pref])
    _scrivi(slug, _sostituisci_sezione(testo, "Preferenze", corpo))
    return leggi(slug)  # type: ignore[return-value]


def rimuovi_preferenza(slug: str, vincolo: str) -> Persona:
    testo = percorso(slug).read_text(encoding="utf-8")
    persona = parse(testo, slug)
    altre = [x for x in persona.preferenze if x.vincolo != vincolo]
    corpo = "\n".join(formatta_preferenza(x) for x in altre) or f"{_PLACEHOLDER}."
    _scrivi(slug, _sostituisci_sezione(testo, "Preferenze", corpo))
    return leggi(slug)  # type: ignore[return-value]


def dimentica_storia(slug: str, vincolo: str) -> Persona:
    """`05` §4.2: la persona può togliere l'aneddoto e tenere il vincolo."""
    persona = leggi(slug)
    assert persona is not None
    for pref in persona.preferenze:
        if pref.vincolo == vincolo:
            return salva_preferenza(slug, replace(pref, storia=""))
    return persona


def _formatta_blocco(nome: str, dati: dict[str, str]) -> str:
    righe = [f"{nome}:"]
    for k, v in dati.items():
        righe.append(f"  {k}: {v}")
    return "\n".join(righe)


def imposta_blocco(slug: str, nome: str, dati: dict[str, str]) -> Persona:
    """Scrive `account:` / `calendario:` — solo fatti non segreti."""
    testo = percorso(slug).read_text(encoding="utf-8")
    corpo = _formatta_blocco(nome, dati)
    _scrivi(slug, _sostituisci_sezione(testo, nome.capitalize(), corpo))
    return leggi(slug)  # type: ignore[return-value]


def togli_blocco(slug: str, nome: str) -> Persona:
    testo = percorso(slug).read_text(encoding="utf-8")
    righe = testo.splitlines()
    inizio = None
    fine = len(righe)
    for i, riga in enumerate(righe):
        if riga.strip().lower() == f"## {nome}".lower():
            inizio = i
        elif inizio is not None and riga.startswith("## "):
            fine = i
            break
    if inizio is None:
        return leggi(slug)  # type: ignore[return-value]
    _scrivi(slug, "\n".join([*righe[:inizio], *righe[fine:]]))
    return leggi(slug)  # type: ignore[return-value]


def aggiungi_mansione(slug: str, nome: str, origine: str = "confermata") -> Persona:
    testo = percorso(slug).read_text(encoding="utf-8")
    persona = parse(testo, slug)
    nome = normalizza_mansione(nome)
    if persona.ha_mansione(nome):
        return persona
    sez = _sezioni(testo)
    righe = [r for r in sez.get("mansioni", []) if r.strip()]
    righe.append(f"- **{nome}** — _{origine}_ —")
    _scrivi(slug, _sostituisci_sezione(testo, "Mansioni", "\n".join(righe)))
    return leggi(slug)  # type: ignore[return-value]


def imposta_ruoli(slug: str, ruoli: list[str]) -> Persona:
    """I ruoli (manager / attivatore) stanno nei metadati della scheda."""
    testo = percorso(slug).read_text(encoding="utf-8")
    riga = f"- ruoli: {', '.join(sorted(set(r.strip().lower() for r in ruoli)))}"
    righe = testo.splitlines()
    for i, r in enumerate(righe):
        if re.match(r"^-\s*ruoli\s*:", r):
            righe[i] = riga
            break
    else:
        ultimo = 0
        for i, r in enumerate(righe):
            if _META.match(r.strip()):
                ultimo = i
        righe.insert(ultimo + 1, riga)
    _scrivi(slug, "\n".join(righe))
    return leggi(slug)  # type: ignore[return-value]
