# 02 — Surfaces
**Owner:** AIUxer · **Status:** ready

## Roles × surfaces
| Role | Surface | Family | Entry |
|---|---|---|---|
| Dipendente | Home persona | dashboard-deterministic + composer | `GET /home` |
| Manager | Home persona + stato ciclo + pack + gap | hybrid | `GET /home` |
| Manager | Approval (inline) | dashboard-deterministic | iniettata in `/home` via `_FLUSSO["conferma"]` |
| Manager | Tabellone (vista rara) | dashboard-deterministic | `GET /tabellone` — **settimana del ciclo** |
| Tutti | Copilot | conversational-generative | `POST /copilota` — unico slot gen |
| Attivatore / landing / scheda | invariati | det | fuori slice |

Due famiglie restano distinte e etichettate. La conferma **non** è più una terza casa (`/chip/accetta-bozza` come pagina). È chrome sulla home.

**Non è una dashboard conversazionale.** Chat = casa è vietata. Il Copilot è lo **slot generativo**: parla, inietta widget *nel* filo, non è la home.

### Loop C1 — lo slot è una storia

P1 ha fatto del composer un **gateway one-shot** (form → 303 → 0–1 card). `02` §4.1 lo chiama già *rail / pannello conversazionale*. C1 costruisce quello.

| Role | Surface | Family | Entry |
|---|---|---|---|
| Tutti | Home persona | dashboard-det (guscio) | `GET /home` — **invariata** |
| Tutti | Copilota | conversational-generative | composer su `/home` + `POST /copilota` — **storia**, non ultimo colpo |
| Manager | briefing A3 | hybrid, gesti | invariato. I tap gap/blocco **non** passano dal filo |

Contratto di superficie C1:

1. Il composer mostra gli ultimi N turni (`copilot-turn`), dal più vecchio al più nuovo, sopra il campo. Il messaggio dell’umano è chrome del filo (non un tipo).
2. I widget del turno (`scheda-preview`, `person-balances`, `rationale`…) si montano **dentro** quel `copilot-turn`, non XOR al suo posto.
3. Le chip del turno *sono* il what's next. Stesso vocabolario `CHIP`. Testo libero resta acceso.
4. Un tap sulla cella (P2) apre la preview *come turno nuovo* nel filo, stesso contratto.
5. In `attesa_umano` i gesti A3 restano sulla home. Il filo non assorbe i buchi.

Trust C1: testo libero in sessione, non in `kb/`. Write solo chip+preview. Allowlist Anna = sé.

### Loop P1 — gateway + cella

- Composer: NL → enum intent (`preferenza` · `turni_miei` · `saldi` · `copri` · `comando_ciclo` · `saluto` · `sconosciuto`) → `consult` / fetch. `saluto`/`sconosciuto` non chiamano Scheduling.
- Anna: allowlist su di sé. Tap giorno = intent `preferenza`.
- Manager: stesso gateway, roster `01` §4.3.
- Chip = intent. Write solo conferma.

### Gerarchia in `attesa_umano` (emendamento A)

Quando c’è una bozza, la regola Bozza vince sulla regola Landing. Stesso `/home`, stesso catalogo, ordine diverso (P-G):

1. stato-ciclo (settimana *del ciclo*, chip del ciclo)
2. approval pending, se c’è
3. `compliance-block` se c’è — l’occhio prima della mano
4. `coverage-gap` — ogni riga è un atto
5. `proposal-pack` — chi la bozza tocca, tetto 8
6. `person-shifts(me)` + `person-balances` — guscio, *in fondo*. Settimana in corso, niente overlay della settimana dopo

Fuori da `attesa_umano` (idle / monitora): resta la landing persona, come Anna. Il Copilot non è mai la porta per coprire un buco.

### Loop A3 — residuo, non muro

I buchi non vetoano `pubblica`. In `attesa_umano`:

- Card `coverage-gap`: prima riga = «N buchi · non bloccano»; una riga primaria aperta; il resto collassato.
- Approval accetta/pubblica: «restano N buchi» in testa. Non è un blocco.
- Dopo `sposta` confermato: aprire il prossimo buco copribile (stesso path `consulta`), non il muro di 15.

### Loop A2 — il blocco e il buco tappato

In `attesa_umano`, dopo A1:

- Tap su una **violazione** di `compliance-block` (non su una segnalazione) inietta `person-shifts` di quella persona (settimana ciclo, senza `adesso` finto) + chip `sposta-turno` sulle celle utili a sciogliere il flag.
- Tap su un gap: i candidati si montano **sotto quella riga**. Il resto della lista può restare, ma non *sopra* il risultato.
- Card candidato: giorno del buco + badge layer 2 + form. Vietato usare `adesso` per un giorno che non è `tempo.oggi()`.
- `sposta-turno` **sostituisce la cella-giorno**, non aggiunge un pezzo. La preview dice cosa si perde («Mara mar 10-14 → 16-20»), non solo la destinazione.

