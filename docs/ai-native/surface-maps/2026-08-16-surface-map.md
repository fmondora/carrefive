# Surface map — TIME MACHINE / Le Rocce — 2026-08-16

## Meta
- Design root: `/Users/fmondora/wip/personal/carrefive`
- Impl root: `/Users/fmondora/wip/personal/carrefive/.claude/worktrees/runtime-specs`
- Live: `http://127.0.0.1:8770/` (`TM_OGGI=2026-06-29T14:05`, kb usa-e-getta via `demo.sh`)
- Sources:
  - `specs/00-high-level.md`, `01-sistema-agentico.md`, `02-genui.md`, `03-calendario-google.md`, `04-ferie-permessi-gamma.md`, `05-security-gdpr.md`, `06-design-system.md`, `07-landing-attivazione.md`
  - `timemachine/domain/catalogo.py`, `timemachine/vista.py`, `timemachine/web/app.py`
  - `timemachine/web/templates/{home,widget,landing,tabellone,conferma,scheda,attivatore,attiva}.html`
  - `timemachine/agents/{copilot,scheduling}.py`, `timemachine/orchestrator/ciclo.py`
  - Test live 2026-08-16: Anna + Francesco (ciclo U1, U5, U8, L1, L10, preferenza, bozza, tabellone, attivatore, copilot, API)

## Roles
| Role | Surfaces | Notes |
|---|---|---|
| Dipendente (Anna) | landing, home persona, scheda propria, composer Copilot | Job: «quando lavoro» + preferenza + saldi. Non vede colleghi né tabellone. |
| Manager (Francesco) | home persona + stato ciclo + proposal-pack, tabellone, conferma, Copilot | Job: pianificare la settimana *che arriva*. Oggi la home è la sua settimana *in corso*. |
| Attivatore (Emilio = Francesco) | `/attivatore`, QR, `/attiva` | Invite-only. Zero AI. |
| Anonimo | `/` landing, `/attiva?t=` | Nessun nome, nessun turno (L1 live). |
| Consulente paghe / titolare | n/a | Solo-spec (00 Must/Should). Non esiste superficie. |

## Surfaces
| Surface | Family | Entry | Primary jobs |
|---|---|---|---|
| Landing pubblica | dashboard-deterministic | `GET /` `app.py:118` · `landing.html` | Entrare; incollare invito |
| Attivazione | dashboard-deterministic | `GET /attiva` `app.py:197` | Completare uid/pwd o Google |
| Home persona (guscio) | hybrid | `GET /home` `app.py:292` · `home.html` | Vedere i *miei* turni; (manager) avanzare il ciclo |
| Copilot (composer fisso) | conversational-generative | `POST /copilota` `app.py:334` | NL: preferenza, consulta, comando ciclo |
| Conferma / approval | dashboard-deterministic | `POST /chip/{nome}` → `conferma.html` | Gate su accetta/rifiuta/pubblica/scollega |
| Scheda md | dashboard-deterministic | `GET /scheda/{slug}` `app.py:575` | Vista deterministica del file |
| Tabellone | dashboard-deterministic | `GET /tabellone` `app.py:610` | Vista rara 30×7 — *settimana corrente pubblicata*, non la bozza |
| Attivatore | dashboard-deterministic | `GET /attivatore` `app.py:629` | Invitare chi non è ancora dentro |
| API JSON | n/a (non UI) | `/api/turni/{slug}` `app.py:721` | Authz: Anna→Debora = 403 live |

## Runtime agents
| Agent | user_facing | emits | owns_presentation | Source |
|---|---|---|---|---|
| copilot | yes | `copilot-turn` + widget filtrati + chip | true | `agents/copilot.py` · `01` §4.3 |
| forecast | no | dominio (fabbisogno) | false | mapping in ciclo |
| scheduling | no | `Proposta` bozza-turni | false | `agents/scheduling.py` → `vista.proposal_pack` |
| compliance | no | violazioni / pubblicabile | false | `vista.compliance_block` |
| anomaly | no | segnali | false | roster 01; non esercitato in UI (niente consuntivo) |
| secondo-pv | no | note memoria | false | retrieval in `home` `app.py:304`; `vista.secondo_note` |

Canary: `WIDGET_SELEZIONABILI_LLM` ⊆ `WIDGET` ⊆ renderer `widget.html:256`. `week-grid` **non** è LLM-selectable (`catalogo.py:33-46`). OK.

