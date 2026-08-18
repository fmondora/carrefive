"""Backend AI astratto (`01` §3).

Senza `TM_LLM` il backend si sceglie da solo: la **chiave** se ce n'è una che
l'SDK sappia risolvere (env o profilo `ant auth login` — la stessa catena che
usa Claude Code), altrimenti la **CLI** `claude -p` locale, altrimenti niente
modello. `TM_LLM=fake|cli|api` forza la scelta; i test usano `fake`.

Il resto del sistema non sa quale gira: vede `genera(prompt, schema)` e riceve
un dict già validato.

Due regole non negoziabili:

1. **L'output LLM è input non fidato**: si valida allo schema al confine;
   sul mismatch si scarta e si ritenta, poi si rinuncia con onestà.
2. **Se l'AI è giù si dice**: `LLMGiu`. Nessun 200 finto (E6, U7, P-D).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class LLMGiu(Exception):
    """Il backend non risponde. Il path deterministico non ne risente."""


class LLMNonConfigurato(LLMGiu):
    """Non c'è nessun backend da chiamare: manca la chiave, il comando, la config.

    È un caso diverso da «è giù»: il sistema funziona come previsto, solo senza
    la parte di linguaggio. Dirlo con le stesse parole di un guasto spaventa
    per niente — e nasconde un guasto vero quando capita davvero.
    """


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
        raise LLMNonConfigurato("nessuna risposta scriptata: backend fake senza copione")


def _comando_cli() -> list[str]:
    """`TM_LLM_CLI` sovrascrive il comando (utile per scegliere un modello).

    Misurato su questa macchina: `claude -p` risponde in ~38 s a una richiesta
    del Copilot. Va bene per provare, è troppo per un composer sincrono — chi
    sviluppa a lungo può puntarlo a un modello più rapido, ma è una scelta sua:
    `TM_LLM_CLI="claude -p --model haiku"`.
    """
    grezzo = os.environ.get("TM_LLM_CLI", "").strip()
    return grezzo.split() if grezzo else ["claude", "-p"]


@dataclass(slots=True)
class BackendCLI:
    """Dev: un coding agent locale in subprocess (`claude -p`, o simili)."""

    comando: list[str] = field(default_factory=_comando_cli)
    timeout: float = 120.0
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
        except FileNotFoundError as e:
            raise LLMNonConfigurato(f"comando {self.comando[0]!r} non trovato") from e
        except (OSError, subprocess.TimeoutExpired) as e:
            raise LLMGiu(str(e)) from e
        if p.returncode != 0:
            raise LLMGiu(p.stderr.strip()[:400] or f"exit {p.returncode}")
        return p.stdout


@dataclass(slots=True)
class BackendAPI:
    """Prod: Messages API tramite l'**SDK ufficiale** `anthropic`.

    Credenziali: il client a zero argomenti risolve da solo la catena
    `ANTHROPIC_API_KEY` → `ANTHROPIC_AUTH_TOKEN` → profilo OAuth di
    `ant auth login` → federazione → profilo di default. Quindi *non* si legge
    la chiave a mano e non la si passa in giro: nessun segreto attraversa il
    nostro codice (`05` §4.5).

    Effort basso di default: qui l'LLM scrive due righe di prosa o ordina tre
    candidati — non deve ragionare a lungo (`01` §3, costo).
    """

    modello: str = field(default_factory=lambda: os.environ.get("TM_MODELLO", "claude-opus-5"))
    effort: str = field(default_factory=lambda: os.environ.get("TM_EFFORT", "low"))
    max_tokens: int = 8192
    nome: str = "api"
    _client: Any = None

    def _apri(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:  # pragma: no cover - dipendenza dichiarata
                raise LLMNonConfigurato("SDK `anthropic` non installato") from e
            try:
                self._client = anthropic.Anthropic()
            except Exception as e:
                raise LLMNonConfigurato(f"nessuna credenziale Anthropic risolvibile: {e}") from e
        return self._client

    def genera(self, prompt: str, sistema: str = "") -> str:
        import anthropic

        client = self._apri()
        corpo: dict[str, Any] = {
            "model": self.modello,
            "max_tokens": self.max_tokens,
            "output_config": {"effort": self.effort},
            "messages": [{"role": "user", "content": prompt}],
        }
        if sistema:
            corpo["system"] = sistema
        try:
            risposta = client.messages.create(**corpo)
        except anthropic.AuthenticationError as e:
            raise LLMNonConfigurato(f"credenziali rifiutate: {e}") from e
        except anthropic.APIStatusError as e:
            raise LLMGiu(f"{e.status_code}: {str(e)[:200]}") from e
        except anthropic.APIConnectionError as e:
            raise LLMGiu(str(e)) from e
        if risposta.stop_reason == "refusal":
            # rifiuto del modello: è un esito, non un guasto — si scarta pulito
            raise SchemaNonRispettato("il modello ha rifiutato la richiesta")
        return "".join(b.text for b in risposta.content if b.type == "text")


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


def _credenziale_api() -> bool:
    """C'è una credenziale Anthropic che l'SDK sappia risolvere?

    Non basta guardare `ANTHROPIC_API_KEY`: la catena dell'SDK include anche
    `ANTHROPIC_AUTH_TOKEN` e il profilo OAuth di `ant auth login` — quello che
    usa anche Claude Code. Una chiave assente **non** significa «niente
    credenziali», quindi si chiede a `ant` invece di dedurlo.
    """
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    if shutil.which("ant") is None:
        return False
    try:
        p = subprocess.run(
            ["ant", "auth", "status"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return p.returncode == 0 and "no active" not in p.stdout.lower()


def scelta_automatica() -> str:
    """La chiave se c'è, altrimenti la CLI locale, altrimenti niente modello.

    In sviluppo su una macchina già autenticata con Claude Code la CLI c'è
    quasi sempre: è il motivo per cui viene prima di `fake`.
    """
    if _credenziale_api():
        return "api"
    if shutil.which(BackendCLI().comando[0]):
        return "cli"
    return "fake"


_llm: LLM | None = None


def llm() -> LLM:
    global _llm
    if _llm is None:
        scelta = (os.environ.get("TM_LLM") or "").lower() or scelta_automatica()
        _llm = LLM(backend=_costruttori.get(scelta, _costruttori["fake"])())
    return _llm


def imposta_llm(x: LLM | Backend | None) -> None:
    global _llm
    if x is None or isinstance(x, LLM):
        _llm = x
    else:
        _llm = LLM(backend=x)
