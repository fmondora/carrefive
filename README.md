# TIME MACHINE

Sistema agentico + GenUI per i turni di un punto vendita GDO.

Pilota: **Le Rocce**, Poggiridenti. Invariante: **l'AI propone, l'umano dispone, il calcolo è deterministico.**

Il runtime implementa le spec `01`–`07`: pacchetto `timemachine/`, superficie web,
CLI `tm`. Le evals delle spec sono la suite di test.

## Come si prova

```bash
python3.12 -m pip install -e ".[dev]"

python3.12 -m pytest -q     # le evals E, U, C, S, G, D, L + i 22 use case
./demo.sh                   # http://127.0.0.1:8770 — landing, poi la home persona
```

`demo.sh` copia `kb/` in una directory usa-e-getta (l'archivio del pilota non si
tocca), attiva due account — `anna@lerocce.it` e `francesco@lerocce.it`, password
`settelune2026` — e ferma l'orologio a lunedì 29/06/2026 14:05, che è la
settimana pubblicata in `kb/turni/`: così «Adesso» è un turno davvero in corso.

Anna è una dipendente, Francesco è manager e attivatore (l'Emilio di `07`).

Primo giro a mano:

```bash
tm ruolo francesco --aggiungi manager attivatore   # Emilio: attiva ed è manager
tm invita anna-mondora --da francesco --email anna@example.com
tm bozza --settimana 2026-07-06 --da francesco     # genera, non pubblica
tm import-saldi --file export-studio.csv --at 2026-08-16
tm scan --ci                                       # matcher di sicurezza (`05`)
```

### Il copilota

Il backend del modello si sceglie da solo, in quest'ordine:

1. **la chiave**, se l'SDK ne risolve una — `ANTHROPIC_API_KEY`,
   `ANTHROPIC_AUTH_TOKEN` o il profilo di `ant auth login`, la stessa catena
   che usa Claude Code. Modello di default `claude-opus-5`.
2. **la CLI** `claude -p`, se è nel PATH — il caso normale in sviluppo su una
   macchina già autenticata.
3. **niente modello**: il sistema funziona lo stesso e lo dice. Forecast,
   scheduling e compliance sono codice; senza modello si perdono solo la prosa
   del copilota e l'interpretazione delle note libere della testata.

| Variabile | Effetto |
|---|---|
| `TM_LLM=fake\|cli\|api` | forza la scelta (i test usano `fake`: nessuna rete) |
| `TM_LLM_CLI` | comando della CLI, es. `"claude -p --model haiku"` |
| `TM_MODELLO`, `TM_EFFORT` | modello e effort del backend `api` |

Una nota di misura: `claude -p` risponde in **~38 s** a una richiesta del
copilota su questa macchina. Va bene per provare, è troppo per un composer
sincrono — chi ci lavora a lungo punti `TM_LLM_CLI` a un modello più rapido.

Dettaglio: [`docs/architettura.md`](docs/architettura.md) ·
[`docs/security/README.md`](docs/security/README.md).

## Cosa stiamo costruendo

Un loop settimanale — prevedi, proponi turni, verifica CCNL, il manager decide, pubblica, monitora — con agenti specialisti e un orchestratore **deterministico**. L'interfaccia non è il tabellone Excel: ogni persona ha sempre a schermo i *suoi* turni (adesso e quelli che arrivano). Il foglio resta come storia in `kb/turni/`.

I turni pubblicati possono finire sul calendario Google della persona.

## Specs

Si costruisce da qui, non dalla chat. Come si scrive una spec: `specs/README.md`.

| Spec | Contenuto |
|---|---|
| [00 — visione e principi](specs/00-high-level.md) | Mercato, MoSCoW, KPI, i 4 principi fondanti e i 12 sull'AI |
| [01 — sistema agentico](specs/01-sistema-agentico.md) | Contratto agenti, orchestratore, knowledge, evals |
| [02 — GenUI](specs/02-genui.md) | Superficie persona-first, catalogo chiuso, chip |
| [03 — calendario Google](specs/03-calendario-google.md) | OAuth, sync dei soli turni pubblicati |
| [04 — ferie e permessi](specs/04-ferie-permessi-gamma.md) | Montante in kb (file), poi tempo reale da Gamma |
| [05 — security e GDPR](specs/05-security-gdpr.md) | Cosa condivide il dipendente; authz; DeepSec |
| [06 — design system](specs/06-design-system.md) | Beautiful UI + fresco; token; mappa primitive |
| [07 — landing e attivazione](specs/07-landing-attivazione.md) | Emilio invita (mail/QR); uid/pwd o Google |

## Knowledge (pilota)

Markdown, leggibile da un umano. Tre famiglie:

- `kb/persone/` — scheda di ciascuno: contratto, mansioni, preferenze
- `kb/turni/` — settimane pubblicate (22/06 e 29/06/2026) + foto dei tabelloni
- `kb/saldi/` — montante ferie/permessi (file ora; snapshot Gamma dopo)
- `kb/secondo/` — memoria collettiva del negozio (ancora vuota)

Mappa colori → reparti: `kb/reparti.md`.

## Runtime

| Pezzo | Dove | Nota |
|---|---|---|
| Knowledge | `timemachine/kb/` | parser e writer del markdown; il tabellone resta la storia |
| Dominio | `timemachine/domain/` | turni, ore, saldi, catalogo chiuso, grounding gate |
| Agenti | `timemachine/agents/` | forecast · scheduling · compliance (zero LLM) · anomaly · copilot · secondo-pv |
| Orchestratore | `timemachine/orchestrator/` | macchina a stati, contesto con budget, coda job |
| Adattatori | `timemachine/saldi/`, `timemachine/calendario/`, `timemachine/auth/` | Gamma, Google, identità |
| Sicurezza | `timemachine/security/` | authz, allowlist di prompt, audit, diritti, matcher |
| Superficie | `timemachine/vista.py`, `timemachine/web/` | dominio → tipi del catalogo → HTML |

Il confine di fiducia è verificato dal codice: i moduli deterministici non
importano gli agenti (`tests/test_confine.py`), e solo il gate `pubblica`
scrive in `kb/turni/`.

## Ciclo di sviluppo

Si costruisce dalle spec, non dalla chat. Ogni giro ha un **id** (`A1`, `P2`…)
citato uguale in spec, Book e commit. Indice: [`specs/LOOPS.md`](specs/LOOPS.md).

Plugin [`ai-native`](https://github.com/fmondora/AI-Engineering): **AIUxer**
(superficie, *desiderabile*) e **AIEngineer** (orchestratore, costo, evals,
*fattibile*). Le due lenti possono divergere: l'arbitro è l'esito misurato;
su pubblicazione turni e dati retributivi il confine ha veto.

```
surface-map  →  scelta direzione  →  project-book  →  ok  →  impl da Book §09
       ↑                                                         │
       └──────── live + evals  →  emenda spec `## Loop <id>` ────┘
```

1. **Surface map.** Inventario di ciò che c'è (ruoli, widget, chip, gap
   spec↔codice) e due o tre direzioni. Output in `docs/ai-native/surface-maps/`.
2. **Scelta.** Una direzione, un id nuovo. Non si parte in parallelo su due loop.
3. **Project book.** Sintesi dual-lens + delta rispetto al giro prima. Le slice
   shippabili stanno in `docs/ai-native/book/09-IMPL-READY.md`. Le `specs/0N-*.md`
   restano source of truth: il Book non le sostituisce.
4. **Approvazione.** Niente codice di catalogo, niente tipo nuovo, niente
   allargamento di enum, finché il Book di quel loop non è approvato.
5. **Implementazione.** Solo le slice di §09. Le evals della spec **sono** i
   test (`E` in `01`, `U` in `02`, …). Toccare una spec senza il suo file di
   test è un lavoro non finito. Poi si prova sull'app, non solo `pytest`.
6. **Chiusura.** Sezione `## Loop <id>` in coda alla spec toccata — non si
   riscrive il corpo storico. Riga nuova in `LOOPS.md`. Il giro dopo riparte
   dalla mappa, non da una chat.

Un loop è chiuso quando l'esito si vede in casa (Anna o Francesco), non quando
il brief è scritto. Dettaglio per gli agenti: `AGENTS.md`. Come si scrive una
spec: `specs/README.md`.

## Fuori da questa edizione

Payroll interno, multi-store, secondo personale, scoring individuale, Outlook/Apple, rilevazione biometrica.
