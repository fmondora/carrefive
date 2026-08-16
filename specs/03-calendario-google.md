# 03 — Calendario Google

Specifica di **costruzione**. Una persona collega il proprio account Google e trova i turni **pubblicati** sul calendario. Zero AI: è un effetto deterministico di `pubblica` (`01`).

Non copre Outlook/Apple, né inviti a colleghi, né la bozza non pubblicata.

> **Lenti.** Lead `[AIEngineer]` (OAuth, token, idempotenza, job). `[AIUxer]` sul widget/chip di collegamento e sullo stato visibile. Confine: la persona autorizza; il sistema non legge la sua vita privata sul calendario.

---

## 1. Problema & job-to-be-done

**Per chi.** Ogni persona del punto vendita (Anna, Matteo, il manager — stesso contratto).

**Job.** Collegare Google una volta. Da quel momento, i turni pubblicati compaiono sul suo calendario (orario, mansione, negozio). Se il piano cambia e viene ripubblicato, il calendario si aggiorna. Se si scollega, smette.

Oggi il tabellone vive su un foglio: il giovedì pomeriggio di piano e il turno si pestano. Il calendario è dove la persona *già* tiene la vita. I turni devono arrivarle lì, non chiederle di aprire un'altra app per sapere se lavora.

---

## 2. Metrica d'esito

- **Adozione:** % di persone attive con Google collegato e almeno un evento futuro a 4 settimane dal deploy pilota. Target: ≥ 60%.
- **Fedeltà:** dopo ogni `pubblica`, gli eventi futuri di una persona collegata coincidono col piano pubblicato (stesso giorno, fascia, mansione). Mismatch = 0 sul campione di eval.
- **Latenza:** eventi aggiornati entro 2 minuti dalla pubblicazione (coda, non request-path).
- **Revoca:** scollegare cancella *solo* gli eventi che abbiamo creato, entro 2 minuti. Il resto del calendario intatto.
- **Privacy:** zero lettura di eventi non nostri. Scope OAuth minimo.

---

## 3. Vincoli

- GDPR: data residency UE per i token; minimizzazione; revoca effettiva.
- Token **mai** in `kb/` (le schede sono leggibili). Store segreto, cifrato a riposo.
- Scope: creare/aggiornare/cancellare eventi su un calendario dedicato che *noi* creiamo. Non `calendar.readonly` sull'intero account. Non accesso a Gmail.
- Solo turni **pubblicati**. Bozze, overlay, proposte AI: mai.
- Timezone `Europe/Rome`.
- Un account Google ↔ una persona. Niente calendario condiviso del negozio che invita 30 email (RSVP, organizer, rumore).
- Degrado: se Google è giù, `pubblica` nel prodotto **riesce comunque**. Il sync ritenta. La persona vede lo stato sul widget, non un fallimento della pubblicazione.
- `[AIEngineer]` job idempotente, keyed per `(persona, data, fonte=turni-pubblicati)`.

---

## 4. Approccio

### 4.1 Cosa succede (non un invito RSVP)

Non mandiamo un "invito" da un calendario aziendale. La persona autorizza; noi scriviamo sul **suo** Google, in un calendario dedicato `Le Rocce — Turni` (nome fisso). Lo crea il primo sync; se lei lo cancella, al giro dopo lo ricreiamo.

Perché non invite/RSVP: niente "Accetta/Rifiuta" su un turno di lavoro, niente organizer nostro nella sua inbox, niente lista invitati che espone i colleghi.

`[AIUxer]` In UI si può dire «ricevi i turni sul calendario». È il job. L'implementazione è write sul suo calendar, non iCal invite.

### 4.2 Collegare / scollegare

1. Da `person-shifts` (o scheda), chip `collega-google`.
2. OAuth Google (schermata Google, non un form nostro di password).
3. Al ritorno: salviamo token + `google_sub` + email. In `kb/persone/{slug}.md` scriviamo solo il fatto non segreto:

   ```
   calendario:
     provider: google
     email: anna@gmail.com
     stato: collegato
     da: 2026-08-16
   ```

4. Primo sync: crea il calendario dedicato + upsert di tutti i turni **futuri** già pubblicati (orizzonte = stesso di `person-shifts`, default 14 giorni, e comunque tutta la settimana pubblicata corrente).
5. `scollega-google`: revoca token, cancella gli eventi *nostri* e (default) il calendario dedicato, toglie il blocco `calendario:` dalla scheda o lo marca `stato: scollegato`. Conferma obbligatoria.

