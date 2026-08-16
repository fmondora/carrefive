# Esempi

`export-studio-esempio.csv` — la forma dell'export dello studio per
`tm import-saldi` (`04` §4.2). **Numeri fittizi**: servono a far girare il
comando, non sono i residui veri di nessuno.

```bash
tm import-saldi --file docs/esempi/export-studio-esempio.csv --at 2026-08-16
```

Il mapping delle colonne è dichiarato in `timemachine/saldi/importer.py`
(`MAPPING_DEFAULT`), non indovinato da un modello. Una riga che non matcha una
scheda in `kb/persone/` finisce nel report: non fa fallire la run e non crea un
file spazzatura.
