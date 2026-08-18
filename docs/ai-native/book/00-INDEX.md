# AI-native Book — TIME MACHINE / Le Rocce — edition **C1** (2026-08-18)

## Status
- **State:** approved
- **Loop id:** **C1**
- **Scope:** lo slot copilota diventa una **conversazione**: storia di `copilot-turn`, widget *dentro* il turno, chip = what's next. Il modello **compone** (tipi + chip da enum chiuso), non instrada una frase. Casa = due card. Zero tipi nuovi.
- **Surface map:** [`docs/ai-native/surface-maps/2026-08-18-C1-surface-map.md`](../surface-maps/2026-08-18-C1-surface-map.md)
- **Scelta:** A (thread + compose) — 2026-08-18
- **Shippato:** A1–A3 · P1 `251ab6a` · P2 `9ccb62a` · copilot-dock `d3f504c`
- **Non questo loop:** P3 (`viola` overlap) resta in-review a parte. Chat-casa (map B) vietata.
- **Frame sopra C1:** «parli con Le Rocce» — map [`2026-08-18-azienda-surface-map.md`](../surface-maps/2026-08-18-azienda-surface-map.md). C1 = voce. Poi M1 memoria+profilo, R1 richieste, Q1 piano mio + roster. Non si implementano in C1.
- **Approved by / date:** Francesco · 2026-08-18 (C1 + frame Azienda C1→M1→R1→Q1; impl solo C1.1–C1.3)

## Sources
- `specs/00` §§2–3; `specs/01` §4.3 + Loop P1; `specs/02` §4.1–4.3, P-A/P-F/P-L
- Map C1; live «non è conversazionale», «suono il piano il giovedì»
- Book A3 + delta P1/P2 (file sotto: non si riscrivono)

## Chapters
| Ch | Owner | Status | Delta C1 |
|---|---|---|---|
| 01 INTENT | AIUxer | ready | job «continuare» + metriche thread |
| 02 SURFACES | AIUxer | ready | rail = storia; non casa |
| 03 CATALOG | AIUxer | ready | nessun tipo nuovo; thread = shell |
| 04 AGENTS | dual | ready | Copilot compone, non classifica-e-switch |
| 05 ARCHITECTURE | AIEngineer | ready | stato conversazione + schema compose |
| 06 ECONOMICS | AIEngineer | ready | 1 LLM / enunciato; 0 LLM / chip |
| 07 RELIABILITY | AIEngineer | ready | evals U-c-* |
| 08 TENSIONS | dual | ready | righe C1 chiuse |
| 09 IMPL-READY | dual | ready | C1.1 thread · C1.2 compose · C1.3 next dopo write |

01–09 restano i file A3/P*; il **delta C1** è in sezione `## Loop C1` in ciascun capitolo.

## How to implement
Solo slice **C1.1 → C1.2 → C1.3** in `09` dopo approvazione. Zero tipi nuovi. Enum compose ⊆ CHIP ∪ tool allowlist ⊆ renderer.

## Fuori da C1
Chat-casa. Streaming (se CLI ~38s: fuori budget, si documenta). Persistenza conversazione su disco. Marketplace swap. P3. Inbox cover Anna.
