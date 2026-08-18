# 05 — Architecture
**Owner:** AIEngineer · **Status:** ready

## Composition contract
Tutto torna su `GET /home`. Nessuna nuova casa.

| Ingresso | Validazione | Effetto | Render |
|---|---|---|---|
| `POST /chip/consulta` + `data,fascia,reparto` | manager; ISO date; fascia ∈ forecast.FASCE; reparto in kb | `_FLUSSO[sid]["candidati_gap"] = vista.candidati_gap(...)` | home: stack `person-shifts` + rationale det |
| `POST /chip/consulta` senza payload | — | no-op → home (come oggi) | |
| `POST /chip/sposta-turno` senza `conferma=1` | campi presenti, parse_cella ok | `_FLUSSO["conferma"] = {azione, campi, domanda}` | home + chrome approval |
| `POST /chip/sposta-turno` `conferma=1` | come sopra | `ciclo.sposta_turno` → `_compliance` | home aggiornata; pulisce conferma e candidati |
| `POST /chip/{accetta-bozza,rifiuta-bozza,pubblica,scollega-google}` senza conferma | — | stesso `_FLUSSO["conferma"]` | home, non `conferma.html` come destinazione |
| `conferma=0` | — | pop `_FLUSSO["conferma"]` | 303 `/home` |
| `POST /copilota` | authz | widget in `_FLUSSO["widget"]`; `copilota_spento` solo se `motivo=="giu"` | |
| `GET /tabellone` | manager | `week_grid(bozza.piano if bozza else piano_ciclo)` | `tabellone.html` |

`enum ⊆ renderer`: immutato. Il path `consulta`/gap chiama `vista`, non l’LLM. `filtra_widget` resta il gate se un giorno il Copilot inietta tipi.

## Registry path
`catalogo.py` → `vista.py` (dict con `tipo`) → `widget.html` `render`. Tipo sconosciuto → stringa vuota (U6).

Nuova funzione, non nuovo tipo:

```
scheduling.candidati_per_gap(piano, data, fascia, reparto, schede) -> list[str]
  layer 1: _candidati (libero, mansione, non R/F/badge)
  layer 2: _movibili  (già in turno quel giorno, altra fascia/reparto) se layer 1 = []
  ordine: _ordine_deterministico
  tetto: MAX_TOCCATI

vista monta person_shifts(slug, oggi=bozza.settimana, bozza=bozza)
handler inietta chip=["sposta-turno"] + campi {persona, data, fascia}
```

Candidati **ricalcolati al tap** sul piano della bozza. Non si cachano sul `Gap` (dopo uno sposta sono stale). Zero JS, zero LLM.

`person-shifts(me)`: `home` passa `bozza=None` sullo slot fisso. Overlay solo nel pack / candidati.

## Deterministic vs LLM
| Path | LLM? | Why |
|---|---|---|
| tap gap → candidati | no | P-B; < 200ms; stesso solver già in `genera-bozza` |
| sposta + compliance | no | CCNL = codice |
| approval chrome | no | |
| tabellone ciclo | no | |
| prosa Copilot | sì, best-effort | mismatch schema → fatti, composer acceso |
| ordine morbido in `genera-bozza` | sì + fallback det | già così; fuori dal tap-gap |

## Persistence
| Stato | Dove | Vita |
|---|---|---|
| ciclo, bozza, pubblicabile, accettata | server (`orchestrator.ciclo`, TM_STATO) | finché la settimana non chiude |
| widget Copilot, candidati_gap, conferma pending | `_FLUSSO[sid]` in-process | sessione; si perde al restart (ok per pilota) |
| preferenza confermata | `kb/persone/{slug}.md` | durable |
| piano pubblicato | `kb/turni/YYYY-MM-DD.md` | durable, immutabile |

Coda: `jobs.Coda.sincrona=True` resta. Async **deferred** (P2 / D4 pagina). Questa slice non fa del loader un requisito: tap-gap e sposta sono sincroni e corti.

## Validazione `sposta-turno`
1. `esigi_manager`
2. `persona` slug in kb; `data` ISO; `fascia` parseabile da `kb.celle.parse_cella`
3. stato ciclo `attesa_umano` e bozza presente
4. Mancano campi → 400 + copilot-turn det «manca il bersaglio», **non** 500
5. Conferma obbligatoria (`CHIP_CON_CONFERMA` già elenca `pubblica` ecc.; **aggiungere** `sposta-turno`)

Chip nuda nel guscio (`CHIP_PER_STATO` senza hidden fields): togliere `sposta-turno` da `CHIP_PER_STATO["attesa_umano"]`. Vive solo sulle card candidato / `diff-edit`.

## Loop C1 — composizione e stato

### Contratto `compone`
Una mossa NL = **un** `genera_json`. Schema:

```
SCHEMA_COMPONI {
  required: [testo, chip]
  testo: string
  tool: "" | enum tool_per(attore)     # 0 o 1
  chip: array[string]                  # 1–3, filtrati a CHIP ∩ ruolo
}
```

Validazione al confine (già `valida` + enum). Tipo widget **non** lo sceglie il modello: `tool` → fetcher det → `vista` → `tipo` già in `WIDGET`. `filtra_widget` resta. Chip fuori enum si droppano, non si «correggono».

Prompt: enunciato, ultimi k≤4 turni (solo `testo` + `tipo` widget, **non** storie private di colleghi), allowlist tool/chip. `allowlist.blocco_dati` sul testo utente.

### Stato
| Cosa | Dove | Vita |
|---|---|---|
| `conversazione[]` | `_FLUSSO[sid]` | sessione; cap **8** turni copilota (i più vecchi cadono) |
| enunciato umano | stesso array, `{ruolo:umano,testo}` | come sopra |
| kb / audit | invariati | write solo da chip confermate |

Restart = filo perso (come oggi i widget). Ok per pilota. Non si scrive in `kb/`.

### Path HTTP
`POST /copilota` appende, non sostituisce. 303 `/home#copilota`. Render: composer elenca la storia; widget del turno *dentro* la card.

Tap cella / `salva-preferenza`: appendono un turno (preview o chiusura), non svuotano il filo.

### Deterministic vs LLM (C1)
| Path | LLM? |
|---|---|
| NL → turno | sì, 1× `compone` |
| tool scelto (preferenza, saldi, turni, consulta_*) | no |
| chip write + turno di chiusura | no (tabella next, C1.3) |
| tap gap / sposta / pubblica | no (A3, invariato) |
| LLM giù / fake senza copione | `_intent_det` + fatti, `motivo` già esistente |

`TM_LLM=fake` nei test: si scripta `SCHEMA_COMPONI`. La demo che si *sente* non usa `fake`.

## Key modules (paths, impl root)
- `timemachine/web/app.py` — handler chip, home, tabellone, `_conferma` → flusso
- `timemachine/web/templates/{home,widget,conferma,tabellone}.html`
- `timemachine/vista.py` — `candidati_gap`; `person_shifts(..., bozza=)` solo se `bozza.settimana` interseca l’orizzonte di `oggi`
- `timemachine/agents/scheduling.py` — `candidati_per_gap`
- `timemachine/agents/copilot.py` — `_copy` motivi
- `timemachine/domain/catalogo.py` — `CHIP_CON_CONFERMA` + `sposta-turno`
- `timemachine/orchestrator/ciclo.py` — `CHIP_PER_STATO` senza chip nuda
- `tests/test_u_genui.py` + nuovi casi in 07
