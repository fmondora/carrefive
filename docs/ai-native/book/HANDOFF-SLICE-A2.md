# Handoff — slice A2 — per Claude Code

Book **A2 approvato** 2026-08-17. Tu implementi. Non ridisegni.

A1 (`c8585ee`) è già shippata: non la rifare. Questo giro sono le slice **6–8** di `09-IMPL-READY.md`.

## Dove

```
cwd: /Users/fmondora/wip/personal/carrefive/.claude/worktrees/runtime-specs
python3.12 · test: pytest
demo: TM_OGGI=2026-06-29T14:05 + account (demo.sh). Non avviare su 8770 senza TM_KB/TM_OGGI.
```

Design root (sola lettura):

`/Users/fmondora/wip/personal/carrefive/`

## Leggi prima, in quest’ordine

1. `docs/ai-native/book/09-IMPL-READY.md` — slice **6, 7, 8**
2. `docs/ai-native/book/02-SURFACES.md` — sezione Loop A2
3. `docs/ai-native/book/08-TENSIONS.md` — blocco = gesto; layer 2 sostituisce la cella-giorno
4. `docs/ai-native/surface-maps/2026-08-16-A2-surface-map.md`
5. `specs/01-sistema-agentico.md` Loop A2 + UC-03 passo 5
6. `specs/02-genui.md` Loop A2
7. `specs/LOOPS.md`

## Cosa fai

**Slice 6 — Blocco = gesto.** Tap su una *violazione* di `compliance-block` (non su una segnalazione) → `person-shifts` di quella persona (settimana ciclo) + `sposta-turno` sulle celle che possono sciogliere il flag (es. togliere uno spezzone a Matteo, o `R`). Dopo lo spostamento Compliance ricalcola. Se il tetto scende, il blocco tetto sparisce; `pubblica` solo se anche `accettata`.

**Slice 7 — Il buco tappato è il soggetto.** Dopo tap su un gap: stack candidati *sotto quella riga* (dentro il `<li>` o subito dopo, non sotto le altre 14). Card candidato: niente slot `adesso` se il giorno ≠ `tempo.oggi()`. Soggetto = giorno/fascia del buco + overlay/diff.

**Slice 8 — Debito A1.** `scegli-variante` assente da `ciclo.chip()` se `len(varianti) ≤ 1`. Non unificare `MAX_CANDIDATI` e `MAX_TOCCATI`.

Preview di ogni `sposta-turno`: **prima → dopo** («Mara mar 10-14 → 16-20»). `imposta` sostituisce l’intera cella-giorno, non aggiunge.

## Vietato

- Nuovi tipi di catalogo
- Toccare la home di Anna (U1)
- Auto-accorciare Matteo / saltare Compliance
- Rifare Scheduling / il template
- Chat-casa
- Push git
- Allargare lo scope

## Test

`python3.12 -m pytest tests/ -q`

Restano verdi: U1–U9, E1–E8, confine, G2, canary A1 (U-sposta-*, U-gap-*, U-settimana-ciclo, U-composer-det, U-annulla).

Aggiungi: **U-blocco-gesto** (tap Matteo 52h → suoi turni + sposta; dopo spezzone in meno sotto tetto, blocco tetto assente). U-gap-candidati aggiornato: primo candidato in DOM dopo la rationale del tap, prima del pack; nessun `.adesso` su candidato futuro. Preview mostra entrambe le etichette.

## Done

I *Done when* delle slice 6–8. Poi stop. Se il Book contraddice il codice: fermati e scrivi il delta. Non inventare.

Invariante: **l'AI propone, l'umano dispone, il calcolo è deterministico.**
