# Handoff — slice A — per Claude Code

Book **approvato** 2026-08-16. Tu implementi. Non ridisegni.

## Dove

```
cwd: /Users/fmondora/wip/personal/carrefive/.claude/worktrees/runtime-specs
python3.12 · test: pytest
demo: ./demo.sh 8770   (TM_OGGI=2026-06-29T14:05)
```

Design root (solo lettura, SoT + Book):

`/Users/fmondora/wip/personal/carrefive/`

## Leggi prima, in quest’ordine

1. `docs/ai-native/book/09-IMPL-READY.md` — **unico piano di lavoro**
2. `docs/ai-native/book/02-SURFACES.md` — gerarchia `attesa_umano`; Anna non si tocca
3. `docs/ai-native/book/03-CATALOG.md` — zero tipi nuovi
4. `docs/ai-native/book/05-ARCHITECTURE.md` — composizione, `_FLUSSO`, validazione
5. `docs/ai-native/book/07-RELIABILITY-EVALS.md` — evals da aggiungere, canary da non rompere
6. `docs/ai-native/book/08-TENSIONS.md` — decisioni già chiuse

Specs `specs/0N-*.md` restano SoT. Se Book e spec divergono su **questa slice**, vince il Book. Non emendare le spec. Non aprire 01–03 del Book.

## Cosa fai

Cinque slice di `09`, in ordine (5 può andare in parallelo a 2–4):

1. Composer spento solo su `LLMGiu` vero; `SchemaNonRispettato` → `motivo=schema`; Annulla → `/home`
2. `sposta-turno` con campi + conferma; POST nudo ≠ 500; via dal guscio
3. `coverage-gap` cliccabile → `candidati_per_gap` (layer 1 liberi, layer 2 già-in-turno altra fascia; mai R/F; tetto 8; zero LLM)
4. Approval inline sulla home; in `attesa_umano` ordine: ciclo → conferma → blocco → gap → pack → `me`
5. Tabellone = settimana del ciclo + overlay bozza; niente fallback al 29/06

## Vietato

- Nuovi tipi di catalogo (`gap-candidates`, canvas, HTML libero, chat-casa)
- Toccare la home di Anna (U1 invariato: `person-shifts` + `person-balances`, zero `week-grid`)
- Rifare Scheduling / 3 varianti / solver da zero
- Far eseguire `sposta-turno` al Copilot
- Chat come dashboard
- Font, attivatore, calendario Google, request ferie
- Push git (repo locale; niente push)
- Allargare lo scope «perché sarebbe meglio»

## Test

`python3.12 -m pytest tests/ -q`

Devono restare verdi: U1–U9, E1–E8, confine P-L, G2.

Aggiungi i canary di `07`: U-sposta-*, U-gap-*, U-settimana-ciclo, U-annulla, U-composer-det, U-me-senza-overlay-altra-settimana, E-candidati-fn.

## Done

Le cinque slice di 09 hanno il loro *Done when*. Poi stop. Se la realtà contraddice il Book: fermati e scrivi il delta — non inventare.

Invariante: **l'AI propone, l'umano dispone, il calcolo è deterministico.**
