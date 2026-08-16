# Sicurezza — come verifichiamo

Operativo di `specs/05-security-gdpr.md` §4.7. DeepSec è il modello: inventario
delle superfici, matcher dichiarativi, storia **append-only**.

## Ora: `tm scan`

La parte gratis della pipeline gira già, senza agenti e senza rete.

```
tm scan          # elenca i finding e aggiorna la storia
tm scan --ci     # esce 2 se ci sono HIGH+ aperti → merge bloccato
```

Matcher in `timemachine/security/matchers.py`:

| Slug | Cerca | Perché |
|---|---|---|
| `kb-secret` | token / hash dentro `kb/` | C8 di `03` |
| `prompt-full-kb` | loader che concatena schede raw nel prompt | `01` §4.5 |
| `balances-list-all` | endpoint che elenca i residui del PV | S4 di `04` |
| `calendar-on-draft` | write su Calendar prima di `pubblica` | C7 di `03` |
| `llm-writes-published` | pubblicazione senza gate umano | `01` §5 |
| `anomaly-individual-score` | scoring individuale | art. 4 Statuto |
| `pii-in-log` | CF, token, residui nei log | minimizzazione `05` |

I finding vivono in `docs/security/findings/findings.json`: un re-scan non
cancella niente, marca `fixed` o `false-positive`.

## Poi: DeepSec vero

Quando il repo si onborda:

```
npx deepsec init --yes --through coverage
cd .deepsec && npx deepsec process --diff origin/main
```

I matcher di sopra diventano plugin/generated-matchers con review umana. La
regola resta: `revalidate` su HIGH+, e «fixed» lo dichiara una persona.

## Diritti dell'interessato

```
tm gdpr export anna-mondora     # accesso e portabilità: le sue md + i suoi record
tm gdpr cancella anna-mondora   # oblio: preferenze, saldi, token, eventi, log
```

I **turni pubblicati storici restano** con lo slug — obbligo organizzativo e
retributivo — senza preferenze né segreti. Nessun'altra persona viene toccata.

## Retention

```
tm purga-log     # inferenza oltre 30 giorni: via (G7)
```

Le decisioni umane restano più a lungo: sono la traccia richiesta dall'AI Act.

## Segreti

Solo come **nome** di variabile d'ambiente in configurazione: `ANTHROPIC_API_KEY`,
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GAMMA_TOKEN`, `TM_CHIAVE_STORE`.
I token OAuth stanno in `.stato/token-google.enc`, cifrati; `.stato/` è in
`.gitignore` e non è dentro `kb/`.
