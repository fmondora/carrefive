# 01 — Sistema agentico

Specifica di **costruzione del runtime**. Definisce cos'è un agente, come si consulta da solo, come l'orchestratore li chiama, che forma ha una proposta, dove vive la knowledge, dove si ferma l'autonomia.

Non copre il catalogo GenUI (`02-genui.md`) né il motore ore/CCNL (zero AI, spec futura).

> **Lenti.** Lead `[AIEngineer]`. `[AIUxer]` su P-L (un solo parlante) e sul confine visibile. Dove divergono: cost-per-outcome; veto sul pubblicabile.

---

## 1. Problema & job-to-be-done

**Per chi.** Il **store manager** di Le Rocce (crea e aggiusta i turni ogni settimana). Secondari: il dipendente (consulta, dice preferenze), il titolare (non in questa edizione).

**Job.** Data la settimana che arriva, le schede persona, i turni passati e ciò che il negozio ha imparato: **produrre una o più bozze di turni e orari** già verificate sul CCNL, spiegate, e fermarsi. Il manager approva, modifica o rifiuta. Poi si pubblica.

Oggi lo fa su un foglio Excel/colorato. Quel foglio resta in `kb/turni/`. L'interfaccia non lo ripete: si lavora sui turni della persona (`02`).

---

## 2. Metrica d'esito

