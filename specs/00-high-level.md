# TIME MACHINE — Sistema agentico AI per la gestione orari nella GDO

**Documento di visione — v0.2 · 16 agosto 2026**
Target di riferimento: supermercati e punti vendita GDO (Italia). Pilota: Le Rocce, Poggiridenti.
Analisi di mercato: Italia + player globali AI-first.

Le spec di costruzione partono da qui e vivono in `specs/01-sistema-agentico.md` e `specs/02-genui.md`.

---

## 1. Visione

Un sistema agentico AI che parte come assistente alla pianificazione turni e diventa progressivamente il gestionale orari del punto vendita: prevede la domanda, propone i turni, verifica la conformità (CCNL, riposi, straordinari), dialoga con responsabili e dipendenti in linguaggio naturale — mantenendo sempre l'umano come decisore finale.

Il principio architetturale non negoziabile: **l'AI propone, l'umano dispone, il calcolo è deterministico.** Tutto ciò che tocca la busta paga (conteggio ore, maggiorazioni, festività) è codice testato e verificabile; l'AI opera a monte (previsione, proposta, segnalazione) e a lato (interfaccia conversazionale).

---

## 2. Principi fondanti

Questi quattro principi sono il *perché* del sistema. Le spec di costruzione non possono violarli. Il quarto è il loop che tiene insieme i primi tre.

1. **Il sistema impara da noi.** È intelligente nella misura in cui impara dai comportamenti — del manager e del team. Il loop non ha un centro unico: cammina anche senza chi l'ha allenato per primo. Per ora niente *secondo personale*; c'è il **secondo del punto vendita** (memoria collettiva) e le **schede persona** (fatti, mansioni, preferenze). Tutto il resto discende da qui.
2. **Abbondanza e possibilità.** Si pensa in grande perché ora tutto è possibile. Serve una superficie? Si genera. Serve uno specialista? Si genera — e la generazione torna al #1: impara da noi.
3. **Tutto è più semplice.** C'è il tempo per semplificare e la possibilità di rigenerare fino alla perfezione. La semplicità non è un vincolo, è il default.
4. **Tutto è reiterativo.** I primi tre sono un loop. Il quarto è il loop stesso: la stessa forma si ripete a ogni scala (Mandelbrot). Una scheda, una settimana, un punto vendita, un'insegna: stesso contratto.

---

## 3. Principi sull'uso dell'AI

La sorgente: la rete è un corpo. Le relazioni fanno evolvere il tutto come uno. Non c'è un livello personale e uno sistemico — sono la stessa vista.

1. **Quiete durante l'azione** — la contemplazione non precede la decisione, la accompagna.
2. **Oscillazione, non amplificazione** — dopo una decisione giusta si ricalibra, non si accelera.
3. **Chi non è nella stanza** — ogni decisione ha un portatore di conseguenze assente. Cercalo prima (il dipendente, il consulente paghe, il cliente in corsia).
4. **Riconoscimento, non costruzione** — le decisioni si rivelano. Il corpo del negozio lo sa prima della mente.
5. **Frame nuovi, non soluzioni** — se la soluzione è dentro il frame vecchio, è il frame che va cambiato.
6. **Visione d'insieme prima del dettaglio** — il dettaglio ha senso solo nel quadro grande.
7. **Abbondanza, non scarsità** — la scarsità genera competizione, l'abbondanza collaborazione.
8. **Il rumore è il nemico** — delega il rumore, tieni la chiarezza.
9. **Più sorgenti che canali** — manda avanti le cose aperte, non aprirne di nuove.
10. **Compassione come intelligenza** — la gentilezza è la risposta più intelligente all'interdipendenza.
11. **Addizionalità prima di sostituire** — non rimpiazzare ciò che esiste, aggiungi ciò che manca. Il tabellone resta la *knowledge* (`kb/turni/`); l'interfaccia non lo ripete. Si aggiunge il widget della persona.
12. **Il terzo spazio** — nel conflitto non si sceglie un lato, se ne crea uno che li contiene.

### Come si costruisce (lenti, non runtime)

L'interfaccia la progetta **AIUxer**. L'architettura, il costo e le evals le progetta **AIEngineer**. Plugin `ai-native` (repo `fmondora/AI-Engineering`). Nelle spec: `[AIUxer]` e `[AIEngineer]` marcano la lente. L'arbitro è l'esito misurato; su turni pubblicati e dati retributivi il confine di fiducia ha veto.

---

## 4. Contesto di mercato

### 4.1 Dimensione e trend

