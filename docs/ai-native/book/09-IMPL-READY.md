# 09 — Implementation-ready slices
**Owner:** dual · **Status:** ready

Ordine = dipendenze. Ogni slice è shippabile da sola. Implementazione **solo dopo approvazione** del Book. Root codice: `.claude/worktrees/runtime-specs/`.

**C1 (questo edition):** C1.1 → C1.2 → C1.3. P0 mappa C1 coperti tutti e tre. P3 e slice A/P storiche sotto, non in questo giro.

---

## Slice C1.1 — Il filo
- **Goal:** due frasi di seguito si vedono entrambe. I widget stanno *dentro* il turno. Il primo paint è vuoto di chat.
- **Authorized by:** Book 02/05 C1, map C1 A, P-F
- **Files:** `_FLUSSO["conversazione"]` in `app.py`; `home.html` composer elenca i turni; `widget.html` `copilot_turn` accetta `widget[]` figli; CSS composer (scroll, cap visivo)
- **Interfaces:** `conversazione: [{ruolo, testo?, turno?}]` cap 8. `POST /copilota` e tap cella **appendono**. 303 `/home#copilota`.
- **Tests:** U-c-filo, U-c-dentro, U1 resta. U-p-cella: preview è un turno nel filo.
- **Done when:** «ciao» poi «suono il piano il giovedì» → due card nel composer; preview dentro la seconda; GET a freddo senza turni.
- **Status:** ready (Book C1 approvato 2026-08-18 — impl da questo file)
- **Depends:** nessuno. Può usare ancora il router P1.

---

## Slice C1.2 — Compose
- **Goal:** un enunciato = una `compone`. Niente switch su regex nel path felice.
- **Authorized by:** Book 04/05/06 C1, `01`/`02` Loop C1
- **Files:** `copilot.py` (`compone` + `SCHEMA_COMPONI`; `_intent`/`_è_preferenza` solo except LLM*); test con `llm_finto.per_agente` scriptato
- **Interfaces:** `{testo, tool ∈ tool_per(attore)| "", chip[1–3]}`. Tool → fetcher già esistenti. Chip filtrate.
- **Tests:** U-c-compose, U-c-degrado, U-p-ciao e U5 restano (script o degrado).
- **Done when:** path felice con copione JSON non chiama `_è_preferenza`. Anna + tool `consulta_scheduling` → rifiuto onesto, non dump. Composer acceso su schema fail.
- **Status:** ready (Book C1 approvato 2026-08-18 — impl da questo file)
- **Depends:** C1.1 (il turno va nel filo)

---

## Slice C1.3 — Next dopo write
- **Goal:** confermare non è un muro. Tabella det, 0 LLM.
- **Authorized by:** Book 02/06 C1, P-F
- **Files:** `app.py` dopo `salva-preferenza` (e, se già lì, `collega-google`); helper `prossimo_dopo(azione, attore) -> (testo, chip[])`
- **Tabella (chiusa):**
  - `salva-preferenza` → «È sulla tua scheda. Lo Scheduling la vede al prossimo ciclo.» + `apri-scheda`, `collega-google` (se non collegata)
  - `collega-google` ok → «I pubblicati vanno sul tuo calendario.» + `apri-scheda`
  - altre write manager (accetta/pubblica): **non** in C1 — restano A3
- **Tests:** U-c-next. U5/UC-07: kb invariata finché conferma; dopo, turno di chiusura visibile.
- **Done when:** dopo Conferma sul piano, il filo ha un turno nuovo con ≥1 chip; campo ancora acceso.
- **Status:** ready (Book C1 approvato 2026-08-18 — impl da questo file)
- **Depends:** C1.1. Può parallelo a C1.2.

---

## Slice P3.1 — `viola` = sovrapposizione
- **Goal:** `no_pomeriggio` vede un 7-16. Se non si può onorare, E3 (nota).
- **Authorized by:** map P3 A, spec `02` Loop P3, UC-07
- **Files:** `privacy.viola` (turno/`ore_in_fascia`, non solo `inizio_ora`); caller in scheduling; test U-p-sovrapposizione
- **Done when:** 7-16 ∩ `no_pomeriggio` = True; 7-12 ∩ `no_pomeriggio` = False. U5/E3 verdi.
- **Status:** ready (dopo approvazione Book P3)

---

## Slice P2.1 — Cella = quella data
- **Goal:** tap 02/07 salva solo il 02/07. «Tutti i gio» è una seconda chip, esplicita.
- **Authorized by:** map P2 A, spec `02` Loop P2
- **Files:** `privacy.deriva_vincolo` / `Preferenza.viola`; `app.py` tap passa ISO; `scheda-preview` testo scope + chip «tutti i giovedì»
- **Done when:** U-p-data: tap gio 02/07 → `data=2026-07-02`; altri gio non violati. U5 NL ricorrente verde.
- **Status:** ready (dopo approvazione Book P2)

