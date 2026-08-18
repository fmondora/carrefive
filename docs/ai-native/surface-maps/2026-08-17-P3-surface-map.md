# Surface map — TIME MACHINE / Le Rocce — 2026-08-17 — **P3**

## Meta
- Loop id: **P3**
- P2 shippato: `9ccb62a`, 233 test, live `:8770`
- Sources: live tap gio (preview «solo il 02/07» + chip Tutti i giovedì); `privacy.viola` inizio_ora; `ore_in_fascia`; delta Claude

## Cosa P2 ha chiuso
Tap = quella data. Preview ha riga **quando**. Chip Solo / Tutti. Dedup su vincolo+ambito. `operativa()` porta `@ISO` al manager/modello.

## Ratifiche extra (non in lista file, necessarie)
- Dedup `salva_preferenza` su vincolo+ambito.
- Parola «solo» in scheda (data ≠ firma).
- Saluto: ramo copy (niente chip `aggiorna-saldi` su fonte file). OK.

## Gap
### P0
1. **`no_pomeriggio` non vede 7–16.** `viola()` guarda solo `inizio_ora` (`privacy.py:136-139`). 7-16 inizia alle 7 → False. UC-07 (Anna, pianoforte, gio 7-16) si *salva* e Scheduling **non segnala**. U5 verifica la write, non la lettura. `ore_in_fascia` esiste già.

### P1
2. Preview copy: «vedranno `no_turno: gio`» — `operativa()` ora è `no_turno: gio @2026-07-02`. Testo stantio.
3. Chip saluto ancora solo testo + apri scheda (concesso da P2.2).

### P2
Inbox cover. Marketplace.

## Keystone
**`viola` = sovrapposizione di fascia**, non ora d’inizio. Stesso `ore_in_fascia`. Zero tipi.

## Do NOT touch
Enum intent. Casa due card. P2 ambito. Dual gate.

## Proposals
### A — Sovrapposizione (recommended)
`viola(vincolo, turno)` via `ore_in_fascia`. `no_pomeriggio` ∩ 7-16 = True. Se non si può onorare: nota «non onorato» (E3). `free-det`.

### B — Lasciare inizio_ora
Allora UC-07 è teatro. No.

**Raccomando A.**