- Mercato europeo del workforce management software: **~2,89 mld $ nel 2026 → 4,34 mld $ previsti al 2031 (CAGR 8,48%)**. Cloud al ~63% del mercato; il segmento PMI cresce più veloce (~10,6% CAGR); "workforce planning & analytics" è la funzione a crescita più rapida (~13,4% CAGR). (Mordor Intelligence)
- Driver principali: migrazione cloud del mid-market, **forecasting e scheduling AI**, automazione della compliance sulla Working Time Directive (la sentenza CGUE 2019 sull'obbligo di rilevazione oggettiva dell'orario ha reso il time tracking un obbligo normativo, non una comodità).
- Vincolo/opportunità: **l'AI Act classifica i sistemi AI per la gestione dei lavoratori come alto rischio**, con obblighi pieni in vigore da agosto 2026 — cioè ora. Chi nasce conforme ha una barriera a favore; chi improvvisa dovrà rifare.

### 4.2 Player globali AI-first (chi detta la tendenza)

| Player | Focus | Cosa fanno con l'AI | Note per noi |
|---|---|---|---|
| **Legion** (USA) | Retail/frontline enterprise | Release 2026: 90+ innovazioni; assistenti AI "agentici" che interrogano previsioni, turni, regole e dati come un analista; ottimizzazione turni in tempo reale su vendite e domanda; claim clienti: +33% retention, +11% eNPS, +66% puntualità | Il benchmark tecnologico. Enterprise-only, non presidia la PMI italiana |
| **Quinyx** (SE) | Retail/GDO Europa | "Hyperlocal forecasting" per punto vendita: POS, footfall, meteo, eventi locali, driver di domanda per reparto (cassa vs panetteria); turni generati "in 15 minuti"; gestione pause e task | Il concorrente europeo più vicino al nostro caso d'uso supermercato. Citato nel Gartner Market Guide retail WFM 2026 |
| **Orquest** (ES) | Retail/ristorazione | "Smart Planning" AI; caso di riferimento: scheduling per 2.000+ ristoranti McDonald's a livello globale | Dimostra che un player iberico di nicchia può vincere contratti globali con un prodotto verticale |
| UKG / ADP / Oracle / Infor | Enterprise generalista | Suite complete HR+WFM con AI incrementale | Dominano l'enterprise, lenti sul mid-market locale |

### 4.3 Player italiani (chi incontriamo in vendita)

| Player | Focus | Posizionamento |
|---|---|---|
| **Zucchetti** | GDO e retail, dalla PMI all'enterprise | Il riferimento in Italia: presenze, turni (Cost Planning/Infinity), payroll integrato; forte nella GDO. AI presente ma non centrale né agentica |
| **TeamSystem** | PMI generalista | Suite gestionale ampia, HR incluso; meno verticale sui turni GDO |
| **Factorial / Sesame HR** | PMI, HR all-in-one | Turni come modulo di una suite HR; AI generativa in arrivo ma orizzontale, non specializzata sul forecasting di punto vendita |
| **Fluida** | PMI, presenze mobile-first | Ottima UX presenze, non fa scheduling predittivo |

### 4.4 Il gap che possiamo occupare

Nessuno oggi offre insieme: (a) **AI agentica di livello Legion/Quinyx**, (b) **profondità normativa italiana** (CCNL Commercio/DMO, art. 4 Statuto, integrazione con consulenti del lavoro e payroll italiani), (c) **prezzo e semplicità da PMI** — il supermercato indipendente o la piccola insegna da 1–15 punti vendita, troppo piccola per Legion/Quinyx, troppo complessa per Fluida. Zucchetti presidia la fascia ma con tecnologia pre-agentica: la finestra è la velocità di esecuzione, non l'assenza di concorrenti.

---

## 5. Specifiche (indice)

Costruzione: `01-sistema-agentico` (contratto runtime) · `02-genui` (superfici e catalogo). Questa sezione resta la mappa prodotto.

### 5.1 Utenti e personas

1. **Store manager / capo reparto** — crea e aggiusta i turni ogni settimana; oggi lo fa su Excel o su un gestionale rigido. Utente primario.
2. **Titolare / direzione (multi-store)** — guarda costo del lavoro vs vendite, copertura, straordinari. Compratore.
3. **Dipendente turnista** — consulta turni, chiede cambi e ferie, timbra. Utente più numeroso: la sua adozione fa vivere o morire il prodotto.
4. **Consulente del lavoro / ufficio paghe** — riceve i dati consuntivi; l'export pulito verso i suoi sistemi è un requisito di vendita, non un extra.

### 5.2 Architettura agentica

Contratto completo in `01-sistema-agentico.md`. Qui resta il quadro.

Un orchestratore **deterministico** coordina agenti specializzati; ogni agente produce **proposte tracciate e motivate**, mai azioni definitive su dati retributivi. Consulta individuale e ciclo orchestrato usano lo stesso schema.

