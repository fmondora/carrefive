# 07 — Reliability & evals
**Owner:** AIEngineer · **Status:** ready

## Failure modes → honest UX
| Failure | User sees |
|---|---|
| Gap senza candidati (tutti in turno/R/F o senza mansione) | rationale det: «nessuno libero; un riposo si tocca solo a mano». Composer acceso. |
| `sposta-turno` senza campi (chip nuda o form rotto) | 400 + testo det, home. Mai 500. |
| `parse_cella` fallisce | 400, fascia non accettata. Piano intatto. |
| Sposta che rompe CCNL | piano si aggiorna, `compliance-block` visibile, `pubblica` assente. Non rollback silenzioso (come oggi: il manager ha deciso). |
| Annulla | home, nessuna write, conferma sparita. |
| `SchemaNonRispettato` sulla prosa | fatti deterministici, `motivo=schema`, composer **acceso**. |
| `LLMNonConfigurato` | `motivo=non-configurato`, composer acceso (già). |
| `LLMGiu` (backend c’era, non risponde) | `motivo=giu`, composer spento, `person-shifts` pubblicato resta (U7). |
| Tabellone senza piano per la settimana ciclo | card «nessuna settimana» — non ricadere sul 29/06 pubblicato se il ciclo è 06/07. |
| Dipendente tappa un gap | non vede i gap (solo manager). API 403. |
| Restart processo | `_FLUSSO` perso; ciclo/bozza restano. Manager rigenera i candidati con un tap. |

## Canaries / evals
Esistenti da **non rompere**: U1–U9, U8-bis, E4, E6, E8, L1, L10.

Nuovi (questa slice):

| Name | Asserts |
|---|---|
| U-sposta-400 | POST `/chip/sposta-turno` senza campi → ≠ 500; home o 400 |
| U-sposta-conferma | senza `conferma=1` non chiama `ciclo.sposta_turno`; piano invariato |
| U-sposta-ok | manager + campi + conferma=1 → turno sul piano, stato `attesa_umano`, compliance ricalcolata |
| U-gap-candidati | tap `consulta` su un `bozza.gap` → stack di `person-shifts` (layer 1∪2) **oppure** testo onesto; nessuno in R/F; 0 chiamate LLM |
| U-gap-vuoto | gap senza liberi → testo onesto, zero `person-shifts` extra di colleghi a caso |
| U-settimana-ciclo | `GET /tabellone` in `attesa_umano` contiene la data della settimana *ciclo*, non solo `_settimana_corrente` |
| U-annulla | `conferma=0` su accetta → 303 `/home`; seconda GET senza domanda «Accetto questa bozza?» |
| U-composer-det | preferenza con LLM che alza `SchemaNonRispettato` → HTML ha input copilota **non** disabled |
| U-me-senza-overlay-altra-settimana | home Francesco: `person-shifts(me)` senza badge bozza se `bozza.settimana != lunedi_di(oggi)` |
| U4 resta | dopo genera-bozza con Matteo 52h, `pubblica` assente |

## Loop C1 — failure + evals

| Failure | User sees |
|---|---|
| Modello giù | ultimo filo resta; nuovo turno det da `_intent_det`; `motivo=giu` o `non-configurato`; composer acceso salvo `giu` vero |
| Schema compose | fatti + tool nessuno + chip utili det; `motivo=schema` |
| Tool nego / 403 | turno onesto (già `RIFIUTO_ALTRUI` / `COPRI_NON_MIO`), nel filo |
| Tipo / chip fuori enum | drop silenzioso + resto del turno |
| Cap 8 | cadono i più vecchi; i due card guscio restano |
| Restart | filo vuoto; turni pubblicati restano (U7) |

Nuovi (non rompere U1, U5, U-p-ciao, U-p-cella, U-p-data, U-composer-det):

| Name | Asserts |
|---|---|
| U-c-filo | due POST NL di seguito → ≥2 `copilot-turn` nel composer; il primo testo c’è ancora |
| U-c-dentro | «suono il piano il giovedì» → `scheda-preview` è **dentro** `copilot-turn`, non XOR |
| U-c-next | ultimo turno ha 1–3 chip ⊆ CHIP; dopo `salva-preferenza` un turno di chiusura + ≥1 chip |
| U-c-compose | con llm scriptato `{testo, tool:prepara_preferenza, chip:[salva-preferenza]}` **non** passa da `_è_preferenza` |
| U-c-degrado | fake senza copione → euristica, composer acceso, niente Scheduling per Anna |
| U1 resta | GET /home a freddo: 0 `copilot-turn` |

## Observability minimum
- audit già su accetta / rifiuta / pubblica / preferenza / sposta (`ciclo.sposta_turno` già logga). Tenere.
- Non loggare token QR / password.
- Un evento log «gap_consultato» (data, fascia, n_candidati) basta per la metrica «sessioni che aprono week-grid vs tap-gap».
