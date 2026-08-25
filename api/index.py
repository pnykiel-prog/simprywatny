"""Funkcja serverless: strona glowna — serwuje jednoplikowy interfejs.

Interfejs zostaje w `web/index.html`, zgodnie ze struktura repozytorium
z rozdz. 2.3 specyfikacji. Ta funkcja tylko go podaje; cala arytmetyka dzieje
sie w pozostalych funkcjach, ktore wolaja silnik.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sim_kalkulator.serverless import zbuduj_uchwyt_strony  # noqa: E402

handler = zbuduj_uchwyt_strony()