---

## Slice P2.2 — Hygiene P1
- Chip saluto Anna: non solo `apri-scheda` (ferie / tocca un giorno). `copri` manager: rationale, non 5 person-shifts. Fix overlay riga tappata.
- **Status:** ready (dopo approvazione Book P2)

---

## Slice P1.1 — Gateway intent (non regex)
- **Goal:** «ciao!» e ogni NL passano da un enum chiuso, poi dalla pipeline. Mai `consult(scheduling)` di default.
- **Authorized by:** spec `01`/`02` Loop P1, Book 02 P1, map P1 proposta A
- **Files:** `timemachine/agents/copilot.py` (`rispondi`: classifica intent con LLM+schema enum; fallback det se giù = `sconosciuto` + chip, non scheduling); allowlist per ruolo; `tests/test_u_genui.py` U-p-ciao; `test_e_sistema_agentico.py` E10
- **Interfaces:** `Intent = preferenza|turni_miei|saldi|copri|comando_ciclo|saluto|sconosciuto`. Tool Anna ⊆ {mostra_turni self, mostra_saldi self, prepara_preferenza}.
- **Done when:** POST «ciao!» da Anna: 0 chiamate scheduling, 0 `person-shifts` di colleghi, composer acceso, ≥1 chip (`non posso` / ferie / scheda). «giovedì ho pianoforte» resta U5.
- **Status:** ready (dopo approvazione Book P1)

---

## Slice P1.2 — Cella = preferenza
- **Goal:** tap su un giorno dei *miei* turni apre `scheda-preview`.
- **Files:** `widget.html` `person_shifts(mio=True)` form per giorno; `app.py` chip `salva-preferenza` già c’è
- **Done when:** U-p-cella verde. U1: primo paint senza preview.
- **Status:** ready (dopo approvazione Book P1)
- **Depends:** nessuno. Può parallelo a P1.1

---

## Slice 1 — Composer onesto + Annulla
- **Goal:** dopo un path det, si può scrivere di nuovo. Annulla torna a casa.
- **Authorized by:** 01 (parlare due volte), 02 (composer / Annulla), 05, 07 U-composer-det U-annulla, 08
- **Files:**
  - `timemachine/agents/copilot.py` (`_copy`: `SchemaNonRispettato` → `motivo="schema"`; non `"giu"`)
  - `timemachine/web/app.py` (`conferma=0` → pulisci flusso, 303 `/home`; non rirenderizzare preview)
  - `tests/test_u_genui.py` (U-composer-det, U-annulla); `test_llm.py` se tocca i motivi
- **Interfaces:** `Risposta.motivo ∈ {"", "giu", "non-configurato", "schema"}`. `spento` resta `motivo=="giu"`.
- **Tests / canaries:** U-composer-det, U-annulla, U5 e U7 restano verdi.
- **Done when:** Anna dopo il pianoforte ha l’input acceso. Annulla su accetta non lascia la pagina di conferma. Nessun 500 nuovo.
- **Status:** ready

---

## Slice 2 — `sposta-turno` con campi, conferma, no 500
- **Goal:** il manager sposta un turno senza far cadere il server; Compliance ricalcola.
- **Authorized by:** 01, 02 (flow conferma), 03 (`CHIP_CON_CONFERMA`), 05, 07 U-sposta-*, 08
- **Files:**
  - `timemachine/domain/catalogo.py` — `sposta-turno` in `CHIP_CON_CONFERMA`
  - `timemachine/orchestrator/ciclo.py` — togliere `sposta-turno` da `CHIP_PER_STATO["attesa_umano"]`
  - `timemachine/web/app.py` — validare campi; 400 se mancano; preview in `_FLUSSO["conferma"]`; `conferma=1` chiama `ciclo.sposta_turno`
  - `timemachine/web/templates/widget.html` — form su `person-shifts` non-mio (candidato) e/o `diff-edit`: hidden `persona,data,fascia`
  - `tests/test_u_genui.py`
- **Interfaces:** `ciclo.sposta_turno(attore, persona, data, fascia)` invariato. HTTP: campi form obbligatori.
- **Tests / canaries:** U-sposta-400, U-sposta-conferma, U-sposta-ok, U4.
- **Done when:** POST nudo ≠ 500. Senza conferma il piano è identico. Con conferma il turno è sul piano e si torna in `attesa_umano`.
- **Status:** ready

---

