# Surface map — TIME MACHINE / Le Rocce — 2026-08-18 — **Azienda**

## Meta
- Non è un loop solo: è il **frame** («parli con Le Rocce»). C1 è la prima slice.
- Scelta precedente: C1 A (thread + compose). Questo documento *allarga* il job, non lo sostituisce.
- Design / impl: stessi root. Sources: Francesco 2026-08-18; `00` §§1–3; `01` ciclo e secondo; `02` catalogo; `05` §4.2 regola della storia; Book C1.

## Roles
| Role | Job nuovo (sue parole) |
|---|---|
| Lavoratore | Chattare con l’azienda; la scheda ricorda; profilo; chiedere/vedere richieste; approvare *la mia* settimana proposta |
| Direttore | Stesso, più: vedere chi ha approvato la propria proposta e chi no |

## Surfaces
| Surface | Family | Oggi | Serve |
|---|---|---|---|
| Copilota | conversational-gen | form / C1 filo | voce **Le Rocce**, non un centralino |
| Scheda persona | det | md + `apri-scheda` | **sommario** conversazione (lei); profilo come widget |
| Home | det guscio | 2 card | invariata al primo paint (U1) |
| Inbox richieste | — | assente (marketplace deferred) | chiedere / vedere |
| Piano proposto (me) | — | overlay bozza solo se manager | widget+chip, **lei** conferma |
| Roster approvazioni | — | assente | solo direttore |

## Runtime agents
Invariati. Il Copilot è **la voce del PV** (P-L). Scheduling/compliance restano system-facing. Secondo-pv impara da *decisioni*, non dal transcript.

Nuovo stato di ciclo (solo se si fa Q1): dopo `attesa_umano` (bozza CCNL-ok) → `attesa_persone` (ognuno vede la propria riga) → direttore vede residuo → `pubblica` resta atto del direttore (dual-gate + residuo visibile, non veto automatico — da chiudere in Book Q1).

## Catalog diff
Tipi **nuovi** = solo-intent finché un Book slice non li approva.

| Type | Kind | Chi | Status | Note |
|---|---|---|---|---|
| copilot-turn | widget | tutti | C1 | busta della voce azienda |
| person-shifts / balances | widget | tutti | none | guscio; nel filo solo sé (lavoratore) |
| scheda-preview | widget | tutti | none | preferenza |
| **`person-profile`** | widget | tutti | **only-intent** | «il mio profilo»: mansioni, vincoli operativi, sommario (solo lei), stato Google |
| **`sommario`** | campo scheda, non widget | sé | **only-intent** | compressione della chat; non è un tipo UI |
| **`richiesta`** | widget | mittente+destinatario | **only-intent** | una domanda a un collega (copri/scambia) |
| **`inbox-richieste`** | widget | tutti | **only-intent** | lista delle *mie* (in/out) |
| **`piano-proposto`** | widget | tutti | **only-intent** *o* `person-shifts` overlay + chip `accetta-piano` | la *mia* settimana dalla bozza pipeline |
| **`roster-approvazioni`** | widget | solo direttore | **only-intent** | chi ha detto sì / chi no / chi non ha aperto |
| coverage-gap / compliance / pack | widget | direttore | none | briefing A3, non chat-casa |
| week-grid | widget | direttore | chip only | invariato |

## Trust boundary hotspots
- Sommario in `kb/persone/{slug}.md`: è **suo** testo (come la storia). Manager e Scheduling vedono **solo operativa**. Compose di Anna carica il sommario; compose di Emilio no.
- Transcript intero: sessione, non kb. Retention log 30g (`05`).
- Richieste: visibili a mittente, destinatario, direttore. Non a Jessica. Niente ranking («Anna rifiuta sempre»).
- Piano proposto: overlay, non pubblicato. `pubblica` resta Emilio. Lei approva *la sua riga*, non il PV.
- Art. 4: roster approvazioni = stato d’atto (sì/no/silenzio), non «Anna è poco collaborativa».

## Gaps that matter
### P0
1. La chat non è l’azienda (C1 — in review).
2. Nessuna memoria sulla scheda → ogni sessione riparte da zero (M1).
3. Nessun profilo come widget (M1).
4. Nessuna richiesta tra persone (R1).
5. La bozza è solo del direttore; il lavoratore non può dire sì alla *sua* settimana (Q1).
6. Emilio non vede chi ha chiuso e chi no (Q1).

### P1
7. U1 vs terza card profilo.
8. Ciclo `01` non ha `attesa_persone`.
9. Marketplace era fuori edizione.

### P2
Streaming, persistenza transcript, secondo che legge le chat (vietato).

## Keystone
**Una voce (Copilot = Le Rocce) + una memoria per persona (sommario in scheda) + una bozza unica della pipeline che ciascuno approva sulla propria riga.** Non 30 pianificatori. Non chat-casa.

## Do NOT touch
U1 primo paint. Dual-gate CCNL. Calcolo ore. Regola della storia (`05` §4.2). A3 gesti buco/blocco. Catalogo chiuso: tipi nuovi solo con Book.

## Proposals (sequenza, non alternative esclusive)

### C1 — Voce (già scelto, Book in review)
Filo + compose. «Parli con Le Rocce». Zero tipi nuovi.

### M1 — Memoria + profilo (recommended next)
- Dopo N turni o a fine sessione: 1 LLM → `{sommario}` schema, write scheda **con conferma** o auto-append solo se è compressione (niente fatti nuovi). Lei vede e può cancellare.
- Compose carica `sommario` + vincoli operativi **suoi**.
- Tipo nuovo `person-profile` (det). Chip `apri-profilo`. Non terza card al primo paint (U1).
- Jobs: il contesto migliora; «chi sono per il negozio» è un widget.

### R1 — Richieste
- Tipi `richiesta` + `inbox-richieste`. «Mi copri gio?» → proposta, write solo se il destinatario conferma. Direttore vede le sue + le aperte del PV.
- Dopo M1 (serve identità/profilo). Authz nuova.

### Q1 — Piano mio + roster
- La pipeline (forecast → scheduling → compliance) produce **una** bozza.
- Ciascuno riceve `piano-proposto` = i *suoi* `person-shifts` overlay + chip `accetta-piano` / `rifiuta-piano` (motivo).
- Direttore: `roster-approvazioni` (sì / no+motivo / silenzio). I no sono atti, come i buchi A3.
- `pubblica` resta Emilio. I no non auto-vetano il CCNL; si vedono.
- **Non** un solver per persona: i piani indipendenti si pestano.

**Ordine: C1 → M1 → R1 → Q1.** Fare Q1 senza voce e senza memoria è un altro Excel.
