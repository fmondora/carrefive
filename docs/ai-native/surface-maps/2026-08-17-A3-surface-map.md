# Surface map — TIME MACHINE / Le Rocce — 2026-08-17 — **A3**

## Meta
- Loop id: **A3**
- Precedente: A2 map `2026-08-16-A2-surface-map.md` · impl `849f86a`
- Live: `http://127.0.0.1:8772/` (`TM_OGGI=2026-06-29T14:05`)
- Test: 88 verdi (`test_u_genui` + e + confine)
- Sources: Book A2, specs Loop A2, `widget.html` gap/blocco, `app.py` `_celle_del_blocco`/`_scarta_esiti`, `compliance.celle_che_sciolgono`, live Francesco

## Roles
| Role | Surfaces | Note A3 |
|---|---|---|
| Anna | 2 card + composer | Intatta. Non ritestata a screenshot; U1 verde. |
| Francesco | briefing + blocco-gesto + gap-gesto + approval + `Pubblica` | **Settimana pubblicabile.** 15 buchi restano visibili come muro. |

## Surfaces
Invariate. Delta: esito del tap **dentro** il `<li>` (gap e blocco). `mostra_adesso=false` sulle card bozza. Preview `prima → dopo` sulla cella.

## Runtime agents
P-L tiene. `celle_che_sciolgono` è codice Compliance, non un agente nuovo. Tap = 0 LLM (canary).

## Catalog diff
| Type | Status | Note live A2 |
|---|---|---|
| compliance-block | none | «Come lo sciolgo» solo su violazioni. 8 mosse Matteo, esito interno. |
| coverage-gap | none | candidati sotto la riga. 15 chip identiche restano un muro. |
| person-shifts | none | «Settimana in bozza», no Adesso. Mosse sulla riga. |
| scegli-variante | none | assente con n=1. Live ok. |
| approval | shell | «Matteo lunedì 06/07: 6-14 → R. Sostituisco la cella?» |

## Trust boundary
- Dual gate vivo: dopo 6-14→R, blocco tetto sparisce; `Pubblica` solo dopo Accetta. Live verificato.
- Segnalazioni (41h) senza bottone.
- `sposta` riazzera `accettata`.

## Gaps that matter
### P0
Nessuno sul *veto*. Sul *job negozio* (chiudere senza 15 tap e senza pubblicare alla cieca):

1. **Residuo invisibile sul close.** Approval accetta/pubblica non dice «restano 15 buchi, non bloccano». Francesco o tap-tap o pubblica cieco.

### P1
2. **Dopo lo sposta, `_scarta_esiti`** ributta sul muro di 15. P-F della *settimana* rotto.
3. **Layer 2 apre un altro buco** e la preview del *candidato gap* non sempre nomina quale (il blocco sì).
4. Composer `fixed` ancora copre il corpo della card Matteo.

### P2
Path kb, font 06, date, 8770 senza demo.

## Keystone
**Residuo, non muro.** Stessi tipi. La card gap diventa conteggio + 1 riga primaria; approval elenca N buchi restanti; dopo un tap il *prossimo* buco si apre da solo. Non si tocca il solver. Non si vieta pubblica se ci sono buchi.

## Do NOT touch
Anna. Dual gate come veto. Catalogo. Layer 2. Tabellone ciclo. Chat-casa.

## Proposals
### A — Residuo, non muro (recommended)
`coverage-gap` compresso (N + prossimo); approval dice i residui; dopo conferma, stesso `consulta` sul prossimo buco copribile. `free-det`.

### B — Template sotto tetto
Scheduling non copia settimane già illegali. Chiude la *nascita* del 52h. `free-det` nel solver. Più rischio, altro mestiere.

### C — Hygiene
Giorno sulle chip `6-14→R` duplicate; z-index composer; allineare Book 05–07 al codice A2.

**Raccomando A** (+ C nello stesso PR). B è A4 se dopo A il manager pubblica ancora poco.