## Slice 3 — Gap cliccabile → candidati det
- **Goal:** dal buco si arriva a delle persone, senza prompt e senza LLM.
- **Authorized by:** 01 (coprire un buco), 02 flow, 03 `consulta`, 04 P-L, 05 `candidati_gap`, 06 free-det, 07 U-gap-*, 08
- **Files:**
  - `timemachine/agents/scheduling.py` — `candidati_per_gap` (layer 1 `_candidati` + layer 2 `_movibili` se 1 è vuoto). Non chiamare `_ordina` / LLM.
  - `timemachine/vista.py` — `candidati_gap(...)`; `person_shifts` overlay solo se la bozza interseca `oggi`
  - `timemachine/web/app.py` — `consulta` con payload scrive `_FLUSSO["candidati_gap"]`
  - `timemachine/web/templates/widget.html` — riga `coverage-gap` = form POST `/chip/consulta`
  - `timemachine/web/templates/home.html` — monta i candidati sotto i gap
  - `tests/test_u_genui.py`
- **Interfaces:** `candidati_per_gap(piano, data, reparto, schede) -> list[str]`. Nessun tipo catalogo nuovo.
- **Tests / canaries:** U-gap-candidati, U-gap-vuoto, U-me-senza-overlay-altra-settimana, U1.
- **Done when:** tap su un buco della bozza demo produce stack (layer 1 o 2) **o** empty onesto, ≤8, zero R/F, zero LLM. Confermare un candidato usa slice 2. Francesco `me` senza badge bozza se le settimane non coincidono. < 200ms.
- **Status:** ready
- **Depends:** slice 2 (il candidato deve poter confermare lo spostamento)

---

## Slice 4 — Approval inline sulla home
- **Goal:** accetta / rifiuta / pubblica non sbalzano su un’altra casa. Copy umana sulle chip toccate.
- **Authorized by:** 02 (approval inline), 03 (shell, non tipo nuovo), 05, 07 U-annulla, 08
- **Files:**
  - `timemachine/web/app.py` — `_conferma` scrive `_FLUSSO` e 303 `/home` (non TemplateResponse `conferma.html` come pagina)
  - `timemachine/web/templates/home.html` — include la card se `_FLUSSO["conferma"]`; in `attesa_umano` ordine: ciclo → conferma → blocco → gap → pack → `me` (Book 02 gerarchia)
  - `timemachine/web/templates/conferma.html` — diventa macro incluso, o si sposta il markup in `widget.html` come macro `approval` (non un `tipo`)
  - `timemachine/web/templates/widget.html` — disegnare le chip del `proposal-pack`; nascondere `scegli-variante` se N=1
  - `tests/test_u_genui.py` (U9 spirito: genera-bozza e accetta restano su `/home`)
- **Interfaces:** `_FLUSSO["conferma"] = {domanda, azione, toccati, avvisi, campi, blocco}`.
- **Tests / canaries:** U-annulla (già 1, riaffermare), U4 (`pubblica` assente se blocco), U9.
- **Done when:** URL dopo tap `accetta-bozza` è `/home`. Annulla pulisce. Pack mostra le sue chip.
- **Status:** ready
- **Depends:** slice 1 (Annulla)

---

## Slice 5 — Tabellone = settimana del ciclo
- **Goal:** se il manager apre il foglio, è quello che sta pianificando.
- **Authorized by:** 01, 02 tabellone, 03 week-grid, 05, 07 U-settimana-ciclo, 08
- **Files:**
  - `timemachine/web/app.py` — `tabellone` usa `_settimana_del_ciclo()`; se `ciclo.bozza`, `vista.week_grid(ciclo.bozza.piano)`
  - `timemachine/vista.py` — overlay opzionale celle bozza vs pubblicato allineato per weekday
  - `timemachine/web/templates/widget.html` / `tabellone.html` — segno overlay; link chiudi resta `/home`
  - `tests/test_u_genui.py` U8 + U-settimana-ciclo
- **Interfaces:** `GET /tabellone` invariato come route. Query `?settimana=` resta override esplicito.
- **Tests / canaries:** U8 (chip, chiudi, 403 dipendente), U-settimana-ciclo.
- **Done when:** in `attesa_umano` sul 06/07, il tabellone mostra 06/07 (o la bozza), non solo 29/06. Home ancora senza `week-grid`.
- **Status:** ready
- **Depends:** nessuna. Può andare in parallelo a 2–4.

---