| Agente | Compito | Autonomia |
|---|---|---|
| **Forecast Agent** | Prevede fabbisogno per reparto/fascia oraria da storico vendite, scontrini, meteo, festività, eventi locali (modello per punto vendita) | Autonomo: produce previsioni, sempre ispezionabili |
| **Scheduling Agent** | Genera bozza turni ottimizzando copertura, costo, equità, preferenze; rispetta vincoli hard (riposi, ore max, CCNL) via constraint solver deterministico | Propone; il manager approva/modifica. Ogni proposta spiega il perché |
| **Compliance Agent** | Verifica continua su turni proposti e consuntivi: riposi violati, straordinari fuori soglia, minori, contratti in scadenza | Segnala e blocca la proposta non conforme; non modifica da solo |
| **Anomaly Agent** | Rileva anomalie contestuali su timbrature e presenze (pattern individuali, non regole fisse) | Solo segnalazione al manager |
| **Copilot conversazionale** | Interfaccia NL per manager ("chi può coprire sabato senza straordinario?") e dipendenti ("posso scambiare il turno con Anna?") | Esegue azioni solo previa conferma esplicita dell'utente. Unico agente che parla con l'umano |
| **Secondo del punto vendita** | Memoria collettiva: impara dalle decisioni umane (accettata / modificata / rifiutata) | Consultabile; non decide i turni. Niente secondo personale in questo taglio |

Confine deterministico: motore di calcolo ore/maggiorazioni, registro timbrature, export paghe = **zero AI**, codice testato con suite di regressione su casi CCNL.

### 5.3 Requisiti funzionali (MoSCoW, per l'MVP)

**Must**: anagrafica dipendenti e contratti (part-time, full-time, chiamata); definizione vincoli CCNL e aziendali; generazione bozza turni AI con approvazione manuale; pubblicazione turni e notifica ai dipendenti; timbratura (app mobile + eventuale badge esistente); consuntivo ore ed export verso paghe/consulente; audit log completo di ogni proposta e decisione AI (requisito AI Act).

**Should**: forecast domanda da dati vendite; richieste ferie/permessi/cambi turno in-app con workflow di approvazione; dashboard costo lavoro vs venduto per la direzione.

**Could**: copilot conversazionale; marketplace interno cambi turno tra colleghi; multi-store con condivisione personale tra punti vendita.

**Won't (per ora)**: payroll interno (si esporta, non si calcola la busta paga); rilevazione biometrica; qualsiasi funzione di scoring o valutazione della produttività individuale (rischio art. 4 e AI Act inaccettabile in questa fase).

### 5.4 Requisiti non funzionali

- **Conformità by design**: AI Act alto rischio → supervisione umana obbligatoria, documentazione tecnica, log delle decisioni, valutazione di conformità prima del rilascio. GDPR → data residency UE, minimizzazione, pseudonimizzazione dei dati verso i modelli, retention log inferenza ≤ 30 gg, nessun training sui dati dei clienti. Art. 4 Statuto → funzioni di analisi individuale disattivabili modularmente + kit documentale per accordo sindacale / istanza Ispettorato fornito al cliente.
- **Affidabilità**: il punto vendita non si ferma se l'AI è giù — pianificazione manuale e timbratura funzionano sempre (AI = enhancement, non dipendenza). Uptime target 99,9% sulle funzioni core.
- **Costi AI sostenibili**: operazioni frequenti su modelli piccoli/regole; LLM grandi solo su copilot e spiegazioni. Target: costo inferenza < 10% del prezzo per utente.
- **Integrazione**: API aperte; export tracciati paghe standard italiani; import da POS per il forecasting.

---

## 6. KPI

### 6.1 KPI di valore per il cliente (quelli che vendono)

| KPI | Baseline tipica | Target 12 mesi dal deploy |
|---|---|---|
| Tempo del manager per creare il piano turni settimanale | 3–6 h | **< 30 min** |
| Errori ore in consuntivo che arrivano alle paghe | da misurare per cliente | **−80%** |
| Incidenza straordinari non pianificati | da misurare | **−30%** |
| Copertura nelle fasce di picco (ore pianificate vs fabbisogno) | da misurare | **> 95%** |
| Violazioni CCNL/riposi rilevate a consuntivo | qualunque | **0** (bloccate a monte) |

### 6.2 KPI di prodotto e AI

- **Accuratezza forecast** (MAPE su fabbisogno per fascia oraria): < 15% dopo 8 settimane di dati per punto vendita.
- **Tasso di accettazione delle proposte turno AI**: > 70% senza modifiche sostanziali (è il KPI che dice se l'AI serve davvero).
- **Adozione dipendenti**: > 80% attivi sull'app ogni settimana; NPS dipendenti in crescita (Legion mostra che è possibile: engagement app all'88% settimanale).
- **Precisione anomaly detection**: > 60% delle segnalazioni giudicate utili dal manager (misurata in-app), falsi allarmi in calo mese su mese.