Chi collega: **solo la persona sul proprio account**. Il manager non collega Google al posto di Anna (niente on-behalf in questa spec).

### 4.3 Cosa diventa un evento

| Sul piano | Sul calendario |
|---|---|
| Fascia oraria (es. 7-12, 14-20, spezzato 8-12 + 16-20) | Un evento per spezzone. Spezzato = due eventi. Titolo: mansione se c'è, senno «Turno — Le Rocce» |
| `R` riposo | Nessun evento (non occupare il giorno) |
| `F` ferie | Nessun evento (stesso). La persona ha già le ferie dove le tiene |
| `BORMIO`, `FESTA`, note (`PIZZE POME`, `NO CHIUSURA`) | Location / description. Testo dal piano, non riscritto da LLM |
| Assenza / «No» / cella vuota | Nessun evento; se ce n'era uno nostro quel giorno, delete |

Campi evento:

- `summary`: `Pizze — Le Rocce` / `Turno — Le Rocce`
- `start`/`end`: Europe/Rome, dalla fascia
- `location`: Le Rocce, Poggiridenti
- `description`: note del piano + «Turno pubblicato. Non rispondere a questo evento.»
- `extendedProperties.private.shift_key`: `{settimana}:{persona}:{data}:{idx_spezzone}` — idempotenza
- `extendedProperties.private.source`: `timemachine`
- `transparency`: `opaque` (occupa il tempo: è il punto, per il pianoforte del giovedì)
- `attendees`: vuoto
- `reminders`: default del calendario della persona (non li forziamo)

Niente elenco colleghi. Niente costo del lavoro. Niente rationale AI.

### 4.4 Quando si sincronizza

Trigger unico: transizione a `pubblica` in `01` (piano nuovo o ripubblicato dopo modifica).

Job `sync-calendario` per ogni persona con `stato: collegato`:

1. Carica i suoi spezzoni futuri dal piano pubblicato.
2. Elenca gli eventi nostri futuri sul suo calendario dedicato (`source=timemachine`).
3. Diff: upsert chiavi presenti, delete chiavi nostre assenti dal piano.
4. Passato: non si tocca (lo storico calendario resta, anche se il consuntivo differisce).

Bozza accettata ma non pubblicata: **nessun sync**.

Cambio scheda (preferenza, mansione): nessun sync. Il calendario segue il *piano*, non il desiderio.

### 4.5 Superficie `[AIUxer]`

Niente nuovo guscio. Sul `person-shifts` dell'utente:

| Stato | Cosa si vede |
|---|---|
| non collegato | chip `collega-google` |
| collegato | badge «Calendario on» + email mascherata + chip `scollega-google` |
| sync in corso / retry | badge onesto «In aggiornamento» — verità dal job |
| errore persistente | badge «Calendario in errore» + chip `riprova` / `scollega-google`. I turni nel widget restano. |