### Anna non è un manager in piccolo

Le due card (`person-shifts` + `person-balances`) **sono** la sua dashboard di widget (`02` spec §4.3 Stop; UC-06; U1). Non si allarga in questa edition «per equità». Gap / pack / blocco sono famiglia *insieme* — lei non ha quel job. Una composizione più ricca (`secondo-note` se la tocca, `diff-edit` se il pubblicato le contradice una preferenza) è una slice **dopo**, e solo se il fetcher ha un fatto. Non un terzo widget vuoto al primo paint.

## Trust boundary
| Surface | Hidden pre-decision | Confirm-only actions |
|---|---|---|
| Home (lettura) | niente retributivo altrui; gap senza nomi di chi è in riposo come «disponibile» | — |
| Gap → candidati | chi è in `R`/`F` non entra nella lista (decisione del manager, non del solver) | scegliere un candidato non scrive finché non conferma `sposta-turno` |
| Approval inline | — | `accetta-bozza`, `rifiuta-bozza`, `pubblica`, `sposta-turno`, `scollega-google` |
| Tabellone | — | non pubblica da lì. Vista. |
| Copilot | — | tool → Proposta / widget. Mai write. |

`pubblica` resta assente se non `accettata ∧ pubblicabile` (`ciclo.py:74-82`).

## Shell vs generative
| Element | shell-not-catalog | notes |
|---|---|---|
| guscio (nome, PV, logout) | sì | `home.html` |
| `person-shifts(me)` fisso | sì (montaggio); tipo è catalogo | settimana **in corso**. Mai overlay della bozza della settimana *dopo*. |
| `person-balances(me)` | sì (montaggio) | |
| stato-ciclo | sì | chip del ciclo, verità server |
| approval card accetta/pubblica/sposta | sì | stesso primitive Beautiful UI #04 di `scheda-preview`, ma **non** è un tipo nuovo: è chrome come `stato-ciclo` |
| composer | sì | spento solo su `LLMGiu` vero |
| Copilot-turn + widget iniettati | no — catalogo | unico slot gen |
| `week-grid` | catalogo, non LLM-selectable | solo chip `apri-tabellone` |

## Flows (happy path)

### Coprire un buco
1. Manager in `attesa_umano`. Vede `coverage-gap` (lista).
2. Tap su una riga (data, fascia, reparto).
3. Stessa home: stack corto di `person-shifts` dei candidati. Prima i *liberi* (layer 1). Se nessuno: chi è già in turno *quel* giorno in un’altra fascia/reparto, stessa mansione (layer 2), etichettati «già in turno — confermi lo spostamento». Mai R/F. Tetto = `MAX_TOCCATI` (8). Se ancora 0: card onesta + form `sposta-turno` a mano.
4. Su un candidato: form `sposta-turno` (persona, data, fascia già valorizzati).
5. Preview chrome: «Metto {nome} il {giorno} in {fascia} su {reparto}?»
6. Conferma → `ciclo.sposta_turno` → ri-compliance → pack/gap/blocco aggiornati. Composer e casa persona restano.

### Accettare / pubblicare
1. Chip `accetta-bozza` apre approval **sulla home** (chi è toccato, avvisi, blocco se non pubblicabile).
2. Annulla pulisce `_FLUSSO["conferma"]` e resta su `/home`.
3. Conferma → `accetta`. Se `pubblicabile`, compare `pubblica`. Stesso pattern.
4. `pubblica` scrive `kb/turni/`. Dual gate intatto.

### Tabellone
1. `apri-tabellone` → settimana del ciclo. Se c’è bozza, griglia della bozza + segni overlay dove ≠ pubblicato allineato per weekday.
2. `chiudi` → `/home`. Non è stato del ciclo.

### Composer
1. Path det (preferenza, consulta, comando) con `SchemaNonRispettato` o `LLMNonConfigurato`: fatti a schermo, composer **acceso**.
2. `LLMGiu` (backend c’era e non risponde): «Copilota non disponibile», composer spento. I widget det restano.

## Cosa non succede più
- `POST /chip/sposta-turno` senza campi → 500.
- `Annulla` che riposta `conferma=0` e rirenderizza la preview.
- Tabellone del 29/06 mentre il ciclo è 06/07.
- Overlay della bozza *prossima* sul `person-shifts` di Francesco *questa* settimana.
- Composer spento dopo «giovedì ho pianoforte».
