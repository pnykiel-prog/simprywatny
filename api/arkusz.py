"""Funkcja serverless: /api/arkusz

Adapter na `sim_kalkulator.serverless`, ktory wola ten sam silnik co serwer
lokalny — jedna sciezka obliczeniowa dla obu srodowisk.
"""

import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN))

TRASA = "arkusz"
LIMIT_ZADANIA = 2_000_000


class handler(BaseHTTPRequestHandler):  # noqa: N801 — nazwa wymagana przez platforme
    """Musi byc definicja klasy na NAJWYZSZYM poziomie modulu.

    Platforma szuka `handler` analiza skladni, przegladajac wylacznie ciało
    modulu. Przypisanie schowane w bloku `try` jest dla niej niewidoczne
    i konczy sie bledem "Could not find a top-level app, application,
    or handler".

    Silnik importowany jest leniwie, przy obsludze zadania. Dzieki temu
    niekompletne srodowisko daje czytelna diagnoze zamiast pustego 500,
    a wykrywanie `handler` pozostaje niezalezne od powodzenia importu.
    """

    def do_GET(self):  # noqa: N802
        self._obsluz(b"")

    def do_POST(self):  # noqa: N802
        dlugosc = int(self.headers.get("Content-Length") or 0)
        if dlugosc > LIMIT_ZADANIA:
            return self._odmow("Zadanie zbyt duze.")
        self._obsluz(self.rfile.read(dlugosc) if dlugosc > 0 else b"")

    def _obsluz(self, cialo):
        try:
            from sim_kalkulator import serverless
        except Exception:  # noqa: BLE001 — straznik startu, lapie wszystko
            return self._awaria(traceback.format_exc())
        try:
            serverless.obsluz(self, TRASA, cialo)
        except Exception:  # noqa: BLE001 — zadne zadanie nie moze zostac bez odpowiedzi
            return self._awaria(traceback.format_exc())

    def _odmow(self, powod):
        self._json(400, {"ok": False, "typ": "zadanie", "powod": powod})

    def _awaria(self, slad):
        try:
            zawartosc = sorted(p.name for p in KORZEN.iterdir())[:40]
        except OSError as exc:
            zawartosc = ["blad odczytu: %s" % exc]
        self._json(500, {
            "ok": False,
            "typ": "start",
            "powod": slad.strip().splitlines()[-1],
            "slad": slad.splitlines()[-6:],
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
        })

    def _json(self, kod, dane):
        tresc = json.dumps(dane, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(tresc)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(tresc)

    def log_message(self, format, *args):
        pass
