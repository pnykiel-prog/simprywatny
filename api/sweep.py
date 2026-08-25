"""Funkcja serverless: /api/sweep

Cienki adapter. Korzen repozytorium trafia na sys.path jawnie, zeby import
pakietu nie zalezal od tego, jak platforma ustawia katalog roboczy.
"""

import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN))

try:
    from sim_kalkulator.serverless import zbuduj_uchwyt

    handler = zbuduj_uchwyt("sweep")
except Exception as _wyjatek:  # noqa: BLE001 — straznik startu, lapie wszystko
    # Nazwa z `except ... as` znika po wyjsciu z bloku, wiec komunikat i slad
    # trzeba utrwalic tutaj — inaczej straznik sam wywala sie na NameError.
    _POWOD = "%s: %s" % (type(_wyjatek).__name__, _wyjatek)
    _SLAD = traceback.format_exc().splitlines()[-6:]

    class handler(BaseHTTPRequestHandler):  # noqa: N801 — nazwa wymagana przez platforme
        """Silnik nie zaladowal sie — odpowiadamy, czego brakuje, zamiast pustym 500."""

        def do_GET(self):  # noqa: N802
            self._powiedz_co_sie_stalo()

        def do_POST(self):  # noqa: N802
            self._powiedz_co_sie_stalo()

        def _powiedz_co_sie_stalo(self):
            try:
                zawartosc = sorted(p.name for p in KORZEN.iterdir())[:40]
            except OSError as exc:
                zawartosc = ["blad odczytu: %s" % exc]
            tresc = json.dumps({
                "ok": False,
                "typ": "start",
                "powod": _POWOD,
                "slad": _SLAD,
                "korzen": str(KORZEN),
                "korzen_zawartosc": zawartosc,
                "pakiet_silnika_obecny": (KORZEN / "sim_kalkulator").exists(),
                "interfejs_obecny": (KORZEN / "web" / "index.html").exists(),
                "przyklady_obecne": (KORZEN / "przyklady").exists(),
                "podpowiedz": (
                    "Funkcja wystartowala, ale nie zaladowala silnika. Najczestsza "
                    "przyczyna to pliki spoza katalogu api/ nieobjete includeFiles "
                    "w vercel.json."
                ),
            }, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(tresc)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(tresc)

        def log_message(self, format, *args):
            pass
