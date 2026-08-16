"""Backend AI astratto (`01` §3).

`fake` in test, `cli` in dev, `api` in prod. Il resto del sistema non sa quale
gira: vede `genera(prompt, schema)` e riceve un dict già validato.

Due regole non negoziabili:

1. **L'output LLM è input non fidato**: si valida allo schema al confine;
   sul mismatch si scarta e si ritenta, poi si rinuncia con onestà.
2. **Se l'AI è giù si dice**: `LLMGiu`. Nessun 200 finto (E6, U7, P-D).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class LLMGiu(Exception):
    """Il backend non risponde. Il path deterministico non ne risente."""


class SchemaNonRispettato(Exception):
    """Output fuori schema dopo i retry: si scarta con motivo (E8)."""


# --- validazione di schema minimale -----------------------------------------

_TIPI = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
}


def valida(dati: Any, schema: dict[str, Any], dove: str = "$") -> None:
    tipo = schema.get("type")
    if tipo and not isinstance(dati, _TIPI[tipo]):
        raise SchemaNonRispettato(f"{dove}: atteso {tipo}, trovato {type(dati).__name__}")
    if tipo == "object":
        for chiave in schema.get("required", []):
            if chiave not in dati:
                raise SchemaNonRispettato(f"{dove}: manca il campo obbligatorio {chiave!r}")
        for chiave, sotto in (schema.get("properties") or {}).items():
            if chiave in dati:
                valida(dati[chiave], sotto, f"{dove}.{chiave}")
    elif tipo == "array":
        sotto = schema.get("items")
        if sotto:
            for i, v in enumerate(dati):
                valida(v, sotto, f"{dove}[{i}]")
    if "enum" in schema and dati not in schema["enum"]:
        raise SchemaNonRispettato(f"{dove}: {dati!r} fuori enum")


def _estrai_json(testo: str) -> Any:
    testo = testo.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", testo, re.S)
    if fence:
        testo = fence.group(1).strip()
    inizio = min((i for i in (testo.find("{"), testo.find("[")) if i >= 0), default=-1)
    if inizio > 0:
        testo = testo[inizio:]
    return json.loads(testo)


# --- backend ------------------------------------------------------------------


class Backend(Protocol):
    nome: str

    def genera(self, prompt: str, sistema: str = "") -> str: ...


@dataclass(slots=True)
class BackendFake:
    """Test e dev senza rete. Risposte scriptate per prefisso di prompt."""

    nome: str = "fake"
    risposte: list[Any] = field(default_factory=list)
    per_agente: dict[str, Any] = field(default_factory=dict)
    giu: bool = False
    chiamate: list[tuple[str, str]] = field(default_factory=list)

    def genera(self, prompt: str, sistema: str = "") -> str:
        self.chiamate.append((sistema, prompt))
        if self.giu:
            raise LLMGiu("backend fake marcato giù")
        for chiave, risposta in self.per_agente.items():
            if chiave in sistema or chiave in prompt[:400]:
                return risposta if isinstance(risposta, str) else json.dumps(risposta)
        if self.risposte:
            r = self.risposte.pop(0)
            return r if isinstance(r, str) else json.dumps(r)
        raise LLMGiu("nessuna risposta scriptata per questo prompt")


@dataclass(slots=True)
class BackendCLI:
    """Dev: un coding agent locale in subprocess (`claude -p`, o simili)."""

    comando: list[str] = field(default_factory=lambda: ["claude", "-p"])
    timeout: float = 90.0
    nome: str = "cli"

    def genera(self, prompt: str, sistema: str = "") -> str:
        testo = f"{sistema}\n\n{prompt}" if sistema else prompt
        try:
            p = subprocess.run(
                self.comando,
                input=testo,
                text=True,
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise LLMGiu(str(e)) from e
        if p.returncode != 0:
            raise LLMGiu(p.stderr.strip()[:400] or f"exit {p.returncode}")
        return p.stdout


@dataclass(slots=True)
class BackendAPI:
    """Prod: Messages API. La chiave sta in env, **mai** in config o in kb."""

    modello: str = "claude-sonnet-5"
    env_chiave: str = "ANTHROPIC_API_KEY"
    base_url: str = "https://api.anthropic.com/v1/messages"
    max_tokens: int = 4096
    timeout: float = 60.0
    nome: str = "api"

    def genera(self, prompt: str, sistema: str = "") -> str:
        import httpx

        chiave = os.environ.get(self.env_chiave, "")
        if not chiave:
            raise LLMGiu(f"{self.env_chiave} non impostata")
        corpo: dict[str, Any] = {
            "model": self.modello,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if sistema:
            corpo["system"] = sistema
        try:
            r = httpx.post(
                self.base_url,
                json=corpo,
                headers={
                    "x-api-key": chiave,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                timeout=self.timeout,
            )
            r.raise_for_status()
            dati = r.json()
        except Exception as e:
            raise LLMGiu(str(e)) from e
        return "".join(b.get("text", "") for b in dati.get("content", []))


# --- confine: qui si valida --------------------------------------------------


@dataclass(slots=True)
class LLM:
    backend: Backend
    versione_prompt: str = "1"
    retry: int = 1

    @property
    def nome(self) -> str:
        return self.backend.nome

    def genera(self, prompt: str, sistema: str = "") -> str:
        return self.backend.genera(prompt, sistema)

    def genera_json(
        self, prompt: str, schema: dict[str, Any], sistema: str = ""
    ) -> tuple[Any, list[str]]:
        """Ritorna (dati validati, motivi degli scarti). Alza `LLMGiu` se è giù."""
        scarti: list[str] = []
        for tentativo in range(self.retry + 1):
            grezzo = self.backend.genera(prompt, sistema)
            try:
                dati = _estrai_json(grezzo)
                valida(dati, schema)
                return dati, scarti
            except (json.JSONDecodeError, SchemaNonRispettato) as e:
                scarti.append(f"tentativo {tentativo + 1}: {e}")
                prompt = (
                    f"{prompt}\n\nIl tentativo precedente è stato scartato: {e}. "
                    "Rispondi SOLO con JSON conforme allo schema."
                )
        raise SchemaNonRispettato("; ".join(scarti))


_costruttori: dict[str, Callable[[], Backend]] = {
    "fake": lambda: BackendFake(),
    "cli": lambda: BackendCLI(),
    "api": lambda: BackendAPI(),
}

_llm: LLM | None = None


def llm() -> LLM:
    global _llm
    if _llm is None:
        scelta = os.environ.get("TM_LLM", "fake").lower()
        _llm = LLM(backend=_costruttori.get(scelta, _costruttori["fake"])())
    return _llm


def imposta_llm(x: LLM | Backend | None) -> None:
    global _llm
    if x is None or isinstance(x, LLM):
        _llm = x
    else:
        _llm = LLM(backend=x)
