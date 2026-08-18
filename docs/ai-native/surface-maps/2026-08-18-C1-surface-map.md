# Surface map — TIME MACHINE / Le Rocce — 2026-08-18 — **C1**

## Meta
- Loop id: **C1** (conversazione). Non è P3 (`viola`).
- P1–P2 shippati: gateway + cella. Il gateway è un form, non una conversazione.
- Design root: questo repo · Impl: `.claude/worktrees/runtime-specs/`
- Sources: live Francesco («suono il piano», «non è conversazionale»); `specs/02` §4.1–4.3; Book 02 «non è dashboard conversazionale»; `copilot.py` `_intent`/`_è_preferenza`; `app.py` `POST /copilota` → 303; `home.html` composer; `catalogo.py` WIDGET/CHIP.

## Roles
| Role | Surfaces | Job vero adesso | Cosa manca |
|---|---|---|---|
| Dipendente | 2 card + composer one-shot | Vedere turni; dichiarare un vincolo | Continuare: «e adesso?», storia, widget *nel* turno |
| Manager | briefing A3 + stesso composer | Chiudere la settimana a gesti | Il composer non è dove pianifica (ok). Serve quando *chiede* («chi copre gio?») |

## Surfaces
| Surface | Family (spec) | Family (codice) | Entry |
|---|---|---|---|
| Home persona | dashboard-det (guscio) | det | `GET /home` |
| Copilota | **conversational-generative** (`02` §4.1 rail/pannello) | form POST + 303, 0–1 card, zero storia | `POST /copilota` |
| Tabellone | det, raro | det | `GET /tabellone` |

Due famiglie restano distinte. Il buco non è «chat = casa». Il buco è: **lo slot generativo dichiarato non esiste**.

## Runtime agents
| Agent | user_facing | emits | owns_presentation | Source |
|---|---|---|---|---|
| copilot | sì | `copilot-turn` + widget da `vista` | sì, ma **non compone**: classifica un enum e fa switch | `copilot.py` `_intent` + rami 0–5 |
| forecast / scheduling / compliance / secondo-pv | no | `Proposta` | no | invariato |

P-L storto in un altro modo rispetto a P1: il Copilot *parla*, ma non è un parlante di conversazione. È un router. `_è_preferenza` è ancora regex (`suono il piano|pianoforte|…`). Con `TM_LLM=fake` (demo) l'enum LLM non gira mai: è tutto euristica.

## Catalog diff
Niente tipi nuovi obbligatori. Manca **montaggio** e **stato**.

| Type | Kind | Surfaces | Det/Gen | Status | Notes |
|---|---|---|---|---|---|
| copilot-turn | widget | copilota | Gen copy + chip | diverged | Spec: *un turno* (testo+chip+widget). Codice: un messaggio usa-e-getta, sovrascritto al POST dopo |
| scheda-preview | widget | copilota | Det* | none | Esiste; fuori dal thread (è *invece* del turno) |
| person-shifts / balances | widget | guscio | Det | none | Casa. Non si montano *dentro* un turno |
| rationale | widget | consulta | Gen copy | none | Solo path `copri` manager |
| CHIP (chiuse) | chip | ovunque | Det set, Gen scelta | diverged | Dovrebbero essere il *what's next*. Oggi sono residuo del ramo (`salva-preferenza` / `apri-scheda`) |
| (thread / storia) | — | — | — | shell-not-catalog | Non c'è. `_FLUSSO["widget"]` è l'ultimo colpo |
| chat-generica | — | — | — | **fuori catalogo** (`02` §4.2) | Non si apre |

Canary enum ⊆ renderer: `WIDGET_SELEZIONABILI_LLM` ⊆ `WIDGET`. Ok. Il compose path **non onora** la scelta: il modello (quando c'è) scrive solo `testo`+`chip` *dopo* che il ramo ha già deciso il widget (`_copy`).

## Trust boundary hotspots
- Write scheda / pubblica / sposta: solo chip + preview. Invariato.
- Storia conversazione: contiene testo libero di Anna → `kb` no, sessione sì, retention da dire (`05`).
- Il modello non calcola ore e non inventa tipi. Invariato.
- Allowlist Anna: sé. Invariato.

## Gaps that matter (clustered)
### P0 — blocks a real job end-to-end
1. **Non c'è conversazione.** Ogni frase è un RPC. Niente «ok, e i prossimi giovedì?» che vede il turno prima.
2. **I widget non stanno nel dialogo.** Stanno nel guscio o al posto del turno. P-F (`02` §3: l'azione inietta il prossimo widget *nello stesso flusso*) è lettera morta.
3. **What's next assente.** Dopo «piano salvato» il sistema tace. Le chip non sono mosse successive, sono il submit del ramo.
4. **La conversazione è regex + fake.** Demo `TM_LLM=fake` → `_intent_det`. Anche con modello, due chiamate (classifica, poi prosa) su un intento già deciso dal codice.

### P1 — structural
5. 303 + fragment: occhi sul composer, ma storia = 1. Ricarica = amnesia.
6. P1 ha *vietato* chat-casa. Giusto per U1. Ha anche *evitato* di costruire lo slot conversazionale che `02` §4.1 già nomina.
7. P3 (`viola` overlap) è un altro job; non sblocca la chat.

### P2
Latency compose vs form sincrono (~38s `claude -p`). Streaming. Retention log conversazione.

## Keystone
**Il Copilot compone un turno di catalogo, non instrada una frase.** Stesso catalogo, stessa allowlist, stessi write-via-chip. Cambia il *contratto di superficie*: una storia di `copilot-turn`, widget *dentro* il turno, chip = prossimo passo. L'LLM sceglie tipi e chip da enum chiuso; il calcolo resta codice.

## Do NOT touch
Casa due card (U1). Dual gate pubblica. Catalogo tipi. `deriva_vincolo` / ore / CCNL come codice. Tap cella = preferenza (P2). Gestualità A3 del manager.

## Proposals (2–3)
### A — Thread + compose (recommended)
- Composer/rail = storia di `copilot-turn` (N ultimi, sessione).
- Un turno = testo + 0–n widget già in catalogo + 1–3 chip dal set chiuso ∩ ruolo.
- **Una** chiamata compose (schema). Tool det: `prepara_preferenza`, `mostra_turni`, `mostra_saldi`, `consulta_*` (manager).
- Regex solo se modello giù (degrado onesto, già P-D).
- Demo: non `fake` se si vuole sentire la chat.
- What's next = chip dell'ultimo turno, non un tipo nuovo.
- Jobs: Anna continua dopo il piano; Francesco chiede sul piano e riceve rationale+chip, non un form.
- Costo: `one-llm-turn` / messaggio. Nessun tipo nuovo.

### B — Chat-casa
Home = thread; `person-shifts` è un widget *dentro* la chat. Più «prodotto AI». Rompe U1, il primo paint, e la scelta A/P1. No.

### C — Playbook senza thread
Si toglie la regex, si tiene il form one-shot, si fa compose solo della prosa e delle chip. Meno rischio. Non dà «conversazione» né P-F. Francesco lo sentirebbe ancora come console.

**Raccomando A.** È quello che `02` ha già scritto e P1 non ha costruito.
