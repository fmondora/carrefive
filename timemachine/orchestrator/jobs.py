"""Coda di job (`01` §4.7, `03` §3).

Forecast, scheduling e sync calendario **non** stanno nel request-path del
widget. Il guscio mostra «bozza in preparazione · 12s» con il tempo vero del
job, non un `setTimeout` del client (`06` §4.3 primitive 01).

Proprietà richieste: stato, retry con backoff, **idempotenza** per chiave.
Draft ≠ act: un worker prepara Proposte, non pubblica e non scrive schede.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

Stato = Literal["in_coda", "in_corso", "fatto", "fallito"]


@dataclass(slots=True)
class Job:
    nome: str
    chiave: str = ""  # idempotenza: stessa chiave = stesso job
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    stato: Stato = "in_coda"
    creato_at: float = field(default_factory=time.monotonic)
    iniziato_at: float | None = None
    finito_at: float | None = None
    tentativi: int = 0
    errore: str = ""
    risultato: Any = None

    @property
    def elapsed(self) -> float:
        """Secondi trascorsi — è la verità che il loader mostra."""
        inizio = self.iniziato_at or self.creato_at
        fine = self.finito_at or time.monotonic()
        return round(fine - inizio, 1)

    def come_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "nome": self.nome,
            "stato": self.stato,
            "elapsed": self.elapsed,
            "tentativi": self.tentativi,
            "errore": self.errore,
        }


@dataclass(slots=True)
class Coda:
    max_tentativi: int = 3
    backoff: float = 0.5
    sincrona: bool = True  # in test e in single-process: esegui subito
    jobs: dict[str, Job] = field(default_factory=dict)
    _per_chiave: dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # --- API -----------------------------------------------------------------

    def accoda(self, nome: str, funzione: Callable[[], Any], chiave: str = "") -> Job:
        with self._lock:
            if chiave and chiave in self._per_chiave:
                esistente = self.jobs[self._per_chiave[chiave]]
                if esistente.stato in ("in_coda", "in_corso"):
                    return esistente  # idempotenza: crash ≠ doppio evento
            job = Job(nome=nome, chiave=chiave)
            self.jobs[job.id] = job
            if chiave:
                self._per_chiave[chiave] = job.id
        if self.sincrona:
            self._esegui(job, funzione)
        else:
            threading.Thread(target=self._esegui, args=(job, funzione), daemon=True).start()
        return job

    def _esegui(self, job: Job, funzione: Callable[[], Any]) -> None:
        job.stato = "in_corso"
        job.iniziato_at = time.monotonic()
        for tentativo in range(1, self.max_tentativi + 1):
            job.tentativi = tentativo
            try:
                job.risultato = funzione()
            except Exception as e:  # il fallimento è visibile, non silenzioso (UC-05)
                job.errore = f"{type(e).__name__}: {e}"
                if tentativo < self.max_tentativi:
                    time.sleep(self.backoff * tentativo if not self.sincrona else 0)
                    continue
                job.stato = "fallito"
                job.finito_at = time.monotonic()
                return
            job.errore = ""
            job.stato = "fatto"
            job.finito_at = time.monotonic()
            return

    def stato(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def per_nome(self, nome: str) -> list[Job]:
        return [j for j in self.jobs.values() if j.nome == nome]

    def ultimo(self, nome: str) -> Job | None:
        candidati = self.per_nome(nome)
        return max(candidati, key=lambda j: j.creato_at) if candidati else None

    def in_corso(self) -> list[Job]:
        return [j for j in self.jobs.values() if j.stato in ("in_coda", "in_corso")]

    def svuota(self) -> None:
        with self._lock:
            self.jobs.clear()
            self._per_chiave.clear()


CODA = Coda()
