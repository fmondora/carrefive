"""CLI `tm` — i comandi deterministici (`04` §4.2, `05` §4.7, `07` §4.2).

Import saldi, invito, ruoli, scan di sicurezza, diritti GDPR, server.
Nessun comando qui dentro chiama un LLM: sono atti, e gli atti sono umani.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from .kb import persone as kb_persone
from .kb import turni as kb_turni
from .security.authz import Attore


def _attore_attivatore(slug: str) -> Attore:
    persona = kb_persone.leggi(slug)
    ruoli = tuple(persona.ruoli) if persona else ()
    return Attore(slug=slug, ruoli=ruoli or ("dipendente",))


def cmd_import_saldi(args) -> int:
    from .saldi.importer import importa

    report = importa(args.file, at=args.at)
    print(report.testo())
    return 0 if report.ok else 1


def cmd_invita(args) -> int:
    from .auth import attivazione

    attore = _attore_attivatore(args.da)
    if args.qr:
        esito = attivazione.mostra_qr(attore, args.persona, args.base_url, args.email)
        print(esito["link"])
        if esito["qr_svg"] and args.svg:
            with open(args.svg, "w", encoding="utf-8") as f:
                f.write(esito["qr_svg"])
            print(f"QR salvato in {args.svg}")
    else:
        esito = attivazione.invia_attivazione(attore, args.persona, args.email, args.base_url)
        print(esito["oggetto"])
        print(esito["corpo"])
    return 0


def cmd_ruolo(args) -> int:
    persona = kb_persone.leggi(args.persona)
    if persona is None:
        print(f"nessuna scheda per {args.persona}", file=sys.stderr)
        return 1
    ruoli = set(persona.ruoli) | set(args.aggiungi or [])
    ruoli -= set(args.togli or [])
    kb_persone.imposta_ruoli(args.persona, sorted(ruoli))
    print(f"{args.persona}: {', '.join(sorted(ruoli)) or 'dipendente'}")
    return 0


def cmd_scan(args) -> int:
    from .security import matchers

    trovati = matchers.scan()
    for f in trovati:
        print(f"{f.gravita} {f.matcher} {f.file}:{f.riga} — {f.perche}")
        print(f"    {f.estratto}")
    riepilogo = matchers.registra(trovati)
    print(json.dumps(riepilogo, ensure_ascii=False))
    if args.ci and matchers.blocca_merge(trovati):
        print("merge bloccato: finding HIGH+ aperti", file=sys.stderr)
        return 2
    return 0


def cmd_gdpr(args) -> int:
    from .security import diritti

    if args.azione == "export":
        p = diritti.scrivi_export(args.persona)
        print(p)
    else:
        print(json.dumps(diritti.cancella(args.persona), indent=2, ensure_ascii=False))
    return 0


def cmd_bozza(args) -> int:
    """Genera una bozza headless. Non pubblica: la pubblicazione è umana."""
    from .orchestrator import ciclo as orchestratore

    settimana = (
        dt.date.fromisoformat(args.settimana)
        if args.settimana
        else kb_turni.lunedi_di(dt.date.today() + dt.timedelta(days=7))
    )
    attore = _attore_attivatore(args.da)
    ciclo = orchestratore.ciclo(settimana)
    job = ciclo.genera_bozza(attore, varianti=args.varianti)
    print(json.dumps(job.come_dict(), ensure_ascii=False))
    if ciclo.bozza is None:
        print("nessuna bozza (agenti giù?)", file=sys.stderr)
        return 1
    print(ciclo.bozza.rationale)
    print(f"pubblicabile: {ciclo.bozza.pubblicabile}")
    for v in ciclo.bozza.violazioni:
        print(f"  blocco {v['persona']}: {v['dettaglio']}")
    for g in ciclo.bozza.gap:
        print(f"  gap {g['data']} {g['fascia']} {g['reparto']}: -{g['teste_mancanti']}")
    return 0


def cmd_purga_log(args) -> int:
    from .security import audit

    print(f"record di inferenza purgati: {audit.purga_inferenza()}")
    return 0


def cmd_serve(args) -> int:
    import uvicorn

    uvicorn.run("timemachine.web.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tm", description="TIME MACHINE — Le Rocce")
    sub = p.add_subparsers(dest="comando", required=True)

    s = sub.add_parser("import-saldi", help="importa il montante dallo studio (CSV)")
    s.add_argument("--file", required=True)
    s.add_argument("--at", default=None, help="data dello snapshot (YYYY-MM-DD)")
    s.set_defaults(func=cmd_import_saldi)

    s = sub.add_parser("invita", help="attiva una persona (email o QR)")
    s.add_argument("persona")
    s.add_argument("--da", required=True, help="slug dell'attivatore (Emilio)")
    s.add_argument("--email", default="")
    s.add_argument("--qr", action="store_true")
    s.add_argument("--svg", default="")
    s.add_argument("--base-url", default="https://localhost:8000")
    s.set_defaults(func=cmd_invita)

    s = sub.add_parser("ruolo", help="assegna ruoli (manager, attivatore)")
    s.add_argument("persona")
    s.add_argument("--aggiungi", nargs="*", default=[])
    s.add_argument("--togli", nargs="*", default=[])
    s.set_defaults(func=cmd_ruolo)

    s = sub.add_parser("scan", help="matcher di sicurezza sul repo (stile DeepSec)")
    s.add_argument("--ci", action="store_true", help="esce 2 se ci sono HIGH+ aperti")
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("gdpr", help="diritti dell'interessato")
    s.add_argument("azione", choices=["export", "cancella"])
    s.add_argument("persona")
    s.set_defaults(func=cmd_gdpr)

    s = sub.add_parser("bozza", help="genera una bozza di settimana (non pubblica)")
    s.add_argument("--settimana", default="")
    s.add_argument("--da", required=True, help="slug del manager")
    s.add_argument("--varianti", type=int, default=1)
    s.set_defaults(func=cmd_bozza)

    s = sub.add_parser("purga-log", help="retention 30 giorni sui log di inferenza")
    s.set_defaults(func=cmd_purga_log)

    s = sub.add_parser("serve", help="avvia il server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--reload", action="store_true")
    s.set_defaults(func=cmd_serve)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
