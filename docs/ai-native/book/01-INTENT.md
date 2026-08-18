# 01 — Intent
**Owner:** AIUxer · **Status:** ready

## Loop C1 — continuare, non solo dichiarare

P1 ha sbloccato *un* atto (preferenza / ciao). Il job che manca: **restare nella stessa conversazione** e sapere il passo dopo.

| Job | Who | Success looks like |
|---|---|---|
| Dire una cosa e continuare | dipendente | «suono il piano il giovedì» → turno con preview *dentro* il filo. Conferma. Il filo resta. Una seconda frase («e il sabato?») vede la prima. |
| Sapere il what's next | tutti | Ogni turno chiude con 1–3 chip del catalogo, non col campo vuoto. Dopo «salvato»: «collega Google» / «apri scheda» / tace solo se non c’è una mossa lecita. |
| Chiedere sul piano senza Excel | manager | «chi copre giovedì?» → rationale + chip, *nel* filo. Non un form one-shot. Scheduling non parla. |
| (invariato) Vedere i *miei* turni al primo paint | tutti | U1. Chat non è la casa. |

### Outcome metrics (C1)
| Metric | Surface | Notes |
|---|---|---|
| Turni visibili dopo 2 enunciati | composer | ≥ 2 `copilot-turn` nel DOM. Amnesia al POST = fail. |
| Chip sull’ultimo turno | composer | 1–3, ⊆ CHIP ∩ ruolo. 0 chip solo se `sconosciuto` e niente mossa lecita. |
| Path regex su NL con modello su | copilota | 0. Regex solo se LLM giù (P-D). |
| Primo paint Anna | home | U1 invariato: due card, zero thread. |
| Write autonome | — | 0. Conferma resta. |

### Maturity target (C1)
**L2** sullo slot conversazionale: il sistema *compone* tipi e propone il passo dopo. Non L3: non anticipa «domenica pizze» da solo. Non L4.

L’intelligenza nuova è **di composizione**. Ore, vincolo, CCNL restano codice.

### Non-goals C1
- Chat-casa (map B).
- Tipo `suggestion` / `chat-message` / HTML libero.
- Allargare l’enum intent a nomi di agenti.
- Streaming, persistenza disco della chat, P3.

---

Slice A. Il prodotto esiste; il job del manager no.

## Jobs-to-be-done
| Job | Who | Success looks like |
|---|---|---|
| Coprire un buco della settimana che arriva, senza Excel | manager | Tap sul gap → vede 1–N persone (libere, o già in turno in un’altra fascia) → sceglie → preview → conferma. Resta sulla home. I riposi non si propongono da soli. |
| Sistemare un turno che Compliance ha flaggato | manager | `sposta-turno` ha bersaglio e fascia, non 500. Dopo lo spostamento: ri-compliance, `pubblica` assente se ancora bloccato. |
| Accettare o rifiutare la bozza sapendo chi è toccato | manager | Approval card *nella* home (come `scheda-preview`). Annulla torna alla casa, non al loop. |
| Pubblicare solo se è pubblicabile | manager | Dual gate: accettata ∧ `pubblicabile`. Preview elenca chi cambia. |
| Guardare il foglio della *bozza*, se serve | manager | `apri-tabellone` = settimana del ciclo, overlay bozza. Chiudi → home. Non è landing. |
| Parlare due volte al copilota | tutti | Dopo una preferenza o una consulta, il composer resta acceso se il path det ha funzionato. |
| (invariato) Sapere i *miei* turni di oggi e i prossimi | dipendente / manager-come-persona | U1 non si tocca. `person-shifts(me)` = settimana *in corso*, senza overlay della bozza *prossima*. |

## Outcome metrics (distributions)
| Metric | Surface | Notes |
|---|---|---|
| Tempo da «vedo un buco» a «bozza aggiornata» | home manager | Target pilota: < 2 min per un buco. Non 3–6 h del foglio. |
| Sessioni manager che aprono `week-grid` | home → tabellone | `02` §2: < 10%. Se dopo A resta alta, il gesto sui gap non basta — emendare, non insistere. |
| 500 su chip di write | `/chip/sposta-turno` | 0. |
| Composer spento dopo path det riuscito | home | 0. Spento solo se backend AI è giù. |
| U1 Anna (primo paint) | home dipendente | Invariato: `person-shifts` + `person-balances`, zero `week-grid`. |
| Violazioni pubblicate | ciclo | 0 (E4 / U4 restano). |

## Maturity target (this slice)
**L2** sul ciclo (accetta / modifica / rifiuta / pubblica → secondo-pv impara). Non L4: il sistema non anticipa «copri pizze domenica» da solo.

L’intelligenza di questa slice è **deterministica**: i candidati del buco sono codice (`scheduling._candidati`). L’LLM non entra nel gesto.

## Non-goals
- Nuovi tipi di catalogo (`copri-buco`, canvas, HTML libero).
- Due home (direzione B).
- Far compilare allo Scheduling una settimana intera da zero (è un altro slice; qui si *usa* la bozza che c’è).
- Togliere il tabellone.
- Font / igiene visiva (P2), salvo copy delle chip che questa slice tocca.
- On-behalf: il manager non scrive la scheda o il calendario di Anna.
- Far eseguire `sposta-turno` al Copilot.
