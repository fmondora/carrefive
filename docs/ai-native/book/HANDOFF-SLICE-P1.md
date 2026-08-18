# Handoff — slice P1 — per Claude Code

Book **P1 approvato** 2026-08-17. Tu implementi. Non ridisegni.

A1–A3 sono shippate (manager). Non le rifare. Questo giro: **P1.1** e **P1.2** in `09-IMPL-READY.md`.

## Dove

```
cwd: /Users/fmondora/wip/personal/carrefive/.claude/worktrees/runtime-specs
python3.12 · pytest
demo: TM_OGGI=2026-06-29T14:05 + account. Non avviare su 8770 senza TM_KB/TM_OGGI.
```

Design root (sola lettura): `/Users/fmondora/wip/personal/carrefive/`

## Leggi prima

1. `docs/ai-native/book/HANDOFF-SLICE-P1.md` (questo file)
2. `docs/ai-native/book/09-IMPL-READY.md` — slice **P1.1**, **P1.2**
3. `docs/ai-native/book/02-SURFACES.md` — Loop P1
4. `docs/ai-native/surface-maps/2026-08-17-P1-surface-map.md`
5. `specs/01-sistema-agentico.md` Loop P1 (gateway)
6. `specs/02-genui.md` Loop P1
7. `specs/LOOPS.md`

## Cosa fai

**P1.1 — Gateway intent (non regex)**

`rispondi` classifica l’NL in enum chiuso, poi invoca la pipeline. Non è un `if pianoforte`.

```
preferenza | turni_miei | saldi | copri | comando_ciclo | saluto | sconosciuto
```

- Classifica: LLM + schema JSON sull’enum. Se LLM giù / schema fail / non configurato: intent = `sconosciuto` (o heuristica det **solo** come fallback debole). **Vietato** l’`else` attuale `consult(scheduling)`.
- `saluto` / `sconosciuto`: `copilot-turn` onesto + chip (`preferenza` / ferie / apri scheda). Composer acceso.
- `preferenza` → `scheda-preview` + `salva-preferenza` (già c’è).
- `turni_miei` / `saldi` → widget di **sé**. Anna: 403 se bersaglio ≠ self.
- `comando_ciclo` → chip, non eseguire (già così).
- `copri` in P1: proposta / chip, **non** write, **non** dump di 5 colleghi. Se non hai un path det sicuro: `sconosciuto` + chip.
- Allowlist Anna: `mostra_turni(self)`, `mostra_saldi(self)`, `prepara_preferenza`. Zero `genera-bozza` per lei.
- Manager: può `consult` forecast/scheduling/compliance/secondo **dopo** intent classificato, non sul default.

**P1.2 — Cella = preferenza**

Tap su un giorno di `person-shifts(me)` → stesso intent `preferenza` → `scheda-preview`. I pubblicati non si riscrivono. Primo paint U1: nessuna preview.

Chip sul widget e nel composer = gli stessi intent.

## Vietato

- Nuovi tipi di catalogo
- Chat-casa (il composer resta slot, le due card restano casa)
- `coverage-gap` in home Anna
- Marketplace swap / write turni della persona
- Toccare A3 residuo / Scheduling solver
- Push

## Test

`python3.12 -m pytest tests/ -q`

Restano verdi: U1, U5, U7, resto A1–A3.

Aggiungi:
- **U-p-ciao** — POST «ciao!» come Anna: 0 invocazioni scheduling, 0 `person-shifts` di colleghi, composer acceso, ≥1 chip utile
- **U-p-cella** — tap/POST giorno → `scheda-preview`, kb invariata finché `salva-preferenza` conferma
- **E10** — «ciao!» non è `consult(scheduling)`

## Done

*Done when* P1.1 e P1.2. Poi stop. Se il Book contraddice il codice: delta, non inventare.

Invariante: **l'AI propone, l'umano dispone, il calcolo è deterministico.**
