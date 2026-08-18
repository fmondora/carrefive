"""TIME MACHINE — runtime del sistema agentico + GenUI per i turni di Le Rocce.

Invariante di tutto il pacchetto (`00` §1):
**l'AI propone, l'umano dispone, il calcolo è deterministico.**

Il confine è anche architetturale: `domain`, `kb`, `saldi`, `calendario`,
`auth` non importano `agents`. Il test `tests/test_confine.py` lo verifica.
"""

__version__ = "0.1.0"
