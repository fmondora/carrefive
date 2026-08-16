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
- Catalog / types: `timemachine/domain/catalogo.py`
- Renderer: `timemachine/vista.py` + `timemachine/web/templates/widget.html`
- Runtime agents: `timemachine/agents/` (roster chiuso), orchestratore in `timemachine/orchestrator/`
- Shell: `timemachine/web/templates/home.html`, `timemachine/web/app.py`
- Design root: `timemachine/web/static/tokens.css`
- Mappa completa: `docs/architettura.md`

## Design system
Prima di qualsiasi UI: `specs/06-design-system.md`. Carta, foglia, Fraunces + Source Sans 3. Grammatica [Beautiful UI](https://www.beautifului.dev/), non la libreria. Catalogo tipi in `02`.

## Security
Vincoli in `specs/05-security-gdpr.md`. `kb/` = dati personali. Secret solo come nome di env.
In CI gira `tm scan --ci` (matcher di dominio, storia append-only in `docs/security/findings/`);
DeepSec `process --diff` quando il repo si onborda.

## Runtime
- Pacchetto `timemachine/`, CLI `tm`, server FastAPI. Test: `python3.12 -m pytest -q`.
- Le evals delle spec **sono** la suite: E (01), U (02), C (03), S (04), G (05), D (06), L (07).
- Toccare una spec senza toccare il suo file di test è un lavoro non finito.
- Backend LLM astratto: `TM_LLM=fake|cli|api`. Il default `fake` non fa rete.
- Confine di fiducia verificato in `tests/test_confine.py`: i moduli deterministici
  non importano `agents/`, e solo `pubblica` scrive in `kb/turni/`.

## Convenzioni
- Lingua: italiano — codice, commenti, test e messaggi di commit.
- Git locale; nessun push senza richiesta.
- python3.12 per CLI e server.
