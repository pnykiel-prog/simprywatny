"""Funkcja serwisowa: /api/diag — co naprawde wyladowalo w paczce funkcji.

Istnieje po to, zeby diagnoza wdrozenia nie opierala sie na zgadywaniu.
Zwraca wersje Pythona, katalog roboczy, sciezke importow oraz stan trzech
rzeczy, ktorych funkcje potrzebuja spoza katalogu `api/`: pakietu silnika,
pliku interfejsu i pliku parametrow. Nie ujawnia zmiennych srodowiskowych
ani zawartosci plikow.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sim_kalkulator.serverless import zbuduj_uchwyt_diagnostyczny  # noqa: E402

handler = zbuduj_uchwyt_diagnostyczny()
