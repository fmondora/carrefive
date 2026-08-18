# Surface map — TIME MACHINE / Le Rocce — 2026-08-17 — **P1**

## Meta
- Loop id: **P1** (persona). Non è A3.
- A1–A3 = manager. Shippato fino a `89cdf05`.
- Design / impl: stessi root di A3.
- Sources: live Francesco («ciao!», casa scarna); `copilot.py:141-232`; `home.html` ramo non-attesa; spec `00` UC-02, `02` UC-06/07; Book 02 Anna; AIUxer 2026-08-17.

## Roles
| Role | Surfaces | Job vero |
|---|---|---|
| Dipendente | home 2 card + composer cieco | **Legge.** Non programma. |
| Manager | briefing A3 | Chiude la settimana. Non è questo loop. |

## Surfaces
| Surface | Family | Jobs | Stato |
|---|---|---|---|
| Home Anna | det | Vedere i *miei* turni | Funziona (UC-06) |
| Composer | dovrebbe essere gen | Regole, spostamenti, saluto | Router regex. «ciao!» = consulta scheduling + 403 colleghi = sembra nulla |
| (manca) Gesto sulla cella | det | «quel giorno no» | Celle non cliccabili |
| (manca) Inbox cover | det | «il negozio ti chiede di coprire» | `coverage-gap` è del manager |

## Runtime agents
Copilot `user_facing`. Per Anna, l’`else` (`copilot.py:218`) lo fa parlare *come* Scheduling. P-L storto sul path sconosciuto.

## Catalog diff
Niente tipi nuovi obbligatori. Manca affordance su tipi esistenti.

| Type | Per Anna oggi | Per P1 |
|---|---|---|
| person-shifts | sola lettura | tap giorno → `scheda-preview` |
| person-balances | lettura | chip ferie (già path saldi) |
| scheda-preview | solo se regex | da tap + da NL |
| copilot-turn | sotto il fold, o vuoto | fallback onesto + chip chiuse |
| coverage-gap | 403 / assente | **fuori P1** (inbox cover = P2) |

## Trust boundary
Anna **non** pubblica e **non** si assegna un turno. Dichiara vincolo / chiede. Write scheda solo con `salva-preferenza`.

## Gaps
### P0
1. Non si programma il proprio tempo: nessun tap, chat opaca.
2. «ciao!» e ogni NL fuori regex = path manager svuotato.

### P1
3. Zero chip sul proprio widget (`consulta` no-op).
4. Composer fixed / risposta sotto le card.

### P2
Inbox «copri questo buco» (pipeline → lei). Marketplace swap. Font.

## Keystone
**Il Copilot è il gateway della pipeline.** NL → intent chiuso → `consult(agente)` o fetch det → widget del catalogo. Non è la casa. Non è un `if pianoforte`.
La cella è il gesto *muto* dello stesso contratto (stesso intent `preferenza`, senza passare dalla regex).

## Do NOT touch
Casa due card. Catalogo. Dual gate manager. A3 residuo.

## Proposals
### A — Gateway + cella (recommended)
Copilot classifica intent in enum chiuso ⊆ chip/tool (`preferenza` · `turni_miei` · `saldi` · `copri` · `comando_ciclo` · `saluto` · `sconosciuto`). Poi `consult` o fetch. «ciao!» = `saluto` + chip, mai Scheduling. Tap cella = stesso intent `preferenza`. Anna: allowlist senza turni altrui. Manager: pipeline piena. `one-llm-turn` per l’intent, resto det.

### B — Terza card disponibilità
Settimana vuota da cliccare posso/no. Tipo nuovo. No: #23, non prima di A.

### C — Warning cover in home Anna
`coverage-gap` filtrato. Job vero, loop dopo (P2). Authz nuova.

**Raccomando A.**
