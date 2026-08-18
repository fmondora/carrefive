# Handoff — slice P2 — per Claude Code

Book **P2 approvato** 2026-08-17. Tu implementi. Non ridisegni.

P1 `251ab6a` è shippata. A1–A3 anche. Non le rifare. Questo giro: **P2.1** e **P2.2** in `09-IMPL-READY.md`.

## Dove

```
cwd: /Users/fmondora/wip/personal/carrefive/.claude/worktrees/runtime-specs
python3.12 · pytest
demo: TM_OGGI=2026-06-29T14:05 + account.
```

Design root (sola lettura): `/Users/fmondora/wip/personal/carrefive/`

## Leggi prima

1. Questo file
2. `docs/ai-native/book/09-IMPL-READY.md` — slice **P2.1**, **P2.2**
3. `docs/ai-native/surface-maps/2026-08-17-P2-surface-map.md`
4. `specs/02-genui.md` Loop P2
5. `specs/01-sistema-agentico.md` (`copri` ombrello — già ratificato, non allargare l’enum)

## Cosa fai

**P2.1 — Cella = quella data**

- Tap su un giorno → vincolo con `Preferenza.data` = ISO di *quel* giorno.
- Preview in italiano: «solo il 02/07» (non solo il token `no_turno: gio`).
- Stesso preview, chip **«tutti i giovedì»**: weekday, `data` vuota (come UC-07 / NL «giovedì ho pianoforte»).
- `viola()` (o equivalente) **onora** `data` se c’è: gli altri giovedì non matchano.
- NL «giovedì pomeriggio ho pianoforte» resta ricorrente (U5 invariato).
- Enum intent: **non** si tocca. `copri` resta ombrello.

**P2.2 — Hygiene P1**

- Saluto Anna: non solo `apri-scheda`. Almeno una chip che porta al gesto (o copy che dice «tocca un giorno»).
- `copri` manager: rationale, non dump di 5 `person-shifts` di colleghi.
- Fix overlay illeggibile sulla riga tappata (live: `gio 7-16` si sporcava).

## Vietato

- Nuovi tipi. Allargare `INTENT`. Chat-casa. Inbox cover / marketplace. Push. Rifare P1 gateway.

## Test

`python3.12 -m pytest tests/ -q`

Restano verdi: U1, U5, U-p-ciao, U-p-cella, E10, resto A*.

Aggiungi **U-p-data**: tap gio 02/07 → preferenza con `data=2026-07-02`; un altro giovedì non è violato. Chip «tutti i giovedì» → weekday senza data.

## Done

*Done when* P2.1 e P2.2. Poi stop. Se il Book contraddice: delta, non inventare.

Invariante: **l'AI propone, l'umano dispone, il calcolo è deterministico.**
