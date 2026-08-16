# TIME MACHINE

Sistema agentico + GenUI per i turni di un punto vendita GDO.

Pilota: **Le Rocce**, Poggiridenti. Invariante: **l'AI propone, l'umano dispone, il calcolo è deterministico.**

Questo repo è ancora solo specifiche e knowledge. Non c'è runtime.

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

## Knowledge (pilota)

Markdown, leggibile da un umano. Tre famiglie:

- `kb/persone/` — scheda di ciascuno: contratto, mansioni, preferenze
- `kb/turni/` — settimane pubblicate (22/06 e 29/06/2026) + foto dei tabelloni
- `kb/saldi/` — montante ferie/permessi (file ora; snapshot Gamma dopo)
- `kb/secondo/` — memoria collettiva del negozio (ancora vuota)

Mappa colori → reparti: `kb/reparti.md`.

## Come si progetta

Plugin [`ai-native`](https://github.com/fmondora/AI-Engineering): **AIUxer** (superficie) e **AIEngineer** (architettura, costo, evals).

```
surface-map  →  scelta  →  project-book  →  implementazione da Book §09
```

Niente codice di catalogo finché il Book slice non è approvato. Dettaglio per gli agenti: `AGENTS.md`.

## Fuori da questa edizione

Payroll interno, multi-store, secondo personale, scoring individuale, Outlook/Apple, rilevazione biometrica.