## Catalog diff
| Type | Kind | Surfaces | Det/Gen | Status | Spec | Code | Notes |
|---|---|---|---|---|---|---|---|
| orario, etichetta-mansione, badge-stato, nome-persona, giorno | atom | person-shifts, week-grid | Det | none | 02 §4.2 | `catalogo.py:15` · usati in template, non tipi autonomi | |
| person-shifts | widget | home, proposal-pack, copilot | Det | none | 02 | `vista.py:46` · `widget.html:13` | Casa. Live Anna: adesso 14–20, prossimi, 41h su 40. |
| person-balances | widget | home | Det | none | 02, 04 | `vista.py:118` | Anna 96h/24h; Francesco vuoto onesto. |
| coverage-gap | widget | home manager | Det | none | 02 | `vista.py:179` | Lista lunga, **zero gesto** per coprire. |
| compliance-block | widget | home, conferma | Det | none | 02, 01 | `vista.py:183` | Blocca `pubblica`. Live: Matteo 52h. |
| proposal-pack | widget | home manager | Det* | none | 02 | `vista.py:192` | Live: 1 persona (Luca), non Debora/Cesare (UC-08). |
| rationale | widget | home, copilot | Gen copy | none | 02 | `vista.py:217` | Marcata `generata`. Doppia con copilot-turn. |
| diff-edit | widget | proposal-pack | Det | none | 02 | `vista.py:151` | |
| scheda-preview | widget | copilot | Det* | none | 02, 05 | `vista.py:160` · `widget.html:181` | Live UC-07: vincolo + storia + 3 bottoni. |
| secondo-note | widget | home | Det | none | 02 | `vista.py:228` | kb/secondo vuota in demo. |
| copilot-turn | widget | home | Gen | none | 02 | `vista.py:232` | |
| week-grid | widget | /tabellone | Det | diverged | 02: solo chip, non landing | `app.py:610` apre **settimana corrente**, non `_settimana_del_ciclo` | Manager vede 29/06 mentre pianifica 07/06. |
| consulta … scollega-google | chip | 02 table | — | none | 02 §4.2 | `catalogo.py:61` | Label = slug (`accetta bozza`). |
| riprova, aggiorna-saldi | chip | 03/04 | — | only-code vs 02 | 03, 04 | `catalogo.py:74-75` | In 02 assenti; ok come 03/04. |
| invia-attivazione, mostra-qr, revoca-invito | chip | attivatore | — | only-code vs 02 / none vs 07 | 07 §4.2 | `catalogo.py:76` | Superficie 07, non catalogo generativo. |
| crea-account, entra-con-google | chip | 07 | — | only-spec (come chip) | 07 | form/link, non enum CHIP | shell-not-catalog. |
| stato-ciclo | chrome | home manager | Det | shell-not-catalog | 02 guscio | `home.html:14` | |
| composer | chrome | tutte le home | — | shell-not-catalog | 02, 06 #08 | `home.html:44` `position:fixed` | Copre le card. Live. |
| apri-scheda | chip / link | person-shifts | Det | none | 02 | link `/scheda/…` non form chip | |

## Trust boundary hotspots
- `pubblica` e `salva-preferenza` confermati. OK (P-C).
- `accetta-bozza` ha preview + «chi è toccato». Annulla con `conferma=0` **riapre la stessa preview** (`conferma.html:31` + `app.py:390`).
- `sposta-turno` è write (`CHIP_DI_WRITE`) **senza** campi né conferma: `POST /chip/sposta-turno` → **500** live (`app.py:431` `date.fromisoformat` su vuoto).
- Copilot non scrive. OK. Tool allowlist in `copilot.py:79`.
- Anna `/api/turni/debora` 403, `/tabellone` 403. OK.
- Token QR in chiaro su `/attivatore` (atteso in pilota locale; non loggare).
- Composer `copilota_spento=1` dopo un turno con `motivo=giu` **anche se il path deterministico è riuscito** (preferenza salvata; consulta sabato risolta). `copilot.py:125-127` tratta `SchemaNonRispettato` come `giu`; `Risposta.spento` spegne il composer per la sessione (`app.py:345`).

## Gaps that matter (clustered)
### P0 — blocks a real job end-to-end
1. **Il manager non può organizzare la settimana che arriva.** Home = i *suoi* turni del 29/06 + bozza che tocca 1 persona (Luca, mer sala) + 15 buchi morti + blocco Matteo 52h copiato dalla settimana scorsa. Nessun gesto per coprire un gap. `sposta-turno` crash. Tabellone = settimana *sbagliata*. Job 01 «produrre e chiudere una settimana» non si chiude.
2. **`sposta-turno` è 500.** Chip sempre in `CHIP_PER_STATO["attesa_umano"]` (`ciclo.py:43-50`) senza UI di target.
3. **Composer muore dopo il primo uso reale.** Anna dopo UC-07 e Francesco dopo «chi copre sabato» vedono «Copilota non disponibile». Il job preferenza / consulta è one-shot.