Il Copilot può spiegare e avviare `collega-google` (è un comando, poi redirect OAuth — l'AI non vede il token). Non inventa eventi.

`week-grid` non mostra lo stato calendario dei colleghi (privacy).

### 4.6 Fallimenti `[AIEngineer]`

- Token scaduto: refresh; se revocato da Google, `stato: da-ricollegare`, stop ai write, badge sul widget.
- 429 / 5xx Google: retry con backoff, cap tentativi, poi badge errore. `pubblica` già andata a buon fine.
- Calendario dedicato cancellato dall'utente: ricrealo al prossimo sync, ripopola i futuri.
- Evento nostro modificato a mano (orario cambiato su Google): al prossimo `pubblica` **sovrascriviamo** (il piano pubblicato vince). Non merge. Documentato in UI al collegamento.
- Due spezzoni stesso giorno: due `shift_key` distinti.

---

## 5. Confine di fiducia

| Atto | Chi |
|---|---|
| Autorizzare / revocare Google | La persona, su Google e da chip |
| Decidere *quali* turni esistono | Manager via `pubblica` (`01`) |
| Scrivere/aggiornare/cancellare eventi nostri | Codice, dopo `pubblica` o dopo collega |
| Leggere il resto del calendario Google | Nessuno. Fuori scope |
| Mandare bozze AI sul calendario | Vietato |

Non è un agente. Non produce `Proposta`. È un adattatore sul lato *dopo* la ratifica umana.

---

## 6. Evals

Dataset: settimane `kb/turni/2026-06-22` e `2026-06-29`, persona Anna Mondora + Matteo + Cesare (spezzati C+B).

| # | Caso | Gate |
|---|---|---|
| C1 | Anna collega Google, piano 29/06 già pubblicato | eventi = solo i suoi spezzoni futuri; zero eventi `R`; zero eventi di Debora |
| C2 | Spezzato Cesare 7-12 C / 16-20 B | due eventi, chiavi distinte, orari esatti |
| C3 | Manager ripubblica spostando Anna da mer 12-20 a 7-16 | un upsert, niente doppione mercoledì |
| C4 | Manager toglie Anna dal sabato e ripubblica | evento sabato nostro cancellato; gli altri restano |
| C5 | `pubblica` con Google 503 | piano pubblicato; job in retry; widget turni ok |
| C6 | Anna scollega | eventi `source=timemachine` + calendario dedicato spariti; token assente; scheda `scollegato` |
| C7 | Bozza non pubblicata che cambia i turni di Anna | zero chiamate Calendar API |
| C8 | Token store: grep su `kb/` dopo collega | zero refresh token / access token |
| C9 | Scope OAuth richiesto | non include gmail, non include calendar readonly globale |

Canary online: lag p95 sync, % persone in errore, 401 persistenti.

---

## 7. Aperto / decisioni già prese

**Prese**

- Write sul calendario dedicato della persona, non invite RSVP da un calendar aziendale.
- Solo pubblicati. Bozze mai.
- `R` e `F` non diventano eventi.
- Passato intoccato.
- Piano pubblicato vince sulle modifiche manuali agli eventi nostri.
- No on-behalf del manager.
- Token fuori da `kb/`.

**Aperti** (non bloccano la spec)

- Nome esatto del calendario (`Le Rocce — Turni` va bene finché il pilota è un PV).
- Promemoria: default utente, o un reminder a −2h fisso — default utente.
- Orizzonte oltre i 14 giorni se il manager pubblica a +3 settimane: syncare tutto il pubblicato futuro (la regola 4.4 vince sul default 14).

**Fuori**

- Outlook, Apple, file `.ics` scaricabile (si può aggiungere dopo, stesso contratto evento).
- Calendario unico del negozio condiviso.
- Sync bidirezionale (un evento creato da Anna non diventa un turno).
- Inviti a eventi del negozio (shooting, festa Proloco) oltre il suo turno.

---

## 8. Use case

Scritti da **AIUxer**.

### UC-09 Collega Google, primo sync
- **Chi:** Anna Mondora (solo lei; il manager non collega al posto suo)
- **Quando:** piano 29/06 pubblicato; Google non ancora collegato
- **Fa:**
  1. Su `person-shifts`, chip `collega-google`.
  2. OAuth Google (schermata Google, non un form nostro).
  3. Al ritorno: badge «Calendario on» + email mascherata + chip `scollega-google`.
  4. Primo sync: crea `Le Rocce — Turni`; upsert dei suoi spezzoni futuri.
  5. Sab e dom spezzati pizze = due eventi ciascuno. Ven `R` = nessun evento. Zero eventi di Debora.
  6. In scheda solo `calendario.stato: collegato`. Token fuori da `kb/`.
- **Esito:** i pubblicati occupano il suo Google (`opaque`). Il pianoforte del giovedì vede il conflitto lì.
- **AI può / non può:** Copilot può avviare il comando; non vede il token e non crea eventi.

### UC-10 Ripubblica, il calendario segue
- **Chi:** store manager pubblica; Anna ha Google collegato
- **Quando:** `pubblica` sposta Anna da mer 12-20 PIZZE POME a 7-16
- **Fa:**
  1. Il manager conferma `pubblica` (piano, non bozza).
  2. Job `sync-calendario` su Anna: upsert mercoledì, niente doppione.
  3. Se in un giro dopo toglie Anna dal sabato e ripubblica: delete dell'evento nostro; gli altri restano.
  4. Anna su `person-shifts`: badge «In aggiornamento», poi «Calendario on».
  5. Una bozza non pubblicata che la sposta: zero write su Google.
  6. Se Google è 503: `pubblica` è già ok; retry; i turni nel widget restano.
- **Esito:** calendario = spezzoni futuri del piano pubblicato, entro 2 minuti. Passato intoccato.
- **AI può / non può:** non sincronizza; è codice dopo ratifica umana. Bozze mai sul calendario.