- **Accettazione bozza:** % di settimane in cui il manager pubblica una bozza AI con modifiche non sostanziali (spostamenti < 3 celle). Target pilota: ≥ 60% all'ultimo mese (`00` O1-KR4).
- **Tempo manager:** da 3–6 h a < 30 min per il piano settimanale.
- **Violazioni pubblicate:** 0. Se Compliance ha flaggato, lo stato `pubblicabile` è falso.
- **Cost-per-outcome:** costo inferenza per settimana chiusa (bozza accettata o esplicitamente rifiutata), non per chiamata.
- **Secondo:** % di decisioni umane che producono un aggiornamento della memoria del PV (misura se il loop #1 gira).

---

## 3. Vincoli

- Principi `00` §§2–3. AI Act alto rischio: log di ogni proposta e decisione. Art. 4: niente scoring individuale.
- Knowledge in markdown, in `kb/`. Niente database per persona/turni/memoria in questa edizione.
- Backend AI astratto (`generate` / `run`): fake in test, CLI in dev, API in prod. `[AIEngineer]`
- LLM output = input non fidato: schema validato al confine, scarto + retry sul mismatch.
- Costo: LLM solo dove serve ragionare o interpretare NL. Forecast numerico e check CCNL sono codice dove possibile.
- Il punto vendita non si ferma se l'AI è giù: i turni pubblicati restano visibili sul widget persona; la timbratura resta.

---

## 4. Approccio

**Router deterministico, LLM dentro gli agenti.** Approccio A, deciso in brainstorming. L'orchestratore è una macchina a stati. Non è un modello a scegliere chi parla.

### 4.1 Contratto di un agente

Un agente ha:

| Campo | Regola |
|---|---|
| `id` | stabile: `forecast` \| `scheduling` \| `compliance` \| `anomaly` \| `copilot` \| `secondo-pv` |
| input | JSON schema versionato |
| output | `Proposta` (sotto) — mai un side-effect sul mondo |
| mestiere | uno solo |
| LLM | solo se il mestiere richiede ragionamento o linguaggio |

Due invocazioni, stesso schema:

```
consult(agente, domanda, contesto) → Proposta
ciclo.invoca(agente, contesto_di_fase) → Proposta
```

`consult` non avanza lo stato del ciclo. `ciclo.invoca` sì.

### 4.2 Proposta

```
Proposta {
  id, agente, creato_at,
  tipo: previsione | bozza-turni | blocco | segnale | risposta | memoria,
  payload,            // structured, validato
  rationale,          // perché, in italiano
  fonti[],            // path kb/ o id dato
  confidenza,         // 0–1, opzionale
  varianti[],         // P-E: più bozze quando Scheduling propone
}
```

Il payload di `bozza-turni` è una settimana nello stesso vocabolario del tabellone: persona × giorno → fascia + mansione + note. Grounding gate `[AIUxer P-I]`: ogni `persona` e ogni `mansione` devono esistere in `kb/persone/*.md`. Altrimenti la cella si scarta con motivo, non si inventa un nome.

### 4.3 Roster

Un solo agente parla con l'umano: **Copilot**. Gli altri emettono dominio puro. `[AIUxer P-L]`

| Agente | Nel ciclo | In consulta | LLM? |
|---|---|---|---|
| **forecast** | fabbisogno per reparto/fascia da storia + note di settimana | «che copertura serve sabato?» | no, se la storia basta; sì solo per interpretare note libere (FESTA PROLOCO) |
| **scheduling** | 1–3 bozze turni/orari | «chi copre giovedì pomeriggio senza straordinario?» | sì per l'assegnazione morbida; vincoli hard = solver/codice |
| **compliance** | verifica CCNL/riposi/ore/minori su ogni bozza e sul consuntivo | «questo cambio rompe un riposo?» | no. Solo codice. Può **bloccare** (`pubblicabile: false`) |
| **anomaly** | dopo le timbrature | «le uscite anticipate sono anomale?» | sì, pattern; solo segnala |
| **copilot** | fuori ciclo: NL → `consult` o comando di ciclo | è l'interfaccia parlata | sì. Conferma prima di ogni write |
| **secondo-pv** | dopo una decisione umana, propone un aggiornamento di memoria | «cosa sa questo negozio dei sabati di dicembre?» | sì per distillare; la scrittura è una Proposta, confermata o auto-accettata solo se è un append su `kb/secondo/` senza cancellare |

Nessun altro agente in questa edizione. Ferie, multi-store, costo titolare: dopo, stesso contratto.

### 4.4 Orchestratore — macchina a stati

Stati del **ciclo settimana** (una macchina per punto vendita):

```
idle
  → carica_contesto
  → forecast
  → scheduling
  → compliance
  → attesa_umano          // gate. Qui si ferma.
       ├─ (modifica) → scheduling → compliance → attesa_umano
       ├─ (rifiuta)  → idle  + secondo-pv impara il rifiuto
       └─ (approva)  → pubblica  → monitora
                          → (consuntivo chiuso) → anomaly → secondo-pv → idle
```

Regole dure:

1. Non si salta `compliance` prima di `attesa_umano` né prima di `pubblica`.
2. `pubblica` è un atto umano (bottone). L'orchestratore non pubblica.
3. Se l'AI è giù, i `person-shifts` restano sull'ultimo pubblicato; niente nuova bozza. Degrado onesto. `[AIUxer P-D]`
4. I comandi di ciclo arrivano dal Copilot (traduzione NL) o dalla superficie (chip). L'orchestratore non interpreta il linguaggio.

`carica_contesto` è codice, non un agente. Seleziona:

- tutte le `kb/persone/*.md` del PV
- ultime N settimane in `kb/turni/` + stessa settimana dell'anno prima se esiste (N=8 default)
- `kb/secondo/` pertinente (retrieval, non dump)
- note operative della settimana (testata tabellone: festa, shooting, ordini)

Questo pacchetto è il **contesto condiviso** del giro. Gli agenti non tengono una memoria privata del negozio.

### 4.5 Knowledge base

Tre famiglie, tutte markdown, tutte umane-leggibili. Il tabellone scritto resta in `kb/turni/`; non è la UI (`02`).

| Famiglia | Path | Chi scrive | Immutabile? |
|---|---|---|---|
| Persona | `kb/persone/{slug}.md` | Copilot propone, persona o manager conferma | no: si aggiorna (preferenze, mansioni) |
| Turni | `kb/turni/YYYY-MM-DD.md` (lunedì) | `pubblica` scrive il piano; il consuntivo si **aggiunge**, non sovrascrive | piano pubblicato: sì |
| Secondo PV | `kb/secondo/*.md` | secondo-pv propone dopo una decisione | append-only |

Scheda persona contiene almeno: contratto ore, mansioni (vincoli di assegnazione), preferenze (vincoli morbidi), note. Esempio già in kb: giovedì pomeriggio libero (lezione di piano) → preferenza; «NO CHIUSURA» di Monia → preferenza da confermare; «PIZZE» di Debora → mansione.

Scheduling **deve** leggere le mansioni: non mette in pizze chi non ha quella mansione. Le preferenze si onorano se la copertura e il CCNL lo permettono; se no, la rationale lo dice.

`[AIEngineer]` Il loader di contesto ha un budget: non si concatenano 30 schede + 8 settimane intere nel prompt. Si assembla un riassunto deterministico (tabella persona×mansioni, ultime 4 settimane compresso, retrieval del secondo) e si passano i file grezzi solo all'agente che li chiede per path.

### 4.6 Secondo del punto vendita

Non è un secondo personale. Impara **solo** da decisioni umane:

- bozza accettata senza modifiche → «questo schema va»
- bozza modificata → diff: cosa ha spostato il manager
- bozza rifiutata → «non così»
- preferenza confermata in scheda → fatto della persona, non memoria del secondo

Il secondo distilla pattern di negozio («i sabati di dicembre vogliono due persone in più al bar»), non giudizi sulle persone. Vietato: produttività individuale, ranking, «Anna è lenta».

### 4.7 Jobs asincroni `[AIEngineer]`

Forecast, scheduling, anomaly girano in coda (stato, retry, idempotenza). Non nel request-path del widget. Il manager vede «bozza in preparazione» — stato vero dal job, non un `setTimeout` client.

Draft ≠ act: i worker preparano Proposte. Mai `pubblica`, mai write su scheda persona senza conferma. Write su `kb/secondo/` è append di una Proposta già accettata (default: auto-append se non cancella e non parla di una persona in modo valutativo; altrimenti conferma).

---

## 5. Confine di fiducia

| Atto | Chi |
|---|---|
| Proporre bozze, previsioni, segnali, aggiornamenti scheda/memoria | AI |
| Approvare / modificare / rifiutare / pubblicare turni | Umano (manager) |
| Confermare una preferenza o una mansione nuova in scheda | Umano (persona o manager) |
| Calcolare ore, maggiorazioni, riposi, pubblicabilità CCNL | Codice, zero AI |
| Mostrare il montante ferie/permessi | Codice, da file o Gamma (`04`). Mai LLM |
| Registro timbrature, export paghe | Codice, zero AI |
| Scrivere i turni pubblicati sul calendario Google della persona | Codice, dopo `pubblica` (`03`). Mai le bozze |

Compliance può **bloccare**. Non può riscrivere una bozza in silenzio. Se blocca, Scheduling può essere ri-invocato con i flag, oppure il manager sistema a mano.

Ogni proposta e ogni decisione umana si loggano (id, agente, input hash, versione prompt/modello, esito). Retention inferenza ≤ 30 giorni; audit delle decisioni umane più lungo (AI Act + uso interno).

---

## 6. Evals

Prima di costruire gli agenti, questi casi. Dataset iniziale = le due settimane già in `kb/turni/` più mutazioni.

| # | Caso | Gate |
|---|---|---|
| E1 | Scheduling riceve le schede Le Rocce + settimana tipo | ogni cella ha persona esistente e mansione che la persona possiede |
| E2 | Debora/Anna/Rolando/Mara sulle pizze | almeno una persona con mansione pizze in ogni fascia PIZZE POME della bozza, se il fabbisogno c'è |
| E3 | Preferenza «giovedì pomeriggio libero» in scheda | quella persona non è in fascia pomeridiana il giovedì, *oppure* rationale esplicita del perché no |
| E4 | Bozza che viola un riposo | Compliance → `pubblicabile: false`; orchestratore non offre Pubblica |
| E5 | Consulta «chi copre giovedì senza straordinario?» | Proposta schema-valida, fonti = path kb, zero side-effect |
| E6 | AI down | `person-shifts` sull'ultimo pubblicato; niente 200 finto su forecast |
| E7 | Manager modifica 2 celle e approva | secondo-pv riceve il diff; scheda turno pubblicata contiene il piano *modificato* |
| E8 | Tipo / persona / mansione sconosciuti in output LLM | drop + motivo, non render, non persist |

Canary online: tasso accettazione, violazioni pubblicate (=0), costo/settimana, job falliti.

---

## 7. Aperto / decisioni già prese

**Prese**

- Approccio A (router deterministico).
- Niente secondo personale.
- Secondo del PV sì.
- Schede MD per persone e turni passati.
- Mansioni = vincoli di assegnazione.
- Un solo parlante (Copilot).
- Pilota: Le Rocce.

**Aperti** (non bloccano 01)

- Decodifica `PLS`, `CAM` sul tabellone — non entra nel runtime finché non è in scheda.
- N (settimane di storia) restano 8 finché un eval non dice altrimenti.
- Motore CCNL Commercio/DMO: spec propria, prima del go-live su pubblicabile. Fino ad allora Compliance implementa i check che sappiamo (riposo settimanale, cap ore della scheda, minori se presenti).
- Auto-append del secondo vs conferma sempre: default come in 4.6, da rivedere dopo 4 settimane di pilota.

**Fuori**

- Payroll, biometrico, scoring individuale, multi-store, copilot dipendente come superficie primaria (il dipendente in questa edizione aggiorna la scheda e legge i turni; non parla col consiglio).

---

## 8. Use case

Scritti da **AIUxer**. Esercitano il contratto di questa spec.

### UC-03 Bozza, accetta, pubblica
- **Chi:** store manager di Le Rocce
- **Quando:** prima del lun 29/06; in kb c'è `2026-06-22` (festa Proloco) come storia
- **Fa:**
  1. Chip `genera-bozza` (o NL al Copilot). Guscio: `bozza in preparazione` dal job, non uno spinner finto.
  2. Ciclo: `carica_contesto` → forecast → scheduling → compliance → `attesa_umano`.
  3. Legge `proposal-pack`: `person-shifts` overlay di chi cambia (Anna pizze, Debora, Cesare C+B, Matteo 6-14) + `rationale` + `coverage-gap` (shooting gio, pizze pome).
  4. Matteo esce a 52h su contratto 40: se Compliance flagga, vede `compliance-block` e `pubblica` non c'è.
  5. `sposta-turno` su Matteo (toglie uno spezzone) → di nuovo scheduling/compliance → `attesa_umano`.
  6. `accetta-bozza` (preview di chi è toccato, chi perde un riposo) poi `pubblica`.
  7. Scrittura su `kb/turni/2026-06-29.md`; secondo-pv prende il diff, non un giudizio su Matteo.
- **Esito:** piano pubblicato *modificato dal manager*, zero violazioni, ciclo in `monitora`.
- **AI può / non può:** può proporre e spiegare; non pubblica, non salta compliance, non scrive il turno da sola.

### UC-04 Consulta senza muovere il ciclo
- **Chi:** store manager
- **Quando:** ciclo in `idle` o `attesa_umano`; serve il gio pomeriggio pizze senza straordinario
- **Fa:**
  1. Chip `consulta` o testo al Copilot: «chi copre giovedì pomeriggio senza straordinario?»
  2. Copilot fa `consult(scheduling, …)` — non avanza la macchina a stati.
  3. Risposta: `copilot-turn` + `person-shifts` di Debora e Anna (mansione pizze in scheda) + `rationale`.
  4. Fonti: `kb/persone/debora.md`, `kb/persone/anna-mondora.md`, `kb/turni/2026-06-22.md`.
  5. Nessun write. Per assegnare serve `sposta-turno` o un nuovo ciclo.
- **Esito:** sa chi può, con path kb; il ciclo è dove l'ha lasciato.
- **AI può / non può:** può consultare e mostrare una Proposta; zero side-effect, non assegna il giovedì.

### UC-05 AI giù, il pubblicato resta
- **Chi:** Anna Mondora; in parallelo lo store manager
- **Quando:** settimana 29/06 già pubblicata; forecast / scheduling / Copilot non rispondono
- **Fa:**
  1. Anna apre: `person-shifts` = ultimo pubblicato (lun 14-20, mar No, mer pizze, …). `person-balances` intatti.
  2. Copilota spento in modo onesto — niente 200 finto su forecast.
  3. Il manager tenta `genera-bozza`: il job fallisce visibile; nessuna bozza nuova.
  4. Timbratura e turni pubblicati restano usabili.
  5. Nessun `week-grid` imposto come «piano B».
- **Esito:** il negozio lavora sul pubblicato; la pianificazione nuova aspetta l'AI.
- **AI può / non può:** non può fingersi viva; il path deterministico non dipende da lei.
