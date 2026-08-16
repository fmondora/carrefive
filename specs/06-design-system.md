# 06 — Design system (fresco, AI-native)

Specifica di **costruzione visiva**. Come si *sente* TIME MACHINE. Il catalogo dei tipi resta `02`. Qui: tono, token, e la mappa verso i primitive di [Beautiful UI](https://www.beautifului.dev/).

> **Lenti.** Lead `[AIUxer]`. `[AIEngineer]` su token come codice (CSS vars, no magic number sparsi).
>
> **Riferimento.** Beautiful UI = primitive per interfacce AI-native (loader con tempo, thinking traccia, approval card, tool chip, recommendation, diff, prompt bar). Non si copia il demo gelato. Si copia la *grammatica*: aria, conferma prima dell'atto, fonti in chiaro, chip chiuse.
>
> **Tono: fresco.** Mattina in negozio, carta chiara, aria. Non gestionale HR grigio, non promo da volantino, non viola-gradient da template AI.

---

## 1. Problema & job-to-be-done

Anna apre e deve sentire **chiaro, leggero, suo** — non «un altro Excel del capo». Il manager conferma una bozza come su un'approval card Beautiful UI, non su un modal da 2005.

Job: un sistema visivo che

1. rende `person-shifts` la cosa più bella e più grande della pagina;
2. rende ovvio cosa è fatto (orario, saldo) e cosa è proposta AI;
3. rende le conferme (`pubblica`, `salva-preferenza`) *piacevoli da prendere sul serio*.

Una cosa da ricordare al primo sguardo: **i miei orari, su carta chiara, come un biglietto fresco — non un tabellone.**

---

## 2. Metrica d'esito

- Landing Anna: un ospite riconosce «i suoi turni» in < 2 s. Nessun chrome da dashboard.
- Overlay bozza: si capisce *chi* cambia senza leggere una tabella 30×7.
- Contrasto testo/carta ≥ WCAG AA (4.5:1 body, 3:1 large).
- 0 viola-gradient, 0 Inter come font primario, 0 icon-in-cerchio-colorato a tre colonne (anti-slop).
- I token vivono in un solo file (`tokens` / CSS vars). Un hex sparso nel componente = fail review.

---

## 3. Vincoli

- Catalogo `02` non si allarga «perché Beautiful UI ha 19 componenti». Si *mappano* i nostri tipi sui loro primitive. Tipo nuovo = emendamento `02`, non un one-off.
- Guscio deterministico, slot generativo = Copilot (`02`). Il design non fa diventare tutto chat.
- `05`: niente vita privata in evidenza (pianoforte = vincolo, non headline).
- Accessibile: focus visibile, chip ≥ 44px touch, `prefers-reduced-motion`.
- Mobile-first per il dipendente (il telefono in corsia). Manager può allargare, non il contrario.

---

## 4. Approccio

### 4.1 Direzione

| Asse | Scelta | Perché |
|---|---|---|
| Estetica | **Fresco editoriale** — carta, aria, un accento vegetale | Le Rocce / Valtellina / «fresco» di banco, non SaaS navy |
| Decorazione | Intenzionale e poca: una linea, un'ombra morbida, un accento di reparto | Beautiful UI è pulito, non massimalista |
| Layout | Ibrido: colonna unica sulla persona; editoriale solo sul landing | Il 30×7 è il nemico |
| Colore | Restrained: 1 accento + neutri caldi. Il colore *segnala* (bozza, blocco, gap) | |
| Motion | Funzionale: 150–250ms ease-out. Loader con tempo trascorso (Beautiful UI #01) | |
| Densità | Comoda. I numeri (ore) sono grandi. Le note sono piccole | |

### 4.2 Token

**Superfici**

| Token | Hex | Uso |
|---|---|---|
| `carta` | `#F6F1E8` | fondo pagina |
| `carta-alta` | `#FFFcf7` | card (`person-shifts`, approval) |
| `inchiostro` | `#1C1915` | testo |
| `inchiostro-muto` | `#6B6459` | meta, fonti, `aggiornato_at` |
| `linea` | `#E6DFD2` | bordi |
| `foglia` | `#2A7A56` | accento, chip primaria, «pubblicato» |
| `foglia-acqua` | `#E4F3EB` | chip/badge soft |
| `albicocca` | `#C45C26` | bozza / overlay / attenzione |
| `albicocca-acqua` | `#F8E6D8` | `diff-edit`, `overlay: bozza` |
| `rosso-blocco` | `#B42318` | solo `compliance-block` |
| `ambra-gap` | `#B45309` | solo `coverage-gap` |

Dark mode: non in questa edizione. Il fresco è luce.

**Tipo**

| Ruolo | Font | Nota |
|---|---|---|
| Display (nome, «Adesso», ora grande) | **Fraunces** | serif umido, un po' di Valtellina, non Inter |
| Body / UI | **Source Serif** no — **Source Sans 3** | umanista, tabulare ok |
| Ore e saldi | Source Sans 3 `tabular-nums` | allineamento 6-14 / 16-20 |
| Mono (path kb, `shift_key`) | **IBM Plex Mono** | raro, solo fonti |

Scala: 14 body · 16 UI · 20 titolo card · 32–40 ora «adesso» · 12 meta.

**Spazio:** base 8. Card padding 24. Gap stack 16. Raggio card 16, chip 999, input 10.

**Ombra:** una sola, morbida, sotto `carta-alta`. Niente glassmorphism.

### 4.3 Mappa Beautiful UI → catalogo `02`

Si implementano i *nostri* tipi con la grammatica loro. Non si importa la libreria per intero.

| Primitive Beautiful UI | Da noi | Come si vede |
|---|---|---|
| **01 Loading** (tempo elapsed) | job ciclo / sync calendario | «Bozza in preparazione · 12s» — verità server (`01`) |
| **02 Thinking** (traccia espandibile) | Copilot, opzionale | passi: consultò scheduling → fonti kb. Chiuso di default |
| **03 Streaming + fonti + follow-up** | `copilot-turn` | testo stream; fonti = path `kb/…` cliccabili; follow-up = chip del catalogo, non domande inventate |
| **04 Approval card** | `scheda-preview`, `accetta-bozza`, `pubblica` | domanda in chiaro + scelte chiuse + niente atto al click cieco |
| **05 Tool chips** | chip `02`/`03` | stesso vocabolario chiuso; stato running/done sul job |
| **06 Task rows** | stato ciclo, sync, pull Gamma | riga: nome job, conteggio, completed/failed |
| **07 Chat** | rail Copilot | un thread, non tab «flavors». Il tabellone non è una tab |
| **08 Prompt bar** | composer | testo libero + `@` persona/settimana (allowlist) + `/` comandi = chip (`genera-bozza`, `collega-google`) |
| **09 Recommendation + confidence** | `proposal-pack` + `rationale` | «Propongo questi cambi» + meter solo se c'è `confidenza`; Accept = `accetta-bozza` |
| **10 Context cards** | `secondo-note`, fonti | chunk + source (`kb/turni/2026-06-22.md`) |
| **11 Diff table** | `diff-edit` | **non** una tabella menu: riga per turno che cambia (mer 12-20 → 7-16) |
| **12/13 Records / filter** | `week-grid` | solo se `apri-tabellone`. Stile fresco, non Excel 2003. Quasi mai |
| **15 Search** | command palette | stessi comandi del prompt bar |
| **16 Insight cards** | `person-balances`, `coverage-gap` | una card, un fatto, fonte + `aggiornato_at` |
| 17 Code / 18 Fine-tune / 19 Selection | **fuori** | non è un IDE |

**Cosa non prendere da Beautiful UI:** densità da CRM, tabelle lunghe come home, inspector «Flavor card Adjust», codice che scorre. Quello è il loro demo. Il nostro landing è due card: turni + saldi.

### 4.4 Anatomia delle card (landing)

```
┌─ person-shifts ─────────────────────┐
│ Anna Mondora              Le Rocce  │  Fraunces 20
│                                     │
│ Adesso                              │  muto 12
│ 14–20  ·  pizze                     │  Fraunces 36 / foglia se in turno
│                                     │
│ Prossimi                            │
│ mar  No                             │
│ mer  12–20  pizze pome              │
│ gio  7–16                           │
│ …                                   │
│ 41h su 40                           │  tabular, muto
│ [consulta] [collega-google]         │  chip
└─────────────────────────────────────┘

┌─ person-balances ───────────────────┐
│ Ferie    96 h                       │  grande
│ Permessi 24 h                       │
│ file · 16 ago                       │  muto; se stale: albicocca
└─────────────────────────────────────┘
```

Reparto: un punto colore 8px, non un riempimento riga da tabellone. Overlay bozza: bordo `albicocca`, non un flash su tutta la pagina.

Generated copy (`rationale`, testo Copilot): un segno discreto «proposta» (P-I). I fatti no.

### 4.5 Stati onesti (P-D)

| Stato | Vista |
|---|---|
| AI giù | card pubblicate restano; composer spento con una riga «Copilota non disponibile» |
| Job in corso | loader #01 + secondi |
| Compliance blocca | card `rosso-blocco`, chip `pubblica` assente (non disabled-misterioso) |
| Saldo stale | badge «non in tempo reale» `albicocca` |
| Vuoto saldi | «Non ancora caricato» — mai `0` |

### 4.6 Dove vivono i token `[AIEngineer]`

Un modulo `tokens` (CSS variables o equivalente). Il Renderer legge solo quelli. Tema = quel file. Beautiful UI come dipendenza: **no** (evita lock-in e markup loro). Si reimplementano i primitive che mappiamo, copy-ready come *pattern*, non come npm se non serve.

---

## 5. Confine di fiducia (visibile)

Il design *è* il confine: approval card prima di ogni write; fonti visibili; overlay bozza ≠ pubblicato (albicocca vs foglia). Una UI «troppo fluida» che pubblica in un tap è fuori spec, anche se è carina.

---

## 6. Evals

| # | Caso | Gate |
|---|---|---|
| D1 | Screenshot landing Anna 29/06 | Fraunces sull'ora; fondo `carta`; zero `week-grid`; due card |
| D2 | Overlay bozza Debora | bordo albicocca + `diff-edit` a righe turno, non tabella 30 colonne |
| D3 | Approval `salva-preferenza` | card stile #04: testo + Conferma/Annulla; niente dialog nativo brutto come unica via |
| D4 | Job 8s | elapsed visibile, non uno spinner infinito |
| D5 | Contrasto `inchiostro` su `carta` | ≥ 4.5:1 |
| D6 | Font | zero Inter / Space Grotesk / system-ui come display |

---

## 7. Aperto / decisioni già prese

**Prese**

- Ispirazione Beautiful UI = grammatica AI-native, non la libreria intera.
- Tono fresco: carta `#F6F1E8`, foglia `#2A7A56`, Fraunces + Source Sans 3.
- Landing = due card, non chat-full-bleed.
- Dark mode fuori. Tabelle lunghe fuori dalla home.

**Aperti**

- Self-host font vs CDN (produzione: self-host, GDPR `05`).
- Punto colore reparto: palette da `kb/reparti.md` da fissare in implementazione (non i fill Excel).
- Rail Copilot: basso (mobile) vs destro (desktop) — `surface-map`.

---

## 8. Use case

### UC-17 Anna apre, è fresco
- **Chi:** Anna Mondora, telefono, lun 29/06 14:05
- **Quando:** primo paint
- **Fa:**
  1. Sfondo carta, niente sidebar nera.
  2. Il suo nome in Fraunces. «Adesso 14–20 · pizze» enorme.
  3. Sotto, i prossimi in una lista calma. 41h in basso, piccolo.
  4. Accanto/sotto: 96h ferie, 24h permessi, «file · 16 ago».
  5. Composer in basso, pill, come Beautiful UI #08 — non un rettangolo Slack.
- **Esito:** sa di essere in turno. Non ha aperto un gestionale.
- **AI può / non può:** non c'è ancora. Il bello è deterministico.

### UC-18 Manager conferma come approval card
- **Chi:** store manager
- **Quando:** bozza pronta, Compliance ok
- **Fa:**
  1. Card raccomandazione: «Propongo cambi su Debora e Cesare» + `rationale` + fonti.
  2. Sotto, i due `person-shifts` albicocca.
  3. Chip: Accetta / Un'altra variante / Rifiuta — come Beautiful UI #04, non tre button Bootstrap.
  4. Accetta → seconda card «Pubblico la settimana?» con chi è toccato (`05` chi non è nella stanza).
- **Esito:** due conferme, entrambe chiare. Zero tap ciechi.
- **AI può / non può:** può riempire rationale e confidence; il tap è umano.
