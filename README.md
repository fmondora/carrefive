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

Con `TM_LLM=fake` (default) gli agenti girano **senza rete**: forecast,
scheduling e compliance sono codice, l'LLM serve solo per la prosa e per
interpretare le note libere. `TM_LLM=cli|api` accende il modello vero.

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

## Come si progetta

Plugin [`ai-native`](https://github.com/fmondora/AI-Engineering): **AIUxer** (superficie) e **AIEngineer** (architettura, costo, evals).

```
surface-map  →  scelta  →  project-book  →  implementazione da Book §09
```

Niente codice di catalogo finché il Book slice non è approvato. Dettaglio per gli agenti: `AGENTS.md`.

## Fuori da questa edizione

Payroll interno, multi-store, secondo personale, scoring individuale, Outlook/Apple, rilevazione biometrica.
