# Surface map — TIME MACHINE / Le Rocce — 2026-08-17 — **P2**

## Meta
- Loop id: **P2**
- P1 shippato: `251ab6a`, 98+ canary, live `:8770`
- Sources: live Anna ciao + tap gio; `copilot.py` INTENT/`copri`; `deriva_vincolo`; AIUxer P2

## Roles / surfaces
Anna: due card + composer gateway + tap giorno. **Dichiara.** Non pubblica.
Manager: invariato A3 + `copri` → sotto-router scheduling/compliance/secondo.

## Catalog
Niente tipi nuovi. `scheda-preview` e `Preferenza.data` già esistono.

## Trust
Write solo `salva-preferenza`. Anna allowlist. «ciao!» non gira Scheduling. Live ok.

## Cosa P1 ha chiuso
- Gateway: «ciao!» → saluto + chip, 0 colleghi, composer acceso. Live.
- Tap `gio 7-16` → preview. U1 senza preview al primo paint.
- Allowlist prima della chiamata.

## Gaps P2
### P0
1. **Tap promette una data, salva una ricorrenza.** Storia «giovedì 02/07 non posso», vincolo `no_turno: gio` (tutti i gio). `Preferenza.data` = firma, non scope. Preview non dice «tutti i giovedì».

### P1
2. Saluto: una sola chip `apri scheda` (Book voleva anche non-posso / ferie).
3. Composer in mezzo, risposta sotto; «Nessun modello configurato» sul saluto.
4. `copri` manager ancora può dumpare 5 `person-shifts` colleghi.
5. Overlay visivo sulla riga gio tappata (testo illeggibile live).

### P2 (loop dopo)
Inbox cover. Marketplace. Enum allargato a nomi-agente: **no**.

## Keystone
**Cella = quella data.** Tap → vincolo sul ISO. Chip extra «tutti i gio» se serve la ricorrenza. NL «giovedì ho pianoforte» resta settimanale (U5).

## Do NOT touch
Due card. Enum 7 valori. `copri` come ombrello dominio. Dual gate. A3.

## Proposals
### A — Data sul tap (recommended)
`Preferenza.data` = giorno toccato; `viola()` lo legge. Preview: «solo il 02/07». Seconda chip: «tutti i giovedì» (vincolo weekday, data vuota). Zero tipi.

### B — Allargare enum a compliance/secondo
No. Vocabolario a strati. Ratificare sotto-router in `copri`.

### C — Hygiene P1
Chip ferie sul saluto; dump `copri` manager = rationale only; fix overlay riga.

**Raccomando A** (+ C nello stesso PR).
