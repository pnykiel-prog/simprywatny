"""Funkcja serverless: /api/przelicz

Cienki adapter. Korzen repozytorium trafia na sys.path jawnie, zeby import
pakietu nie zalezal od tego, jak platforma ustawia katalog roboczy.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sim_kalkulator.serverless import zbuduj_uchwyt  # noqa: E402

handler = zbuduj_uchwyt("przelicz")