### 6.3 KPI di business (per il capo)

- **MRR** e nuovi punti vendita attivi/mese; **churn logo < 5% annuo**; **CAC payback < 12 mesi**; margine lordo > 75% (inferenza inclusa); pipeline: trial→pagante > 40%.

---

## 7. Obiettivi (OKR)

**O1 — entro 6 mesi: validare il valore su clienti reali.**
KR1: 3–5 supermercati pilota attivi con dati veri (anche gratis, con lettera d'intenti sul prezzo). KR2: tempo di pianificazione del manager ridotto di ≥ 70% nei pilota. KR3: parere legale su art. 4 + assessment AI Act completati e integrati nelle specifiche. KR4: accettazione proposte AI ≥ 60% nell'ultimo mese di pilota.

**O2 — entro 12 mesi: primo prodotto vendibile e conforme.**
KR1: 10+ punti vendita paganti, MRR ≥ [X]€. KR2: documentazione AI Act completa (sistema di gestione del rischio, log, DPIA). KR3: export paghe validato con almeno 2 studi di consulenza del lavoro. KR4: churn = 0 sui pilota convertiti.

**O3 — entro 18 mesi: ripetibilità.**
KR1: 40+ punti vendita, almeno 2 insegne multi-store. KR2: onboarding di un nuovo punto vendita < 2 settimane senza intervento sviluppatori. KR3: costo inferenza per utente stabile o in calo con la crescita.

*Metrica unica di verità per il capo (punto 13 del nostro Q&A): [MRR a €X / N punti vendita paganti] a 12 mesi — da fissare insieme.*

---

## 8. Rischi principali e mitigazioni

1. **Normativo (art. 4 / AI Act)** — il rischio esistenziale. Mitigazione: parere legale nel primo trimestre, architettura human-in-the-loop già in bozza, funzioni sensibili modulari e disattivabili, il "won't" sulla valutazione individuale.
2. **Zucchetti o Factorial aggiungono AI agentica** — probabile sul generalista. Mitigazione: verticalità supermercato (forecast per reparto, CCNL DMO/Commercio), velocità, servizio compliance impacchettato.
3. **Dati insufficienti per il forecast** nei piccoli punti vendita. Mitigazione: modelli con prior di categoria + fallback su template; il valore iniziale sta nella generazione turni vincolata, non solo nel forecast.
4. **Adozione dipendenti scarsa** → il dato consuntivo muore. Mitigazione: l'app del dipendente deve dare valore a lui (cambi turno, ferie, trasparenza), non solo controllarlo.
5. **Costo inferenza** fuori controllo. Mitigazione: budget per utente monitorato come KPI dal giorno 1.

---

## 9. Fonti

- Mercato EU WFM: [Mordor Intelligence — Europe Workforce Management Software Market](https://www.mordorintelligence.it/industry-reports/europe-workforce-management-software-market-industry)
- Legion: [Press release Spring 2026 — 90+ AI innovations](https://legion.co/company/press-releases/2026/01/12/legion-ai-workforce-management-innovations/) · [Businesswire](https://www.businesswire.com/news/home/20260112371338/en/Legion-Elevates-Hourly-Workforce-Management-with-90-New-Product-Features-That-Maximize-Employee-Value)
- Quinyx: [AI scheduling per supermercati](https://www.quinyx.com/blog/how-ai-driven-employee-scheduling-improves-supermarket-operations) · [Demand forecasting](https://www.quinyx.com/ai-optimization/demand-forecasting) · [Gartner Market Guide Retail WFM 2026](https://www.quinyx.com/blog/what-the-2026-gartner-market-guide-for-retail-workforce-management-technology-reveals-about-ai-scheduling-and-the-future-of-the-store)
- Orquest: [Caso McDonald's — 2.000 ristoranti](https://orquest.com/how-mcdonalds-transformed-scheduling/) · [Sito](https://orquest.com/)
- Italia: [Zucchetti Retail/GDO](https://www.zucchetti.it/it/cms/settori/retail-gdo) · [Zucchetti gestione turni](https://www.zcscloud.it/cost-planning-zucchetti-infinity/gestione-turni) · [Factorial — software gestione turni 2026](https://factorial.it/blog/i-migliori-software-per-la-gestione-dei-turni/) · [Sesame HR — AI per i turni](https://www.sesamehr.it/blog/gestione-dei-turni/intelligenza-artificiale-turni-lavoro/)

*Documento in bozza: i valori tra [parentesi] e le baseline "da misurare" vanno riempiti con i dati reali dei pilota.*
