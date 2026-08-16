# 04 — Ferie, permessi e Gamma

Specifica di **costruzione**. La persona vede il **montante** (residuo) di ferie e permessi. Due adattatori dietro lo stesso contratto: **file → knowledge base** (ora) e **TeamSystem Gamma** (tempo reale).

Zero AI sui numeri. Non è un workflow di richiesta/approvazione (quello resta in Gamma o arriva dopo). Non è il motore ore/CCNL.

> **Lenti.** Lead `[AIEngineer]` (porta, adapter, grounding dei numeri). `[AIUxer]` sul widget. I residui sono fatti: P-I, mai testo LLM.

---

## 1. Problema & job-to-be-done

**Per chi.** Ogni persona del PV. Il manager, in consulta, può vedere il montante di un collega **solo** se sta pianificando un `F` / permesso su di lei — non una rubrica di residui di tutti.

**Job.** Aprire l'app e sapere *quante ore/giorni mi restano*, con data di aggiornamento e provenienza. Oggi quel numero sta nel consulente / in Gamma / su un Excel. Deve stare accanto ai turni, sulla persona.

Due tempi:

1. **Ora.** Un file (export dello studio o del gestionale) si importa in `kb/`. Il widget legge quello.
2. **Poi.** Stesso widget, stessa forma: i numeri arrivano da **Gamma** (TeamSystem), aggiornati in tempo reale.

---

## 2. Metrica d'esito

- **Visibilità:** al primo paint, se esiste un saldo per me, lo vedo senza aprire un'altra app. Se non esiste, stato onesto «non ancora caricato» — non uno zero finto.
- **Fedeltà file:** dopo un import, i montanti in vista = file, persona per persona. Mismatch = 0.
- **Fedeltà Gamma:** p95 dello scarto `visto_at - aggiornato_in_gamma` < 60 s sul path «apro il widget».
- **Degrado:** Gamma giù → ultimo snapshot in kb + badge «non in tempo reale». Mai un 200 con zero inventati.
- **Privacy:** una sessione dipendente non legge i montanti degli altri (canary).

---

## 3. Vincoli

- Residuo = **fatto retributivo-adiacente**. Codice, zero AI. Il Copilot può *citare* il numero già validato, non stimarlo.
- SoT dei numeri: l'adapter attivo (file o Gamma). Il tabellone `F` è pianificazione, non decrementa da solo il montante.
- Token / credenziali Gamma **mai** in `kb/`.
- GDPR: residui sono dati del lavoratore. Minimizzazione: in UI solo i tipi che la persona può usare (ferie, permessi; ROL se il file/Gamma li porta).
- Unità: **ore**, con eventuale vista giorni = ore / ore_giorno della scheda (contratto). Non mischiare giorni e ore nello store.
- CCNL Commercio/DMO: maturazione e massimali li calcola Gamma (o lo studio nel file). Noi non reimplementiamo la maturazione in questa spec.
- `[AIEngineer]` una porta `Saldi`. Due adapter. La UI e Scheduling non sanno quale gira.

---

## 4. Approccio

### 4.1 Contratto di dominio

```
Saldo {
  persona,              // slug kb
  tipo: ferie | permessi | rol | ex_festivita | banca_ore,
  unita: ore,
  maturato,
  goduto,
  residuo,              // = maturato - goduto - prenotato_fonte  (lo dà la fonte; noi non ricalcoliamo se la fonte lo porta)
  prenotato_fonte,      // già approvato in Gamma/studio, se c'è
  aggiornato_at,
  fonte: file | gamma,
  fonte_ref,            // nome file / id movimento Gamma
}
```

`tipo` è un enum chiuso. Un tipo sconosciuto in import si scarta con log, non si inventa una riga.

Lettura:

```
saldi.di(persona) → Saldo[] | vuoto
saldi.aggiornati_at(persona) → timestamp | null
```

Scrittura: solo gli adapter. Nessun agente, nessuna chip «correggi residuo» in questa edizione.

### 4.2 Adapter `file` (ora)

Path: `kb/saldi/{slug}.md` — una scheda saldo per persona, stessa famiglia delle altre kb.

Import: un file dello studio (CSV o XLSX, un foglio, una riga per persona) entra da un comando deterministico, non da un agente.

```
import-saldi --file export-studio.csv --at 2026-08-16
```

Regole:

- Match persona: prima `codice_gamma` / `cf` se presenti in scheda, poi nome normalizzato. Riga non matchata → report, non silent drop di tutta la run.
- Sovrascrive lo snapshot di quella persona (non append di movimenti: per ora basta il montante).
- Scrive `fonte: file`, `aggiornato_at` = `--at` o mtime del file.
- Non tocca mansioni, preferenze, turni.

