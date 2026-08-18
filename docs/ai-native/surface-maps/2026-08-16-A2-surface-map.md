# Surface map — TIME MACHINE / Le Rocce — 2026-08-16 — **A2**

## Meta
- Loop id: **A2** (secondo giro: dopo impl slice A, commit `c8585ee`)
- Precedente: [`2026-08-16-surface-map.md`](./2026-08-16-surface-map.md) (A1)
- Design root: `/Users/fmondora/wip/personal/carrefive`
- Impl root: `/Users/fmondora/wip/personal/carrefive/.claude/worktrees/runtime-specs`
- Live: `http://127.0.0.1:8771/` (`TM_OGGI=2026-06-29T14:05`, `TM_LLM=fake`) — non 8770 (server senza demo/account)
- Sources: Book A, specs 00–02/05–06, `home.html`, `widget.html`, `app.py`, `scheduling.candidati_per_gap`, `vista.candidati_gap`/`week_grid`, `ciclo.chip`, test live Anna + Francesco

## Roles
| Role | Surfaces | Notes A2 |
|---|---|---|
| Dipendente (Anna) | landing, home 2 card, composer | **Intatta.** U1 vivo. Composer acceso dopo preferenza. |
| Manager (Francesco) | briefing `attesa_umano` + tap gap + approval inline + tabellone ciclo | Gesto buco **c’è**. Gesto sul *blocco* **no**. |
| Attivatore / anonimo | invariati | non ritestati in A2 |

## Surfaces
| Surface | Family | Entry | Primary jobs | Stato A2 |
|---|---|---|---|---|
| Home Anna | det + composer | `/home` | i miei turni | chiuso |
| Home manager `attesa_umano` | hybrid | `/home` | chiudere la settimana | gerarchia ok; job pubblica bloccato |
| Approval chrome | det | `_FLUSSO["conferma"]` in `/home` | confermare sposta/accetta | chiuso (URL resta `/home`) |
| Tabellone | det | `/tabellone` | vista bozza 06/07 | chiuso (overlay Luca+Mara) |
| Copilot | gen | `/copilota` | overflow | spento solo se giù; non è la porta |

## Runtime agents
Invariati (P-L tiene). `candidati_per_gap` è fn di Scheduling, non un settimo agente. Handler `app.py:629` è la colla (vista non importa `agents/`).

Canary: selectable ⊆ renderer — invariato, ok.

## Catalog diff
Allineato ad A1 salvo:

| Type | Status A2 | Note live |
|---|---|---|
| coverage-gap | none | ogni riga = form `consulta`. Funziona. 15 chip uguali, rumore. |
| person-shifts (candidato) | diverged vs intento Book | `adesso` = lunedì della *bozza* (Mara 10-14) mentre si parla di mar 16-20. |
| compliance-block | none come *vista* | **non è un atto**. Matteo 52h solo testo. |
| scegli-variante | diverged vs Book 02 | ancora in `CHIP_PER_STATO` con 1 variante (`ciclo.py:48`, `chip()` non filtra) |
| week-grid | none | settimana ciclo + badge bozza + 2 celle overlay. U8 adattato (idle = empty). |

Delta Claude ratificati: firma `candidati_per_gap(..., fascia, ...)`; due costanti 8.

## Trust boundary hotspots
- Dual gate `pubblica` tiene: Matteo 52h → niente chip pubblica. **Troppo tiene**: non c’è modo di *sciogliere* il blocco dall’UI.
- `sposta-turno` confermato: Mara mar 10-14 → 16-20, pack «2 persone». OK.
- R/F fuori dai candidati. OK.
- Anna 403 tabellone / colleghi: non ritestato; test suite verde.

## Gaps that matter (clustered)
### P0 — blocks a real job end-to-end
1. **Non si pubblica.** Il blocco è l’eredità del template (Matteo 52h, già illegale la settimana prima). Coprire pizze non lo tocca. `compliance-block` non ha gesto. Il KPI «violazioni pubblicate = 0» è rispettato; il KPI «settimana chiusa» è irraggiungibile.

### P1 — structural
2. **Candidati sotto i 15 buchi**, non sotto la riga tappata. Il risultato del tap è sotto lo scroll. Composer `fixed` li copre a metà.
3. **`adesso` sul candidato è una bugia di orologio.** Mara «adesso 10-14» mentre il buco è martedì pomeriggio della settimana *dopo*.
4. **`scegli variante` con n=1** — Book A lo vietava, il codice no.

### P2
5. Path `kb/turni/…` ancora in chiaro. Date sui giorni di Anna. Font 06. 8770 di Claude senza `TM_OGGI`/account (401). Due costanti MAX=8.

## Keystone
**Il blocco è un buco che riguarda *una* persona.** Stesso contratto del gap: tap su Matteo 52h → i *suoi* `person-shifts` della bozza + chip `sposta-turno` precompilate sulle fasce che lo fanno scendere sotto tetto (o `R`). Zero tipi nuovi. Senza questo A è un gestore di buchi che non chiude mai la settimana.

## Do NOT touch
- Home Anna (due card).
- Catalogo chiuso, P-L, dual gate come *veto* (non toglierlo: renderlo *agibile*).
- Layer 2 movibili (13/15 gap hanno candidati; layer 1 era 0/15).
- Tabellone della settimana ciclo.
- Composer spento solo su `LLMGiu`.

## Proposals (2–3)
### A — Blocco = gesto (recommended)
- Tap riga `compliance-block` (violazione, non segnalazione) → `person-shifts` della persona flaggata (settimana ciclo) + form `sposta-turno` sulle celle che riducono le ore / mettono un R.
- Stessi tipi. `free-det`. Job: settimana *pubblicabile*.
- Cost/risk: basso; Compliance già ricalcola dopo `sposta`.

### B — Il buco tappato è il soggetto
- Dopo tap: la lista gap si riduce alla riga scelta; candidati subito sotto; card candidato senza `adesso` (solo il giorno del buco + `diff-edit`).
- `free-det`. Chiude P1.2–3.

### C — Debito A (optional)
- Filtrare `scegli-variante` se n=1; z-index composer; ratificare firma e MAX nel Book.

**Raccomando A+B nello stesso loop A2.** C è igiene nello stesso PR se non dilata. Senza A il manager torna al foglio per Matteo — e il tabellone 06/07 glielo mostra già a 52h.
