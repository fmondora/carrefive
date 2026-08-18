# Handoff — slice C1 — per Claude Code

Book **C1 approvato** 2026-08-18. Tu implementi. Non ridisegni. Non aprire M1/R1/Q1.

A1–A3 · P1 · P2 sono shippate. Non le rifare. Questo giro: **C1.1**, **C1.2**, **C1.3** in `09-IMPL-READY.md`.

## Dove

```
cwd: /Users/fmondora/wip/personal/carrefive
python3.12 · pytest
```

Il runtime è su `main` (`timemachine/`). Non usare il worktree se è indietro.

## Leggi prima

1. Questo file
2. `docs/ai-native/book/09-IMPL-READY.md` — solo C1.1–C1.3
3. `docs/ai-native/book/03-CATALOG.md` sezione Loop C1 (widget **proposti per ruolo**)
4. `docs/ai-native/surface-maps/2026-08-18-C1-surface-map.md`
5. `specs/02-genui.md` Loop C1 · `specs/01` Loop C1

## Cosa fai

**C1.1 — Il filo**

- `_FLUSSO["conversazione"]`: voci `{ruolo, testo?|turno?}`, cap 8 turni copilota.
- `POST /copilota` e tap cella **appendono**. 303 `/home#copilota`.
- Composer elenca la storia. Widget del turno (`scheda-preview`, …) **dentro** `copilot-turn`, non XOR.
- GET `/home` a freddo: zero `copilot-turn` (U1).

**C1.2 — Compose**

- Path felice: **una** `genera_json` `SCHEMA_COMPONI` `{testo, tool, chip}`.
- `tool` ⊆ `tool_per(attore)` (0 o 1). Widget lo fa `vista`, non il modello.
- Chip 1–3 ⊆ catalogo ∩ ruolo (tabella Book 03). Direttore ≠ lavoratore.
- `_intent` / `_è_preferenza` / `_copy` **solo** se il modello è giù / schema / non configurato.
- Anna + tool `consulta_scheduling` → rifiuto onesto, non dump.

**C1.3 — Next dopo write**

- Dopo `salva-preferenza` confermata: turno det «È sulla tua scheda…» + `apri-scheda` (+ `collega-google` se non collegata). 0 LLM.
- Dopo collega-google ok: «I pubblicati vanno sul tuo calendario.» + `apri-scheda`.
- Accetta/pubblica manager: **non** toccare (A3).

## Test

`U-c-filo` · `U-c-dentro` · `U-c-next` · `U-c-compose` · `U-c-degrado`.  
Restano verdi: U1, U5, U-p-ciao, U-p-cella, U-p-data, U-composer-det.

## Vietato

Tipi nuovi. Chat-casa. Terza card al primo paint. Sommario in scheda (M1). Richieste (R1). Piano per-persona (Q1). Allargare l’enum intent.
