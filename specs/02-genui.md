# 02 — GenUI (superfici e catalogo)

Specifica sorella di `01`. Definisce **dove** si lavora, **quali tipi** il sistema può mostrare, e il confine di fiducia visibile. Non orchestra gli agenti e non calcola le ore.

> **Lenti.** Lead `[AIUxer]`. `[AIEngineer]` su registry, enum ⊆ renderer, coda, costo. Invarianti da AIUxer P-A–P-L.
>
> **Frame (principio 5).** Il tabellone è il *vecchio* foglio — resta come **knowledge** (`kb/turni/`), quasi non si vede come UI. L'unità dell'interfaccia è la **persona**.

---

## 1. Problema & job-to-be-done

Una persona deve **sapere sempre i suoi turni** — quello di oggi e quelli che arrivano — senza aprire un foglio di 30 righe. Il widget è suo, è lì, non si naviga per trovarlo.

Il manager pianifica **per persone e buchi**, non per celle di un Excel: chiede una bozza, vede chi cambia (gli stessi widget, in overlay), accetta o sistema, pubblica. Il tabellone esiste come vista di emergenza, non come casa.

Job:

1. Aprire l'app e vedere *i miei* turni (ora + prossimi). Sempre.
2. Dire una preferenza («giovedì pomeriggio ho pianoforte») e vederla entrare in scheda.
3. (Manager) generare una bozza, vedere l'effetto sulle persone toccate, coprire i gap, pubblicare.
4. (Manager, raro) aprire il tabellone intero se serve una vista d'insieme.

Il dipendente non è più un utente di serie B: ha la stessa atomica del manager (`person-shifts`). Cambia solo cosa può confermare.

---

## 2. Metrica d'esito

- **Il widget persona è la casa:** al primo paint, `person-shifts` dell'utente loggato è a schermo. Nessun tabellone al landing.
- **Tabellone quasi invisibile:** < 10% delle sessioni manager aprono `week-grid`. Se sale, il frame è sbagliato.
- **Conferme consapevoli:** ogni Pubblica e ogni write su scheda ha preview (chi è toccato, cosa cambia).
- **Catalogo chiuso:** 0 tipi unknown al renderer (canary E8 di `01`).
- **Degrado:** con AI giù, `person-shifts` continua a mostrare l'ultimo piano pubblicato.

---

## 3. Vincoli

- Principio 5 > 11 sulla *superficie*: si cambia frame. Il 11 vale sulla knowledge (i file `kb/turni/` restano il tabellone scritto; non si butta la storia).
- P-A: l'AI sceglie *tipi*, non markup.
- P-L: solo il Copilot emette widget/chip. Gli altri agenti emettono dominio; la vista mappa.
- P-I: fatti (nomi, ore, mansioni) passano dal grounding gate.
- P-F: un'azione inietta il prossimo widget *nello stesso flusso*. Non si viene sbalzati sul tabellone.
- Un vocabolario, non uno per agente.
- `[AIEngineer]` enum del modello ⊆ Renderer. Registry unico prima dello stream.
- Aspetto: `06-design-system.md` (Beautiful UI + fresco). Il catalogo non cambia forma per estetica.

---

## 4. Approccio

### 4.1 Due famiglie, tre superfici

| Famiglia | Superficie | Chi | Generativa? |
|---|---|---|---|
| **Persona** | Home: sempre `person-shifts` | Tutti | No. Deterministico. È il guscio. |
| **Conversazionale** | Copilota (rail / pannello) | Tutti | Sì. Unico slot generativo. |
| **Insieme** | Tabellone `week-grid` | Solo manager | No. Vista secondaria, dietro chip `apri-tabellone`. Quasi mai. |

Il Copilot **compone tipi del catalogo** o **comanda il ciclo**. Non ridisegna il tabellone. Una bozza si vede come `person-shifts` delle persone toccate + `coverage-gap` + `compliance-block`.

### 4.2 Guscio vs catalogo

