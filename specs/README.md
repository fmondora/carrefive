# Specifiche — TIME MACHINE (Le Rocce)

Spec-driven: si costruisce da questi file, non dalla chat. Lingua italiana.
Principi in `00-high-level.md` §§2–3. Knowledge di pilota in `kb/`.

## Come si scrive una spec qui

File numerato, nome parlante: `specs/0N-nome.md`.

1. **Problema & job-to-be-done**
2. **Metrica d'esito** — distribuzione, non booleano
3. **Vincoli**
4. **Approccio**
5. **Confine di fiducia**
6. **Evals**
7. **Aperto / decisioni**

Ogni spec che tocca una superficie marca `[AIUxer]`. Ogni spec che tocca runtime, costo, evals marca `[AIEngineer]`. Le due lenti possono divergere: l'arbitro è l'esito misurato; su pubblicazione turni e dati retributivi il confine ha veto.

Gli **use case** (sezione in coda a ogni spec) li scrive **AIUxer**: utilizzo, persone vere di Le Rocce, cosa l'AI può e non può. Non sostituiscono le evals. Numerazione globale `UC-01`…

Prima di implementare una slice di UI: skill `surface-map` del plugin `ai-native`, poi `project-book`. Niente codice di catalogo finché il Book slice non è approvato.

## Indice

| Spec | Cosa fissa | Lenti |
|---|---|---|
| `00-high-level.md` | Visione, principi, mercato, MoSCoW, KPI | — |
| `01-sistema-agentico.md` | Contratto agenti, orchestratore, KB, loop | AIEngineer (lead), AIUxer su P-L |
| `02-genui.md` | Superfici, catalogo chiuso, chip, guscio | AIUxer (lead), AIEngineer su registry/costo |
| `03-calendario-google.md` | OAuth Google, sync turni pubblicati | AIEngineer (lead), AIUxer su chip/stato |
| `04-ferie-permessi-gamma.md` | Montante ferie/permessi: file → kb, poi Gamma | AIEngineer (lead), AIUxer su widget |
| `05-security-gdpr.md` | GDPR su ciò che il dipendente condivide; security sistema; DeepSec | AIEngineer (lead), AIUxer su visibilità |
| `06-design-system.md` | Tono fresco, token, mappa Beautiful UI → catalogo | AIUxer (lead) |

Fuori da questa edizione: export paghe, multi-store, secondo personale, payroll interno, Outlook/Apple, richiesta ferie verso Gamma.