## Slice 9 — **A3** Residuo, non muro
- **Goal:** Francesco vede `Pubblica` *e* quanti buchi restano; dopo un tap il prossimo, non i quindici.
- **Authorized by:** map A3 proposta A, spec `02` Loop A3, Book 02 A3
- **Files:** `widget.html` `coverage_gap` (conteggio + disclosure); `app.py` `_avvisi` / `_apri_conferma` (N buchi); dopo `sposta` ok, `consulta` sul prossimo gap con candidati
- **Interfaces:** zero tipi nuovi. `coverage-gap.buchi` invariato; chrome + ordine.
- **Tests:** U-residuo-pubblica (dopo blocco sciolto + accetta: chip pubblica + testo residuo). U-prossimo-buco (dopo sposta su un gap, DOM ha `.esito` sul *successivo* copribile, non 15 form piatte). U1/U4/U-blocco-gesto restano.
- **Done when:** live come A2 (Matteo → accetta → Pubblica) **più** «restano N buchi»; un tap-gap + conferma non ributta sul muro.
- **Status:** ready (dopo approvazione Book A3)

---

## Slice 10 — **A3** Hygiene A2
- **Goal:** chip `6-14 → R` distinguibili per giorno; Book 05–07 allineati al codice A2 (tap-blocco, `MAX_CELLE_SBLOCCO`, 0 token).
- **Files:** `widget.html` (giorno sulla mossa); `05`/`06`/`07` markdown
- **Done when:** due `6-14 → R` in pagina hanno lun/mer/ven visibile.
- **Status:** ready (dopo approvazione Book A3)

---

## Slice 6 — **A2** Blocco = gesto
- **Goal:** Matteo 52h (o qualsiasi violazione) si scioglie dalla riga del blocco, senza Excel.
- **Authorized by:** spec `01` UC-03.5 + Loop A2, Book 02 A2, map A2 proposta A
- **Files:** `widget.html` (`compliance_block` form su violazioni), `app.py` (`consulta` con `persona`+`motivo=blocco` *oppure* riuso `sposta` con campi dalle sue celle), `vista.py` (card persona settimana ciclo, no `adesso` se `oggi` ≠ giorno)
- **Interfaces:** nessun tipo nuovo. Payload: `persona`, `data` celle, `fascia` candidata (es. togliere uno spezzone → resto, o `R`).
- **Tests:** U-blocco-gesto; U4 resta (senza gesto, `pubblica` assente); E4 resta.
- **Done when:** tap «matteo 52h» mostra i suoi turni della bozza + almeno un `sposta-turno`; dopo uno spezzone in meno sotto tetto, il blocco tetto sparisce e, se accettata, può comparire `pubblica`.
- **Status:** ready (dopo approvazione Book A2)
- **Depends:** slice 2 (già in A1)

---

## Slice 7 — **A2** Il buco tappato è il soggetto
- **Goal:** tap → risultato visibile senza scrollare 15 buchi; candidato senza `adesso` bugiardo.
- **Authorized by:** Book 02 A2, map A2 proposta B, spec `02` Loop A2
- **Files:** `home.html` (ordine: gap scelto + `candidati` prima del resto dei buchi, o filtro), `vista.candidati_gap` / `person_shifts` (niente `adesso` se `data ≠ oggi`)
- **Tests:** U-gap-candidati: il primo `person-shifts` candidato in DOM è dopo la rationale del tap e prima del pack; nessun `.adesso` su candidato futuro.
- **Done when:** tap pizze pome mostra Mara/Cesare/Monia *sopra* il pack, senza «adesso 10-14».
- **Status:** ready (dopo approvazione Book A2)

---

## Slice 8 — **A2** Debito A1
- **Goal:** `scegli-variante` solo se n>1. Book 05 firma `candidati_per_gap` + due MAX documentati.
- **Files:** `ciclo.chip()`, 05/09 allineati (già vero nel codice: fascia obbligatoria).
- **Done when:** 1 variante → chip assente dallo stato-ciclo.
- **Status:** ready (dopo approvazione Book A2)

---

## Deferred (non in 09 ready)
| Cosa | Perché | Owner |
|---|---|---|
| Direzione B (due case) | Non scelta | — |
| Solver Scheduling da zero / 3 varianti | Altro slice; A è addizionalità sui gap | AIEngineer |
| Coda async + loader visibile | D4; non blocca i job A | AIEngineer |
| Font Fraunces / path kb / date sui giorni | P2 | AIUxer |
| `consulta` discoverable su Anna (preferenza) | P1 utile, non P0 della scelta A | AIUxer |
| Dashboard Anna «più widget» | Ha già le due card. Slice (2) dopo A: `secondo-note` / `diff-edit` solo con un fatto | AIUxer |
| Chip 07 fuori da `CHIP` generativo | P2 canary | AIEngineer |

Non riaprire 01–03 in implementazione. Bug e chiarimenti sì; tipi nuovi no.