**Guscio** (non è catalogo, non lo emette l'LLM):

- chi sono (nome, punto vendita)
- slot fisso: `person-shifts` dell'utente
- stato del ciclo, se manager (`idle`, `bozza in preparazione`, `attesa tuo ok`)
- ingresso copilota (campo + chip)

Niente griglia 30×7 nel guscio.

**Catalogo** (chiuso, versionato). Atomi · widget · chip.

#### Atomi

`orario` · `etichetta-mansione` · `badge-stato` (R, F, BORMIO, …) · `nome-persona` · `giorno`

#### Widget — LLM-selectable ⊆ Renderer

| Tipo | Famiglia | Det/Gen | Cosa fa | Chi lo decide |
|---|---|---|---|---|
| **`person-shifts`** | persona | Det | i turni di *una* persona: **ora** (o oggi) + **prossimi**. Sempre montato per l'utente. Stesso tipo, riusato per gli altri in una bozza | mapping da `kb/turni/` + bozza. L'LLM può *scegliere di mostrarne un altro* (es. «i turni di Anna»), non inventarne il contenuto |
| **`person-balances`** | persona | Det | montante ferie/permessi (`04`). Sempre per me, accanto a `person-shifts` | mapping da `saldi.di`. Mai LLM |
| `coverage-gap` | insieme | Det | buco: fascia, reparto, teste mancanti — lista, non griglia | mapping forecast vs piano |
| `compliance-block` | insieme | Det | violazioni, blocca Pubblica | mapping da Compliance |
| `proposal-pack` | insieme | Det* | 1–3 varianti; ogni variante è un insieme di `person-shifts` toccati, non un tabellone | Scheduling produce; vista mappa |
| `rationale` | entrambe | Gen copy | perché | Copilot la mostra; fatti no |
| `diff-edit` | persona | Det | cosa cambia sui *miei* / su *questa* persona vs pubblicato | codice |
| `scheda-preview` | conversazionale | Det* | diff sulla `scheda.md` | Copilot chiede conferma |
| `secondo-note` | persona / insieme | Det | «il negozio sa che…» | mapping da secondo-pv |
| `copilot-turn` | conversazionale | Gen | un turno: testo + chip + widget | Copilot |
| `week-grid` | insieme | Det | il tabellone intero | **non** nel landing, **non** scelto di default dal Copilot. Solo chip `apri-tabellone` |

\* Det* = forma fissa, contenuto da Proposta validata.

#### Contratto di `person-shifts`

```
person-shifts {
  persona,            // slug kb
  adesso,             // turno in corso | null se libera / fuori orario
  prossimi[],         // turni futuri pubblicati (e, se bozza, quelli proposti)
  orizzonte,          // default: oggi → +14 giorni, o fine ultima settimana pubblicata
  ore_periodo,        // calcolato in codice
  overlay?,           // bozza | pubblicato
}
```

Regole:

- **Sempre visibile** per l'utente loggato. Chiudere il copilota non lo toglie.
- `prossimi` include riposi (`R`) e ferie (`F`) — sono turni di vita, non assenze da nascondere.
- Se c'è una bozza non pubblicata che tocca quella persona, `overlay: bozza` + `diff-edit`. Non si sostituisce in silenzio il pubblicato.
- Grounding: `persona` e ogni `mansione` esistono in kb, altrimenti drop della riga con motivo.

`proposal-pack` onora P-E: più varianti come *insiemi di persone che cambiano*, non come tre Excel.

#### Chip — vocabolario d'azione chiuso

| Chip | Atto | Conferma extra? |
|---|---|---|
| `consulta` | apre il copilota sul widget / sulla persona | no |
| `salva-preferenza` | write scheda persona | sì (`scheda-preview`) |
| `apri-scheda` | vista deterministica della md | no |
| `genera-bozza` | avvia il ciclo (manager) | no (prepare) |
| `accetta-bozza` | verso pubblica | sì: preview delle `person-shifts` toccate |
| `scegli-variante` | una delle N | no |
| `rifiuta-bozza` | idle + secondo impara | sì: motivo opzionale |
| `pubblica` | write `kb/turni/` | sì, solo se `pubblicabile` |
| `sposta-turno` | modifica un turno sulla persona, poi ri-compliance | no sul gesto; Pubblica resta confermata |
| `apri-tabellone` | monta `week-grid` | no. Vista, non atto. Non è nel landing |
| `collega-google` | OAuth + primo sync (`03`) | no sul click: è il consenso Google |
| `scollega-google` | revoca + cancella eventi nostri (`03`) | sì |

Testo libero sempre attivo accanto alle chip. Il Copilot non inventa chip.

**Fuori catalogo:** HTML libero, canvas, chat-generica, un widget per agente, tabellone come home.

### 4.3 Composizione `[AIUxer #19 + AIEngineer registry]`

**Landing (tutti).** Guscio + `person-shifts(me)` + `person-balances(me)`. Stop.

**Preferenza.** «Giovedì ho pianoforte» → `copilot-turn` + `scheda-preview` + chip `salva-preferenza`. Il `person-shifts` resta. Se la preferenza è confermata, i `prossimi` non si riscrivono da soli: entra nello Scheduling al prossimo ciclo.

**Bozza (manager).**

1. Chip `genera-bozza` o NL al Copilot.
2. Coda. Stato job nel guscio — verità server.
3. `Proposta` `bozza-turni` (+ eventuale `blocco`).
4. Mapping: persone toccate → stack di `person-shifts` con `overlay: bozza` + `diff-edit`; buchi → `coverage-gap`; flag → `compliance-block`; `rationale`.
5. Chip: `accetta-bozza` | `scegli-variante` | `rifiuta-bozza` | `consulta`. `pubblica` solo se `pubblicabile` e accettata.
6. `week-grid` **non** si apre.

**Tabellone.** Solo se il manager preme `apri-tabellone`. Si può chiudere. Non è uno stato del ciclo.

### 4.4 Grounding visivo

- Persona/mansione non in kb: niente nome inventato.
- Ore e `ore_periodo`: codice, mai testo LLM.
- Generated copy marcata. I fatti citano il path (`kb/persone/anna-mondora.md`, `kb/turni/2026-06-22.md`).
- Chi non è nella stanza (`00` §3.3): sulla preview di Pubblica, lista di `person-shifts` toccati (chi perde un riposo, chi fa la terza domenica). Mapping, non un sesto agente.

### 4.5 Maturità di questa edizione `[AIUxer §2]`

**L2** sul widget persona (esito della bozza → secondo). **L3** solo retrieval del secondo-pv. **L4** no.

Anticipazione: «domenica sei in pizze» sta già in `person-shifts.prossimi`. «Domenica il banco pizze è scoperto» è `coverage-gap` per il manager. Niente spam proattivo.

---

## 5. Confine di fiducia (visibile)

| Cosa si vede | Cosa non può fare da sola |
|---|---|
| I miei turni, overlay bozza, rationale, gap, blocco | Pubblicare |
| Preview scheda | Scrivere la scheda senza `salva-preferenza` |
| Stato job | Fingere che la bozza sia pronta |
| Tabellone (se aperto) | Pubblicare da lì senza lo stesso gate |

`pubblica` e `salva-preferenza` sono bottoni del guscio / chip confermate. I tool del Copilot tornano solo Proposte (P-C).

---

## 6. Evals

| # | Caso | Gate |
|---|---|---|
| U1 | Login come Anna Mondora, settimana 29/06 in kb | primo paint = `person-shifts` di Anna (lun 14-20, mar No, mer pizze, …). Zero `week-grid` nel DOM |
| U2 | Login come Matteo, stessa kb | `adesso`/`prossimi` allineati alla sua riga 6-14 / spezzati; non vede le 30 righe |
| U3 | Bozza che tocca Debora e Cesare | `proposal-pack` = i loro `person-shifts` in overlay; non un tabellone |
| U4 | Compliance blocca | `compliance-block` visibile; `pubblica` assente |
| U5 | «giovedì pomeriggio ho pianoforte» | `scheda-preview`; nessun write; `person-shifts` resta a schermo |
| U6 | Tipo `foo-widget` | drop, UI invariata |
| U7 | AI down | `person-shifts` dall'ultimo pubblicato; copilota spento in modo onesto |
| U8 | `apri-tabellone` | `week-grid` compare; chiuderlo torna alla home persona |
| U9 | `genera-bozza` | non naviga via; non apre il tabellone; stato job nel guscio |

`[AIEngineer]` canary di renderer + registry, fixture di Proposta, senza rete modello.

---

## 7. Aperto / decisioni già prese

**Prese**

- Unità UI = persona. `person-shifts` è la casa, per tutti.
- Tabellone = knowledge + vista rara. Non guscio, non landing.
- Un solo slot generativo: Copilot.
- Catalogo chiuso. Niente HTML libero.
- Preview obbligatoria su Pubblica e su write scheda.

**Aperti** (non bloccano il primo renderer)

- Orizzonte esatto di `prossimi` (14 giorni vs fine settimana pubblicata) — partire da 14.
- Come il manager *scopre* chi non è in bozza (solo gap, o anche «mostra Simona»). Default: gap + persone toccate. Il resto è consulta.
- Rail vs pannello del Copilot — `surface-map`.
- Varianti default 1 vs 3 — partire da 1.

**Prossimo passo di processo**

Skill `surface-map` su *questo* frame (persona-first) → scelta layout → `project-book` → implementazione da Book §09.

---

## Loop A2 (2026-08-16)

A1 ha chiuso: riga `coverage-gap` = atto; approval sulla home; tabellone = settimana del ciclo; composer spento solo se l’AI è giù; Anna invariata.

**A2 fissa tre contratti di superficie** (zero tipi nuovi):

1. **`compliance-block` (solo `violazioni`)** è un atto come il gap. Tap → `person-shifts` della persona + `sposta-turno` sulle celle che possono sciogliere il blocco. Le `segnalazioni` restano testo.
2. **Dopo un tap sul buco** il soggetto è *quel* buco: i candidati stanno sotto la riga scelta, non sotto le altre quattordici. La card candidato **non** usa `adesso` (è il giorno del buco + overlay/diff).
3. `scegli-variante` solo se le varianti sono > 1.

Evals da aggiungere: U-blocco-gesto (Matteo 52h → suoi turni + sposta; dopo accorcio, blocco tetto sparisce se le ore ≤ tetto). U1 e U4 restano.

Varianti default 1 (aperto di sopra): **chiuso in A2** — n=1, niente chip scegli.

---

## Loop A3 (2026-08-17)

A2 ha chiuso: blocco = atto; esito sotto la riga; `adesso` non mente; `Pubblica` torna dopo accetta se il tetto è a posto.

**A3.** I buchi **non** vetoano `pubblica`. Devono però essere *detti* e *attraversabili*:

1. `coverage-gap` non è un muro di 15 chip. Mostra il conteggio («N buchi · non bloccano») e **una** riga primaria (prossimo copribile). Il resto in disclosure. Tap invariato.
2. Approval `accetta` / `pubblica` elenca il residuo («restano N buchi») *prima* del sì. Non diventa veto.
3. Dopo `sposta-turno` confermato: non scaricare la coda sul muro. Aprire il **prossimo** buco con candidati (stesso `consulta`), o empty onesto se nessuno è copribile.

Evals: U-residuo-pubblica (dopo Matteo sciolto + accetta, testo «buchi» + chip pubblica). U1 e U4 restano.

---

## Loop P1 (2026-08-17) — persona, non A3

A3 è del manager. Questo loop è il job dipendente: **vedere e dichiarare**, non pubblicare.

Il composer è il **gateway** della pipeline (`01` Loop P1), non chat-casa e non un `if` su «pianoforte».

1. NL → intent chiuso → `consult` o fetch → widget. «ciao!» = `saluto` + chip. **Mai** Scheduling di default.
2. Tap su un giorno di `person-shifts(me)` → stesso intent `preferenza` → `scheda-preview` + `salva-preferenza`. I pubblicati non si riscrivono (UC-07).
3. Chip sul widget e nel composer = gli stessi intent. Testo libero per regole e «posso scambiare?» (proposta, non write).

Fuori: marketplace swap, `coverage-gap` in casa Anna, nuovo tipo disponibilità.

Evals: U-p-cella (tap gio → preview, kb invariata finché conferma). U-p-ciao (POST «ciao!» → niente turni di colleghi, composer acceso, almeno una chip utile). U1 resta.

---

## Loop P2 (2026-08-17)

P1 chiuso: gateway + tap. **P2:** il tap su un giorno è *quel* giorno.

- Vincolo dal tap: scope = ISO della cella (`Preferenza.data`). Preview: «solo il 02/07».
- Chip nello stesso preview: «tutti i giovedì» → weekday, senza data (mestiere già di UC-07 / NL).
- `viola()` onora `data` se c’è.
- Enum intent: **non** si allarga. `copri` resta ombrello (ratifica delta P1).

Evals: U-p-data (tap 02/07 → data 2026-07-02; gli altri gio non violati). U5 ricorrente resta.

---

## Loop P3 (2026-08-17)

P2 chiuso: tap = data. **P3:** un vincolo di fascia è violato se il turno **si sovrappone** a quella fascia, non se *inizia* in quella fascia.

`no_pomeriggio: gio` ∩ turno 7-16 = sì. Altrimenti UC-07 è una write che Scheduling non legge (E3 «onorata o spiegata» non scatta). Strumento già in `domain/ore.py`: `ore_in_fascia`.

Eval: U-p-sovrapposizione (`no_pomeriggio` + 7-16 → viola True; + solo 7-12 → False). E3 resta.

---

## 8. Use case

Scritti da **AIUxer**. Esercitano il catalogo e il landing.

### UC-06 Landing: i miei turni
- **Chi:** Anna Mondora
- **Quando:** primo paint, login, settimana 29/06 in kb
- **Fa:**
  1. Apre l'app.
  2. Guscio: lei, Le Rocce, `person-shifts(me)` + `person-balances(me)`. Stop.
  3. `adesso` / oggi e `prossimi` = 14-20, No, 12-20 PIZZE POME, 7-16, `R`, spezzati pizze.
  4. `ore_periodo` 41, da codice, non da testo Copilot.
  5. Chiude il copilota se era aperto: i due widget restano. Zero `week-grid`.
- **Esito:** la casa è la persona. Il tabellone non è nel landing.
- **AI può / non può:** non emette il guscio e non inventa orari; può solo *scegliere di mostrare* un altro `person-shifts` in consulta.

### UC-07 Preferenza: pianoforte / NO CHIUSURA
- **Chi:** Anna Mondora; stesso gesto per Monia
- **Quando:** Anna vede gio 02/07 alle 7-16 e ha lezione di pianoforte il pomeriggio
- **Fa:**
  1. Sul proprio `person-shifts` scrive al Copilot: «giovedì pomeriggio ho pianoforte».
  2. Arriva `copilot-turn` + `scheda-preview` su `kb/persone/anna-mondora.md` (preferenza: no pomeriggio del giovedì).
  3. Il `person-shifts` resta; i `prossimi` pubblicati non si riscrivono.
  4. Conferma con `salva-preferenza`.
  5. Monia, stesso flusso sulla nota del 23/06: «no chiusura» → `scheda-preview` + `salva-preferenza` su `kb/persone/monia.md`.
  6. Entra nello Scheduling solo al prossimo `genera-bozza`, se copertura e CCNL lo permettono.
- **Esito:** fatto in scheda, confermato da lei. Non è memoria del secondo.
- **AI può / non può:** può proporre il diff; non scrive la scheda senza `salva-preferenza` e non sposta i pubblicati.

### UC-08 Bozza come persone toccate
- **Chi:** store manager
- **Quando:** bozza pronta che sposta Debora e Cesare (pizze / spezzati C+B)
- **Fa:**
  1. Resta sulla home persona. Non naviga. `week-grid` chiuso.
  2. `proposal-pack` = `person-shifts` di Debora e Cesare, `overlay: bozza` + `diff-edit` vs pubblicato.
  3. Se manca una testa pizze pome: `coverage-gap`. Se un riposo è rotto: `compliance-block` e niente `pubblica`.
  4. `rationale` a lato (copy generata; fatti da path kb).
  5. Chip `scegli-variante` / `accetta-bozza` / `rifiuta-bozza` / `consulta`. `pubblica` solo dopo accetta e se `pubblicabile`.
  6. Non preme `apri-tabellone`. Se lo fa, è vista: chiuderla torna alle persone.
- **Esito:** capisce chi cambia senza il foglio 30×7.
- **AI può / non può:** Scheduling emette dominio; Copilot mappa i widget. Nessuno apre il tabellone al posto suo.
