# TIME MACHINE — Le Rocce

Sistema agentico + GenUI per i turni del punto vendita. Pilota: Le Rocce, Poggiridenti.

## Principi
Leggi `specs/00-high-level.md` §§2–3 prima di qualsiasi spec o codice.
Invariante: **l'AI propone, l'umano dispone, il calcolo è deterministico.**

## Costruzione (plugin `ai-native`)
- **aiuxer** — superfici, catalogo, GenUI (*desiderabile*).
- **aiengineer** — orchestratore, evals, costo, affidabilità (*fattibile*).
- Pipeline: `surface-map` → scelta direzione → `project-book` → implementazione da Book §09.
- Le `specs/0N-*.md` restano source of truth. Il Book (quando esiste) è sintesi dual-lens + delta.

## Surface map paths
- Specs: `specs/`
- Knowledge: `kb/persone/`, `kb/turni/`, `kb/saldi/`, `kb/reparti.md`, `kb/secondo/`
- Catalog / types: (non ancora — nascerà con `02`)
- Renderer: (non ancora)
- Runtime agents: (non ancora)
- Shell: (non ancora)
- Design root: questo repo

## Design system
Prima di qualsiasi UI: `specs/06-design-system.md`. Carta, foglia, Fraunces + Source Sans 3. Grammatica [Beautiful UI](https://www.beautifului.dev/), non la libreria. Catalogo tipi in `02`.

## Security
Vincoli in `specs/05-security-gdpr.md`. `kb/` = dati personali. Secret solo come nome di env. Quando c'è runtime: DeepSec `process --diff` in CI.

## Convenzioni
- Lingua: italiano.
- Git locale; nessun push senza richiesta.
- python3.12 per CLI e server.
