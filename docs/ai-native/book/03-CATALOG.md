# 03 — Closed catalog
**Owner:** AIUxer · **Status:** ready

Nessun tipo nuovo. La slice A dà *affordance* a tipi che già esistono.

## Types in scope
| Type | Kind | Surfaces | Det/Gen | Authority | Status vs code | Delta slice A |
|---|---|---|---|---|---|---|
| person-shifts | widget | home, pack, candidati gap | Det | `vista.person_shifts` da kb + bozza | none | Come candidato: form `sposta-turno` precompilato. `me` senza overlay della settimana dopo. |
| person-balances | widget | home | Det | `saldi.di` | none | invariato |
| coverage-gap | widget | home manager | Det | mapping forecast vs piano | none | A1: ogni riga è un atto. A2: i candidati stanno sotto *quella* riga |
| compliance-block | widget | home, approval | Det | Compliance | none | A2: `violazioni` = atto (`sposta-turno`). `segnalazioni` = testo. Continua a togliere `pubblica` |
| proposal-pack | widget | home manager | Det* | Scheduling → vista | none | tetto `MAX_TOCCATI`; chip del pack si disegnano (oggi calcolate e non renderizzate) |
| rationale | widget | home, copilot | Gen copy | Copilot / mapping | none | sui candidati: copy **det** («N liberi il …; i riposi non si toccano») |
| diff-edit | widget | pack | Det | `bozza.diff` | none | invariato |
| scheda-preview | widget | copilot | Det* | privacy.deriva_vincolo | none | invariato (pattern visivo da copiare nello shell) |
| secondo-note | widget | home | Det | kb/secondo | none | invariato; non è questa slice |
| copilot-turn | widget | home | Gen | Copilot | none | `motivo` distingue `giu` / `non-configurato` / `schema` |
| week-grid | widget | /tabellone | Det | `vista.week_grid` | diverged → allineare | settimana del ciclo; overlay se bozza |
| consulta | chip | gap, pack, copilot | Det | handler | none | da no-op a «mostra candidati / persona» |
| sposta-turno | chip | candidato, guscio | Det | `ciclo.sposta_turno` | none | campi obbligatori + conferma. Chip nuda nel guscio: nascosta o disabilitata. |
| accetta-bozza, rifiuta-bozza, pubblica | chip | stato-ciclo, pack | Det | ciclo | none | aprono approval **inline**; `scegli-variante` solo se N>1 |
| apri-tabellone | chip | stato-ciclo | Det | redirect | none | target = settimana ciclo |

Atomi (`orario`, `etichetta-mansione`, `badge-stato`, `nome-persona`, `giorno`): invariati. `giorno` resta senza data in questa slice (P2 deferred).

## LLM-selectable set
`catalogo.WIDGET_SELEZIONABILI_LLM` (immutato):

`person-shifts` · `person-balances` · `coverage-gap` · `compliance-block` · `proposal-pack` · `rationale` · `diff-edit` · `scheda-preview` · `secondo-note` · `copilot-turn`

**Non** include `week-grid`.

Chip 07 (`invia-attivazione`, `mostra-qr`, `revoca-invito`) restano in `CHIP` ma **non** sono nello slot generativo di questa slice. Non si aggiungono all’enum LLM.

## Renderer / registry set
`catalogo.WIDGET` + `widget.html` macro `render`:

stessi 11 tipi. `week-grid` montabile solo da `/tabellone`.