Forma della scheda (esempio):

```md
# Saldi — Anna Mondora

- persona: anna-mondora
- fonte: file
- fonte_ref: export-studio-2026-08-16.csv
- aggiornato_at: 2026-08-16

| tipo | maturato_ore | goduto_ore | prenotato_ore | residuo_ore |
|---|---|---|---|---|
| ferie | 160 | 48 | 16 | 96 |
| permessi | 32 | 8 | 0 | 24 |
```

Finché Gamma non è collegato, questo è ciò che il widget mostra.

### 4.3 Adapter `gamma` (tempo reale)

**Gamma** = suite HR/paghe TeamSystem usata dallo studio / dall'insegna. Espone residui ferie, permessi, ROL (stesso perimetro dell'app TeamSystem HR). Il contratto HTTP esatto si valida con lo studio (`[VALIDARE integrazioni]`): Integration Hub o API dello tenant. Questa spec fissa il *nostro* lato.

Comportamento:

1. Config per PV: endpoint, credenziali, mapping `slug ↔ id dipendente Gamma`.
2. Adapter `gamma` implementa `saldi.di(persona)` con **pull on read** + cache corta (default 30 s). Se Gamma offre webhook/push sui movimenti, si aggiunge come invalidazione cache — non è un prerequisito del primo taglio.
3. Ogni lettura riuscita materializza anche lo snapshot in `kb/saldi/{slug}.md` (`fonte: gamma`). È il fallback quando Gamma è giù, non una seconda verità.
4. Timeout ovunque. 5xx / rete → ultimo snapshot file/gamma + `stale: true`.
5. Job periodico (es. ogni 15 min) precarica i collegati, così il landing non aspetta Gamma.

Cambio adapter: flag di PV `SALDI_FONTE=file|gamma`. Stesso codice UI. Nessun if in `person-shifts`.

Fuori dal primo collegamento Gamma:

- richiedere ferie da TIME MACHINE verso Gamma
- scrivere giustificazioni
- leggere buste paga / CU

Solo **lettura residui**.

### 4.4 Superficie `[AIUxer]`

Nuovo widget, non un secondo home. Vive **sulla persona**, accanto a `person-shifts`, sempre per l'utente loggato.

| Tipo | Famiglia | Det/Gen | Cosa fa |
|---|---|---|---|
| **`person-balances`** | persona | Det | montanti ferie / permessi (e altri tipi se presenti). Fonte + `aggiornato_at` visibili |

```
person-balances {
  persona,
  voci[],             // { tipo, residuo_ore, residuo_giorni?, maturato, goduto }
  aggiornato_at,
  fonte,              // file | gamma
  stale?,             // true se fallback
}
```

Regole:

- Sempre montato per me, sotto o a lato di `person-shifts`. Non si naviga per trovarlo.
- `residuo_giorni` è display = `residuo_ore / ore_giorno` della scheda (es. 8 per full-time 40h). Se part-time, le ore_giorno stanno in scheda; se mancano, si mostrano **solo le ore**.
- `stale` o assenza di snapshot: copy onesta, mai `0`.
- Il Copilot può rispondere «quante ferie ho?» mappando questo widget (P-L: non se lo inventa). Grounding: il numero in chat = il numero nel widget.
- Manager: `person-balances` di un collega solo dentro una consulta / overlay bozza che la tocca (`F` o permesso). Niente lista PV-wide.
- Nessuna chip «modifica residuo». Chip `aggiorna-saldi` solo se `fonte: gamma` (forza pull) o, se `file`, non c'è (si re-importa da CLI).

### 4.5 Rapporto col piano turni

| Segnale | Dove vive | Effetto sul montante |
|---|---|---|
| `F` / permesso sul tabellone pubblicato | `kb/turni/` | nessuno, da solo |
| Residuo | `Saldi` | SoT |
| Prenotato in Gamma | `prenotato_fonte` | già nel residuo se la fonte lo dà |

Scheduling **legge** i saldi come vincolo morbido: non proporre una settimana di ferie se `residuo` ferie < ore proposte, e lo dice in rationale. Se il manager forza, Compliance non blocca (non è CCNL): è una segnalazione. Il montante reale si muove quando Gamma (o il prossimo file) lo dice.

---

## 5. Confine di fiducia

