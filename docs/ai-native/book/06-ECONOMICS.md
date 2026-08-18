# 06 — Economics
**Owner:** AIEngineer · **Status:** ready

Questa slice è **`free-det`**. Zero chiamate modello nuove per chiudere i job di 01.

## Cost-per-outcome
| Job | Cost driver | Budget / cap |
|---|---|---|
| Coprire un buco | CPU locale (`candidati_per_gap` + N `person_shifts`) | 0 token. N ≤ 8. |
| Sposta + compliance | codice CCNL | 0 token |
| Accetta / pubblica | write kb + audit | 0 token |
| Tabellone ciclo | mapping piano | 0 token |
| Composer dopo path det | oggi: 1 `genera_json` per la prosa, anche sulla preferenza | **non aumentare**. Se schema fallisce: non ritentare in loop; mostra fatti. |
| Settimana chiusa (accettata o rifiutata) | inferenza già spesa in `genera-bozza` | invariato: costo/settimana, non per tap |

## Model tiering
- Tap-gap, sposta, conferme, tabellone: **nessun modello**.
- Copilot prosa: stesso backend di oggi (`TM_LLM` / CLI / niente). Non è un requisito di A che la prosa sia bella.
- Non chiamare `claude -p` per elencare chi è libero il sabato.

## Caching & free paths
- Candidati: calcolati sul piano della bozza in RAM. No cache extra.
- `_FLUSSO` è la memo della sessione (candidati e conferma pending).

## Latency
| Gesto | Perceived | Total | Gate |
|---|---|---|---|
| tap gap → candidati a schermo | < 200ms | stesso (sync) | se > 1s è un bug, non «serve l’async» |
| conferma sposta → home aggiornata | < 500ms | compliance sul piano | |
| Copilot NL | già ~38s se CLI | fuori budget di A; non peggiorare | composer non si spegne sul det |

`00` target inferenza < 10% del prezzo/utente: A non muove l’ago.

## Loop C1

| Job | Cost driver | Budget |
|---|---|---|
| Un enunciato → turno | **1** `genera_json` (non più classifica + prosa = 2) | cap 1. Schema fail → fatti, niente retry a valanga |
| Chip / conferma / tap cella | 0 token | tabella next det |
| Storia in prompt | ultimi ≤4 turni, solo testo+tipo | tetto caratteri via `blocco_dati` |

Latency percepita: path `api` / modello basso < **3 s** o si dice «un attimo» (copy det, non un tipo). `claude -p` ~38 s resta fuori budget — chi prova la chat non usa quel backend (già in README). C1 non aggiunge stream.

Tiering: stesso `TM_LLM`. Fake = test. Demo conversazionale = `api` o CLI veloce.
