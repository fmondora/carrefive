# Handoff — slice A3 — per Claude Code

Book **A3 approvato** 2026-08-17. Tu implementi. Non ridisegni.

A1 `c8585ee` e A2 `849f86a` sono shippate: non le rifare. Questo giro sono le slice **9–10** di `09-IMPL-READY.md`.

## Dove

```
cwd: /Users/fmondora/wip/personal/carrefive/.claude/worktrees/runtime-specs
python3.12 · pytest
demo: TM_OGGI=2026-06-29T14:05 + account (demo.sh). Non avviare su 8770 senza TM_KB/TM_OGGI.
```

Design root (sola lettura): `/Users/fmondora/wip/personal/carrefive/`

## Leggi prima

1. `docs/ai-native/book/09-IMPL-READY.md` — slice **9 e 10**
2. `docs/ai-native/book/02-SURFACES.md` — Loop A3
3. `docs/ai-native/book/08-TENSIONS.md` — 15 buchi vs close
4. `docs/ai-native/surface-maps/2026-08-17-A3-surface-map.md`
5. `specs/02-genui.md` Loop A3
6. `specs/LOOPS.md`

## Cosa fai

**Slice 9 — Residuo, non muro**

1. `coverage-gap`: prima riga = «N buchi · non bloccano»; **una** riga primaria (prossimo copribile, aperta). Il resto in disclosure. Tap invariato, esito ancora sotto *quella* riga.
2. Approval `accetta` / `pubblica`: in testa «restano N buchi». **Non** è un veto. Dual gate invariato (solo CCNL + accettata).
3. Dopo `sposta-turno` confermato: non scaricare sul muro. Stesso path `consulta` sul **prossimo** buco con candidati, o empty onesto se nessuno è copribile.

**Slice 10 — Hygiene**

- Chip mossa (`6-14 → R`) con il **giorno** visibile (lun/mer/ven).
- Allinea Book 05–07 al codice A2 solo se tocchi quei file (tap-blocco, `MAX_CELLE_SBLOCCO`, 0 token). Non unificare i MAX.

## Vietato

- Nuovi tipi. Toccare Anna (U1). Far diventare i buchi un veto su `pubblica`.
- Rifare Scheduling / template. Auto-coprire i 15 buchi. Chat-casa. Push.

## Test

`python3.12 -m pytest tests/ -q`

Restano verdi: U1–U9, E*, confine, U-blocco-gesto, U-gap-*, U-sposta-*, U-settimana-ciclo.

Aggiungi:
- **U-residuo-pubblica** — dopo Matteo sciolto + accetta: chip pubblica **e** testo residuo buchi.
- **U-prossimo-buco** — dopo sposta su un gap, `.esito` sul successivo copribile, non 15 form piatte.

## Done

*Done when* slice 9–10. Poi stop. Se il Book contraddice il codice: delta, non inventare.

Invariante: **l'AI propone, l'umano dispone, il calcolo è deterministico.**