| Atto | Chi |
|---|---|
| Vedere i propri residui | La persona |
| Vedere i residui di un collega | Manager, solo in contesto di pianificazione su quella persona |
| Calcolare / correggere il residuo | Gamma o il file dello studio — non TIME MACHINE, non l'AI |
| Importare un file | Operatore / studio, comando deterministico |
| Collegare Gamma | Config di PV, non un agente |

Un numero uscito da un LLM non è un saldo. Se il Copilot non ha `saldi.di`, dice che non c'è dato.

---

## 6. Evals

| # | Caso | Gate |
|---|---|---|
| S1 | Import CSV con Anna 96h ferie / 24h permessi | `kb/saldi/anna-mondora.md` allineato; widget di Anna mostra 96 e 24, fonte `file` |
| S2 | Riga CSV nome sconosciuto | report; le altre persone importate; nessun file spazzatura |
| S3 | Login Anna senza file saldi | `person-balances` in stato vuoto, non zeri |
| S4 | Login Jessica, poi fetch `/saldi/anna-mondora` | 403 / vuoto. Nessun leak |
| S5 | `SALDI_FONTE=gamma`, Gamma 200 | widget = payload mappato; snapshot kb scritto; `stale` assente |
| S6 | Gamma 503 con snapshot precedente | widget = snapshot, `stale: true`, nessuna cifra nuova |
| S7 | Copilot «quante ferie ho?» senza saldo | niente numero; invita ad aspettare l'import / Gamma |
| S8 | Copilot stessa domanda con saldo 96 | risponde 96 (o giorni equivalenti) e cita la fonte |
| S9 | Scheduling propone 5 giorni F, residuo 16h | rationale esplicita; bozza possibile; nessun blocco Compliance |

---

## 7. Aperto / decisioni già prese

**Prese**

- Porta unica, due adapter (`file` ora, `gamma` dopo).
- Store in ore. Giorni = display.
- Snapshot kb anche sotto Gamma, per degrado.
- No write verso Gamma in questa spec.
- No correzione manuale del residuo in app.
- `F` sul piano ≠ decremento locale.
- Widget `person-balances` sempre visibile per me.

**Aperti** (non bloccano il file-adapter)

- Contratto HTTP Gamma (auth, path residui, id dipendente) — da chiudere con lo studio. Fino ad allora `SALDI_FONTE=file`.
- Formato esatto dell'export studio (colonne). Il comando di import accetta un mapping dichiarato, non «indovina le colonne» via LLM.
- ROL / ex festività / banca ore: nel contratto, in UI solo se presenti nella fonte.
- Richiesta ferie in-app verso Gamma: spec futura.

**Fuori**

- Payroll, cedolino, CU.
- Maturazione calcolata da noi.
- Multi-studio / più fonti contemporanee sulla stessa persona.

---

## 8. Use case

Scritti da **AIUxer**.

### UC-11 Vede il montante dal file
- **Chi:** Anna Mondora
- **Quando:** landing; esiste `kb/saldi/anna-mondora.md` (`fonte: file`, 2026-08-16)
- **Fa:**
  1. Accanto a `person-shifts` trova `person-balances` — non naviga.
  2. Ferie 96h (maturato 160, goduto 48, prenotato 16). Permessi 24h.
  3. Fonte `file` e `aggiornato_at` 16/08/2026 visibili.
  4. Se in scheda c'è ore/giorno, vede anche i giorni di display (96/8); senno solo le ore.
  5. Al Copilot: «quante ferie ho?» — risponde 96 e cita la fonte, stesso numero del widget.
  6. Nessuna chip per correggere. Un `F` sui `prossimi` non decrementa.
- **Esito:** sa il residuo senza studio né Gamma. I numeri = file.
- **AI può / non può:** può citare `saldi.di`; non stima, non ricalcola, non scrive il saldo.

### UC-12 Gamma stale
- **Chi:** Anna Mondora (`SALDI_FONTE=gamma`)
- **Quando:** apre l'app; Gamma 5xx / timeout; in kb c'è lo snapshot precedente (96 / 24)
- **Fa:**
  1. `person-balances` mostra lo snapshot, non zeri.
  2. `stale: true`: badge «non in tempo reale» e `aggiornato_at` vecchio.
  3. Chip `aggiorna-saldi` ritenta il pull; se fallisce, resta stale.
  4. Copilot sulla stessa domanda: stesso 96, dice che non è live.
  5. `person-shifts` non ne risente.
- **Esito:** ultimo dato onesto. Il landing non mente e non si ferma.
- **AI può / non può:** non inventa un residuo «circa»; se manca anche lo snapshot, niente numero.
