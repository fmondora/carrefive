# 04 — Runtime agents
**Owner:** dual · **Status:** ready

| Agent | user_facing | emits | owns_presentation | Source |
|---|---|---|---|---|
| copilot | sì | `copilot-turn` + widget già costruiti da `vista` | sì (scelta *quale* widget mostrare in consulta) | `agents/copilot.py` |
| forecast | no | `Proposta` previsione | no | mapping in ciclo |
| scheduling | no | `Proposta` bozza-turni; funzione `_candidati` | no | `agents/scheduling.py` |
| compliance | no | violazioni / `pubblicabile` | no | `agents/compliance.py` → `vista.compliance_block` |
| anomaly | no | segnali | no | fuori slice (niente consuntivo) |
| secondo-pv | no | memoria | no | dopo decisione umana; invariato |

## Orchestration
Macchina a stati in `orchestrator/ciclo.py`. Non è un modello a scegliere chi parla.

```
idle → … → attesa_umano
         ├─ tap gap → consulta (codice) → candidati in _FLUSSO → home
         ├─ sposta-turno (confermato) → piano.imposta → _compliance → attesa_umano
         ├─ accetta → (se pubblicabile) offre pubblica
         ├─ rifiuta → idle + secondo-pv
         └─ pubblica → monitora
```

LLM entra solo: (a) prosa del Copilot; (b) ordine morbido dei candidati *dentro* `genera-bozza` (già oggi, con fallback det). **Non** entra nel tap-gap.

## Loop C1 — il Copilot compone

`owns_presentation` diventa vero: una chiamata `compone` sceglie **tool + chip + testo**. Non classifica un intent per poi entrare in uno `if`.

```
enunciato + ultimi k turni
    → llm.genera_json(SCHEMA_COMPONI)     # 1 chiamata
    → tool (se c'è) = funzione det già in allowlist
    → vista mappa output → widget
    → append copilot-turn al filo
```

- Scheduling / compliance / forecast: invariati, `user_facing=false`.
- `consult(scheduling)` solo se il modello ha scelto quel tool **e** l’attore è manager. Mai default.
- Regex / `_intent_det` / `_è_preferenza`: **solo** degrado (LLM giù / non configurato / schema). Non il path felice.
- Chip write: il Copilot non le esegue. Dopo l’esecuzione (handler), un turno det di chiusura + chip next (C1.3) — zero seconda chiamata modello.

## P-L check
- Scheduling **non** emette widget. Espone `_candidati` (o un wrapper pubblico `candidati_per_gap`) come funzione di dominio. La vista mappa slug → `person-shifts`.
- Copilot **non** esegue `sposta-turno`. Può solo *proporre* la chip.
- Un vocabolario: i candidati sono `person-shifts`, non un tipo «del scheduling».

## Delta slice A
1. Pubblicare `candidati_per_gap` in `scheduling.py` (stesso mestiere, non un settimo agente):
   - layer 1 = `_candidati` (libero, mansione ok, non R/F/badge)
   - layer 2 = `_movibili`: stessa mansione, **quel** giorno già in turno ma **non** in quella fascia/reparto — solo se layer 1 è vuoto
   - mai R/F nella lista
   - ordine = `_ordine_deterministico` (ore/contratto), **non** `_ordina` LLM
   - tetto `MAX_TOCCATI` (8)
   - Layer 2 è una proposta di spostamento, non «disponibilità»: rationale det «già in turno, altra fascia — confermi».
   - Senza layer 2 il tap-gap sulla demo è empty su tutti i 15 buchi (il solver ha già preso i liberi).
2. `Risposta.spento` = solo `motivo == "giu"` da `LLMGiu` che non è `LLMNonConfigurato`. `SchemaNonRispettato` → `motivo="schema"`, composer acceso.
3. `consulta` con `data`+`fascia`+`reparto` è codice, non un turno Copilot. Copilot allowlist invariata: niente tool `sposta`.