## Out of catalog (shell)
- stato-ciclo
- composer
- approval card accetta / pubblica / sposta / scollega (chrome, pattern #04)
- landing / attiva / attivatore
- pagina `conferma.html` — **smette di essere casa**. Può restare come template parziale incluso in `home.html`, non come destinazione di navigazione.

## Canary
- [x] selectable ⊆ renderable (già vero; non allargare)
- [x] composition path: tap gap → `consulta` + payload → `vista` monta tipi già nel renderer. L’LLM non sceglie il tipo.
- [ ] chip `consulta` con payload non accetta tipi fuori catalogo (già `filtra_widget`)

## Vietato in questa edition
Inventare `gap-candidates`, `shift-editor`, canvas, HTML libero, un widget «per il manager».

## Loop C1 — nessun tipo nuovo; proposti per ruolo

Il thread **non** entra in catalogo. È chrome del composer (come `stato-ciclo`).

Due montaggi, non si mischiano:

| Dove | Chi decide | Dinamico? |
|---|---|---|
| **Guscio** | codice, ogni GET `/home` | no. Sempre le stesse card. |
| **Filo** | Copilot `compone` → tool det → `vista` | sì. Solo se c’è un fatto o un atto. Zero widget «per riempire». |

`copilot-turn` è la busta. Dentro: 0–n widget del set sotto + 1–3 chip. `suggestion` / `chat-bubble` / `whats-next` restano **fuori** — sono chip.

### Guscio (non proposto)

| Ruolo | Sempre a schermo |
|---|---|
| Lavoratore | `person-shifts(me)` · `person-balances(me)` |
| Direttore | gli stessi due (lui è una persona) + `stato-ciclo`. In `attesa_umano`: `proposal-pack` · `coverage-gap` · `compliance-block` come **briefing A3**, non come chat |

### Proposti nel filo — lavoratore

Tool ⊆ `{mostra_turni, mostra_saldi, prepara_preferenza}`. Bersaglio = sé.

| Widget | Quando il Copilot lo propone | Non |
|---|---|---|
| `scheda-preview` | «non posso», piano, tap su un giorno | write da solo |
| `person-balances` | «quante ferie», ROL, permessi | numeri inventati |
| `person-shifts` | «quando lavoro», «domani», «la settimana» — **solo me** | colleghi |
| `secondo-note` | il negozio ha un fatto *su di lei* | card vuota |
| `rationale` | deve spiegare un no («non vedo i turni degli altri») | prosa al posto dei fatti |

Chip che può proporre: `salva-preferenza` · `apri-scheda` · `collega-google` · `scollega-google` · `aggiorna-saldi` · `consulta` (riapre sé). Mai `genera-bozza` / `pubblica` / `sposta-turno` / `apri-tabellone`.

### Proposti nel filo — direttore

Tool = roster pieno (`mostra_*` + `prepara_preferenza` + `consulta_scheduling` + `consulta_compliance` + `consulta_secondo`). Lui ha anche il set lavoratore, su di sé.

| Widget | Quando lo propone | Non |
|---|---|---|
| `rationale` | «chi copre», «perché Matteo», «il negozio sa» | dump di 5 schede |
| `person-shifts` | ha **nominato** qualcuno, o un candidato di un buco | 30 righe |
| `coverage-gap` | chiede i buchi / «cosa manca» | al posto del tap A3 (il gesto resta sulla home) |
| `compliance-block` | «si può pubblicare?», «chi sfora» | auto-accorciare |
| `proposal-pack` | «chi tocca la bozza» | nuovo Excel |
| `diff-edit` | «cosa cambia su X» | |
| `secondo-note` | «cosa sa il negozio» | |
| `scheda-preview` | una preferenza **sua** | scrivere la scheda di Anna |

Chip in più: `genera-bozza` · `accetta-bozza` · `rifiuta-bozza` · `pubblica` (solo se dual-gate) · `sposta-turno` (proposta, non esecuzione) · `apri-tabellone` · `scegli-variante` se N>1. `week-grid` **mai** montato dal compose — solo la chip.

### Compose: cosa può scegliere il modello
**Tool** ⊆ `tool_per(attore)`. **Widget** ⊆ tabella di ruolo qui sopra (non tutto `WIDGET_SELEZIONABILI_LLM`). **Chip** ⊆ set di ruolo. **Nessun payload**: `vista` mappa tool → tipo. Canary: proposto ⊆ renderer; il path `compone` **onora** il tool.

Un turno senza fatto (tool vuoto, niente da mostrare) = solo testo + chip. Non si inventa un widget.
