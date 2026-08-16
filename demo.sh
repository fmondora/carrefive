#!/usr/bin/env bash
# Demo del pilota su una copia usa-e-getta della knowledge.
#
# La `kb/` del repo è un archivio di dati personali (`05` §3): la demo non ci
# scrive dentro. Copia tutto in una directory temporanea, attiva due account e
# avvia il server con l'orologio fermo al lunedì 29/06/2026, che è la settimana
# pubblicata in `kb/turni/`.
#
#   ./demo.sh            avvia su http://127.0.0.1:8770
#   ./demo.sh 9000       avvia su un'altra porta
set -euo pipefail

PORTA="${1:-8770}"
RADICE="$(cd "$(dirname "$0")" && pwd)"
DEMO="${TM_DEMO_DIR:-${TMPDIR:-/tmp}/timemachine-demo}"
PY="${PYTHON:-python3.12}"

rm -rf "$DEMO"
mkdir -p "$DEMO"
cp -R "$RADICE/kb" "$DEMO/kb"

export TM_KB="$DEMO/kb"
export TM_STATO="$DEMO/stato"
export TM_OGGI="2026-06-29T14:05"
export TM_COOKIE_INSICURO=1   # solo qui: su http i client non-browser non
                              # manderebbero un cookie Secure (`07` §4.4)
export PYTHONPATH="$RADICE"

"$PY" - <<'PYTHON'
"""Emilio attiva sé stesso e Anna, così la demo ha due punti di vista."""
from timemachine.auth import attivazione, store
from timemachine.kb import persone as kb_persone
from timemachine.security.authz import Attore

kb_persone.imposta_ruoli("francesco", ["manager", "attivatore"])
emilio = Attore("francesco", ("dipendente", "manager", "attivatore"))

for slug, email in (("anna-mondora", "anna@lerocce.it"), ("francesco", "francesco@lerocce.it")):
    esito = attivazione.invia_attivazione(emilio, slug, email, "http://127.0.0.1")
    attivazione.crea_account_password(esito["link"].split("t=")[1], email, "settelune2026")
    print(f"  {email:26} settelune2026   ({store.account(slug).stato})")
PYTHON

echo
echo "TIME MACHINE — Le Rocce · http://127.0.0.1:$PORTA"
echo "  oggi = lunedì 29/06/2026, 14:05 (la settimana pubblicata in kb/turni/)"
echo "  knowledge usa-e-getta in $DEMO"
echo "  ctrl-c per fermare"
echo

exec "$PY" -m uvicorn timemachine.web.app:app --host 127.0.0.1 --port "$PORTA"
