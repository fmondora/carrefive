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

Prima di implementare una slice di UI: skill `surface-map` del plugin `ai-native`, poi `project-book`. Niente codice di catalogo finché il Book slice non è approvato.

## Indice

| Spec | Cosa fissa | Lenti |
|---|---|---|
| `00-high-level.md` | Visione, principi, mercato, MoSCoW, KPI | — |
| `01-sistema-agentico.md` | Contratto agenti, orchestratore, KB, loop | AIEngineer (lead), AIUxer su P-L |
| `02-genui.md` | Superfici, catalogo chiuso, chip, guscio | AIUxer (lead), AIEngineer su registry/costo |
| `03-calendario-google.md` | OAuth Google, sync turni pubblicati | AIEngineer (lead), AIUxer su chip/stato |

Fuori da questa edizione: export paghe, multi-store, secondo personale, payroll interno, Outlook/Apple.