### P1 — structural / second surface
4. **Due tempi sulla stessa home.** `person-shifts(me)` = oggi/pubblicato; ciclo = +7 giorni. Il manager non ha un «io la settimana che piano».
5. **Tabellone ≠ bozza** (`app.py:617` usa `_settimana_corrente`, non `_settimana_del_ciclo`). U8 formale passa, il job no.
6. **Copilot consulta = dump di N `person-shifts` interi** (Tiziana/Enrica/Marianna/Stefano/Giacomo, orizzonte *questa* settimana) sotto una pagina già lunga. P-G rotto. «consulta» chip no-op (`app.py:369` → home).
7. **Chip-slug come copy.** `accetta bozza`, `scegli variante` (1 sola variante), `sposta turno`, `non ancora entrate`. 06 chiede approval card, non toolbar da registry.
8. **Annulla in conferma è un loop.**
9. **Niente feedback post-salva-preferenza.** Preview sparisce, gio resta 7-16 (corretto), composer spento: Anna non sa se ha funzionato.
10. **`scegli-variante` nel guscio anche con 1 variante.** `proposal_pack` la filtra, `ciclo.chip` no.

### P2 — cleanup / vocabulary / docs drift
11. Path `kb/turni/….md` a piè del widget (utile in eval, rumore per Anna).
12. Giorni senza data (`mar` / `gio`) — su mobile si perde il 30/02.
13. Badge `No` (martedì Anna) opaco vs `R` / `F`.
14. Composer fisso copre fonti e saldi (desktop e mobile).
15. Attivatore: 28 righe identiche, email vuota, `revoca` anche su non-invitata.
16. README root: «non c’è runtime» — falso rispetto al worktree.
17. AGENTS.md: catalog/renderer «non ancora» — drift.
18. Solo Anna ha `kb/saldi/`. Francesco empty-state onesto.
19. Note operative di settimana (ALZARE DA TERRA, SHOOTING) assenti da ogni superficie.
20. Chip 02 vs 07: `crea-account` non nel registry (ok, shell).

## Keystone
**Un gesto «copri questo buco» (persona candidata → preview → conferma) sulla settimana del ciclo, e spegnere il composer solo se l’AI è davvero giù.** Sblocca P0.1–P0.3 e rende il frame persona-first usabile dal manager. Senza questo, il tabellone tornerà casa — e oggi è persino la settimana sbagliata.

## Do NOT touch
- Landing 07 (L1 live: zero nomi). Design fresco 06 tiene.
- Home Anna: `person-shifts` + `person-balances`, zero `week-grid`. U1 vivo. È il pezzo che ha senso.
- Authz: 403 su turni altrui e tabellone dipendente.
- Catalogo chiuso + drop unknown (U6 test + renderer).
- Gate `pubblica` assente se non `pubblicabile`. Compliance visibile.
- Preferenza: preview vincolo≠storia, write solo su conferma. UC-07 funziona (fino allo spento).
- Invite-only + QR = stesso URL.
- Invariante calcolo: ore e saldi da codice.

## Proposals (2–3)
### A — Chiudere il loop manager sulla settimana che arriva (recommended)
- Scope: (1) `week-grid` e overlay bozza sulla **settimana del ciclo**; (2) `coverage-gap` cliccabile → candidati (det, già in scheduling) come stack corto di `person-shifts` + chip `sposta-turno` **con campi e conferma**; (3) composer spento solo su `LLMGiu` vero, non su `SchemaNonRispettato`; (4) Annulla → `/home`.
- Jobs closed: pianificare, coprire un buco, non crashare, poter parlare due volte.
- Types: nessuno nuovo. `coverage-gap` + `sposta-turno` + `person-shifts` già in catalogo.
- Cost: `free-det` + eventuale `one-llm-turn` solo per ordinare candidati (già previsto in scheduling).

### B — Tenere il frame Anna e ammettere il tabellone come casa manager
- Scope: due famiglie fisicamente separate (02 già lo dice). Home manager = ciclo + gap + tabellone della bozza. Home dipendente invariata.
- Jobs closed: il manager smette di fingere di essere un dipendente con chip extra.
- Risk: tradisce la metrica «<10% sessioni aprono week-grid» — ma oggi quella metrica è un auto-goal.

### C — Solo hygiene (non basta)
- Copy chip, date sui giorni, composer non overlay, feedback post-preferenza, nascondere path kb, togliere `scegli-variante` se n=1.
- Cost: `free-det`. Non sblocca il job manager.
