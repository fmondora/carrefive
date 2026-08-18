# Architettura del runtime

Mappa **spec → codice → test**. Le `specs/0N-*.md` restano source of truth: se
questa pagina e una spec divergono, ha ragione la spec e il codice è da
sistemare.

## Il principio, reso struttura

> l'AI propone, l'umano dispone, il calcolo è deterministico (`00` §1)

Non è solo un'intenzione: è una proprietà del grafo degli import, verificata da
`tests/test_confine.py`.

```
        ┌──────────────────────────────────────────────┐
        │  web/  (guscio, chip, approval card)          │
        └───────────────┬──────────────────────────────┘
                        │  vista.py  (dominio → catalogo chiuso `02`)
        ┌───────────────┴──────────────────────────────┐
        │  orchestrator/  ciclo · contesto · jobs       │  ← macchina a stati
        └───────┬───────────────────────┬──────────────┘
                │                       │
     ┌──────────┴─────────┐   ┌─────────┴───────────────────────────────┐
     │  agents/  (LLM)     │   │  ZERO AI                                │
     │  forecast           │   │  domain/ore · compliance · saldi/       │
     │  scheduling         │   │  calendario/ · auth/ · security/        │
     │  anomaly · copilot  │   │  kb/ (markdown = archivio dati personali)│
     │  secondo-pv         │   └─────────────────────────────────────────┘
     └─────────────────────┘
```

I moduli della colonna di destra **non importano** `agents/` né `agents/llm.py`.
Compliance sta fra gli agenti per contratto (emette `Proposta`), ma è codice
puro: `usa_llm = False`, `modello = "codice"`.

## Mappa per spec

| Spec | Codice | Test |
|---|---|---|
| `00` visione e principi | l'invariante è il confine di import | `tests/test_confine.py` |
| `01` sistema agentico | `agents/`, `orchestrator/ciclo.py`, `orchestrator/contesto.py`, `orchestrator/jobs.py`, `domain/proposta.py`, `domain/grounding.py`, `domain/bozza.py` | `tests/test_e_sistema_agentico.py` (E1–E8) |
| `02` GenUI | `domain/catalogo.py`, `vista.py`, `web/templates/widget.html`, `web/app.py` | `tests/test_u_genui.py` (U1–U9) |
| `03` calendario Google | `calendario/` (`client`, `store`, `sync`, `__init__`) | `tests/test_c_calendario.py` (C1–C9) |
| `04` ferie e permessi | `domain/saldi.py`, `saldi/` (porta + 2 adapter + importer), `kb/saldi.py` | `tests/test_s_saldi.py` (S1–S9) |
| `05` security e GDPR | `security/` (`authz`, `allowlist`, `privacy`, `audit`, `diritti`, `matchers`) | `tests/test_g_security.py` (G1–G8) |
| `06` design system | `web/static/tokens.css`, `web/static/app.css`, template | `tests/test_d_design.py` (D1–D6) |
| `07` landing e attivazione | `auth/` (`attivazione`, `password`, `sessioni`, `oidc`, `store`), `web/templates/landing.html`, `attiva.html` | `tests/test_l_landing.py` (L1–L10) |
| use case UC-01…UC-22 | — | `tests/test_use_case.py` |

## Il ciclo settimana

`orchestrator/ciclo.py` è una macchina a stati; il linguaggio naturale non entra
mai qui (lo traduce il Copilot, che emette un *comando*, non un'azione).

```
idle → carica_contesto → forecast → scheduling → compliance → attesa_umano
     ├─ sposta-turno → scheduling → compliance → attesa_umano
     ├─ rifiuta-bozza → idle + secondo-pv impara
     └─ accetta-bozza → pubblica (umano) → monitora → anomaly → secondo-pv → idle
```

Tre invarianti codificate:

1. `compliance` gira prima di `attesa_umano` **e** di nuovo prima di `pubblica`.
2. `pubblica` è l'unico punto che chiama `kb_turni.scrivi` (test dedicato).
3. Con gli agenti giù non nasce una bozza: `person-shifts` resta sull'ultimo
   pubblicato e il job fallisce **visibilmente**.

## Dove vivono i dati

| Cosa | Dove | Perché |
|---|---|---|
| Persone, turni, saldi, memoria | `kb/**.md` | leggibile da un umano; è il pilota |
| Token Google, account, password | `.stato/*.enc` (Fernet) | mai in `kb/`, mai in git (`05` §4.5) |
| Log inferenza / decisioni / accessi | `.stato/audit/*.jsonl` | retention 30 gg sull'inferenza |
| Finding di sicurezza | `docs/security/findings/` | append-only, come DeepSec |

`TM_KB`, `TM_STATO`, `TM_FINDINGS` spostano le tre radici (i test ci puntano un
tmp: la knowledge del pilota non è un banco di prova).

## Configurazione

| Variabile | Valori | Effetto |
|---|---|---|
| `TM_LLM` | vuoto = automatico · `fake` · `cli` · `api` | backend degli agenti (`01` §3). Automatico: chiave → CLI `claude -p` → nessun modello |
| `TM_LLM_CLI` | es. `"claude -p --model haiku"` | comando del backend `cli` |
| `TM_MODELLO` / `TM_EFFORT` | `claude-opus-5` / `low` | modello e effort del backend `api` |
| `SALDI_FONTE` | `file` (default) · `gamma` | adapter dei residui (`04` §4.3) |
| `TM_GOOGLE` | — · `http` | client Calendar finto o reale |
| `TM_OIDC` | — · `google` | identità finta o reale |
| `TM_OGGI` | `YYYY-MM-DD` | sposta «oggi» (demo sul pilota 29/06/2026) |
| `TM_CHIAVE_STORE` | chiave Fernet o passphrase | cifratura dello store segreti |
| `ANTHROPIC_API_KEY`, `GOOGLE_CLIENT_ID/SECRET`, `GAMMA_TOKEN` | — | **solo** come nome di env, mai in config |

Le credenziali Anthropic non le legge il nostro codice: il client dell'SDK a
zero argomenti risolve da sé env, profilo OAuth e federazione. Un test lo
verifica — leggere la chiave a mano romperebbe il caso «autenticato con
`ant auth login`, nessuna chiave in env».

## Cosa manca (e lo sa)

- Motore CCNL Commercio/DMO completo: `agents/compliance.py` implementa i check
  che sappiamo (riposo settimanale, tetto 48h, riposo giornaliero con deroga
  art. 7 sul frazionato, giorni consecutivi, minori, mansione in scheda). Spec
  propria prima del go-live sul pubblicabile (`01` §7).
- Timbrature e consuntivo: `agents/anomaly.py` ha il contratto, manca la
  sorgente. Export paghe: fuori edizione.
- Contratto HTTP Gamma: `saldi/adapter_gamma.py` isola il punto da chiudere con
  lo studio (`04` §7).
- Provider mail per l'invito: `auth/attivazione.py` produce oggetto e corpo, non
  li spedisce (`07` §7).
- Font self-hosted: i token dichiarano Fraunces / Source Sans 3 con fallback
  serif locali; per produzione vanno serviti da noi (`06` §7, GDPR `05`).
