# 08 — Tensions (AIUxer ↔ AIEngineer)
**Owner:** dual · **Status:** ready

| Topic | AIUxer wants | Eng constraint | Decision | Metric / gate |
|---|---|---|---|---|
| Layer 2 apre un altro buco | Coprire pizze con chi è già in turno | `imposta` sostituisce l’intera cella-giorno | Preview obbligatoria del *prima → dopo*. Non è additivo. | U-sposta-conferma mostra entrambe le etichette |
| Copilot = chat? | Gateway alla pipeline, NL vera | Regex + default Scheduling è un buco P-L per Anna | **P1:** enum intent chiuso; `saluto`/`sconosciuto` non chiamano Scheduling; write solo chip | U-p-ciao |
| 15 buchi vs close | Residuo visibile, non 15 tap | Buchi ≠ veto CCNL | **A3:** compressi + detti in approval. Non diventano veto. | U-residuo-pubblica |
| Blocco CCNL vs pubblica | Il manager deve *chiudere* la settimana | Compliance non può auto-accorciare Matteo (già decisione umana). Template eredita 52h. | **A2:** la violazione è un atto (`sposta-turno` su di lui). Il veto resta; diventa agibile. | U-blocco-gesto; `pubblica` assente finché tetto rotto |
| Chat come casa manager | «Dashboard conversazionale» suona AI-native | Job noto e chiuso: liste/gap = det (P-B). Chat-casa = rumore, dump live, super-app (§5) | **No (1).** Casa = briefing composto (3). Slot = Copilot (2). Gerarchia in `02-SURFACES`. | week-grid < 10%; tap-gap è il path primario, non il prompt |
| Tabellone ancora esiste | Il 30×7 non è casa; il gesto vive sulle persone | Manager senza vista d’insieme se Scheduling tocca 1 persona e 15 gap | Tabellone **resta**, ma è la settimana del ciclo + overlay. Non si toglie in A. | % sessioni `week-grid` dopo A; se > 10% e stabile → emendare (forse B) |
| Candidati = person-shifts interi | Stesso atomo, un vocabolario | 8 card × 14 giorni è rumore (P-G) | Stack corto, tetto 8; `oggi` del widget = settimana del ciclo | U-gap-candidati; n card ≤ 8 |
| Layer 2 «movibili» | Solo i *liberi* (02 prima stesura) | Dopo `genera-bozza` i liberi sui gap residui sono **vuoti per costruzione** (`scheduling.py` assegna e poi elenca i resti). Senza layer 2 il gesto è morto sulla demo. | `candidati_per_gap` = layer 1 poi layer 2 (già in turno, altra fascia/reparto, stessa mansione). Etichetta «già in turno — confermi». Mai R/F. Form manuale se 0. | ≥ 1 gap con ≥ 1 candidato **oppure** empty onesto; 0 LLM sul POST |
| Riposi non sono disponibilità | Non proporre di bruciare il riposo | Manager *può* volerlo | R/F fuori dalla lista. Un riposo si tocca solo da form `sposta-turno` a mano. | U-gap-candidati |
| Approval inline vs route | P-F: niente navigazione | `conferma.html` già esiste e i test U4/U5 non la richiedono come URL | `_FLUSSO["conferma"]` renderizzato in `home.html`. `conferma.html` diventa macro/incluso, non destinazione. | U-annulla |
| Conferma come tipo catalogo | Un solo primitive #04 | Non inventare tipi (03) | Chrome shell, non nuovo widget. `scheda-preview` resta solo per la scheda. | 03 canary |
| Composer spento | Onesto se l’AI è giù | `LLMNonConfigurato` è sottoclasse di `LLMGiu`; `SchemaNonRispettato` oggi mappa a `giu` | `motivo=giu` **solo** per `LLMGiu` che non è `LLMNonConfigurato`. Schema → `schema`, acceso. Non si ribalta la gerarchia delle exception in A. | U-composer-det |
| `sposta-turno` nel guscio | Chip visibile = affordance | Chip senza campi = 500 | Via da `CHIP_PER_STATO`. Vive sulla card. | U-sposta-400 |
| Overlay bozza su `me` | Francesco vede «la sua» settimana viva | `home` passa `bozza=ciclo.bozza` anche se le settimane non coincidono | Overlay su `me` solo se `bozza.settimana` cade nell’orizzonte di `oggi` | U-me-senza-overlay-altra-settimana |
| Scheduling debole (1 persona + 15 gap) | Il manager deve poter chiudere la settimana | Rifare il solver è un altro slice e costa | A **non** riscrive Scheduling. Il gesto sui gap è l’addizionalità. | tempo/buco < 2 min |
| Job async / loader | «Bozza in preparazione · Ns» visibile | `Coda.sincrona=True`; tap-gap è corto | Async deferred. A non dipende dal loader. | — |
| Copy chip (slug) | «Accetta questa bozza» non `accetta bozza` | Fuori dal P0 | Solo le chip che A tocca (`sposta`, `accetta`, `pubblica`, `consulta` sul gap). Resto P2. | review visiva |
| Font 06 | Fraunces + Source Sans 3 | P2, non sblocca il job | Deferred. | — |

| Filo vs one-shot | Conversazione con widget e next | `_FLUSSO` è già volatile; 303 amnesia | **C1:** storia in `_FLUSSO`, cap 8; 303 non svuota. Non è casa | U-c-filo |
| Modello instrada o compone | Compone tipi+chip | Enum intent P1 è un centralino; regex in demo | **C1.2:** 1× `compone` (tool+chip+testo). Intent_det solo degrado | U-c-compose |
| What's next come tipo | «suggerimenti» visibili | Vietato tipo nuovo | Chip 1–3 dell’ultimo turno. Dopo write: tabella det (0 LLM) | U-c-next |
| 2 LLM (classifica+copy) | Una risposta | Costo e 38s×2 | Una chiamata. Fail schema → fatti | 06 |
| Fake in demo | Si sente l’AI | Test devono essere det | Test = fake scriptato. Demo che si prova = non `fake` | README già lo dice |
| Chat-casa | Tutto nel filo | U1, scelta A/P1 | No. Guscio invariato | U1 |
| Storia in kb | Memoria | `05` testo libero di Anna | Solo sessione. Confermata → scheda via chip | G1 |
| P3 nello stesso giro | `viola` giusto | Altro job | Fuori C1 | — |

Nessuna riga aperta. Ogni slice in 09 ha decisione qui.
