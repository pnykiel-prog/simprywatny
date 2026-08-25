"""Adapter funkcji serverless Vercela na wspolna warstwe API.

Kazdy plik w katalogu `api/` jest osobna funkcja i zawiera wylacznie dwie
linijki — cala mechanika siedzi tutaj. Katalog `api/` musi zawierac same
funkcje z obiektem `handler`; plik pomocniczy w srodku wywrocilby build.

Wszystkie funkcje wolaja ten sam `sim_kalkulator.api`, ktory wola ten sam
silnik — nie ma drugiej sciezki obliczeniowej, ktora moglaby sie rozjechac
z lokalnym serwerem.

Srodowisko serverless jest bezstanowe i ma system plikow tylko do odczytu,
wiec parametry bazowe wczytywane sa z repozytorium przy kazdym wywolaniu,
a arkusz wraca strumieniem zamiast byc zapisywany na dysk.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict

KORZEN = Path(__file__).resolve().parent.parent

from . import api as _api
from .dane import BladWalidacji

# Wariant startowy mozna podmienic zmienna srodowiskowa w ustawieniach projektu.
DOMYSLNE_WEJSCIE = os.environ.get("SIM_WEJSCIE", "przyklady/domykajacy_sie.yaml")

_bazowe_cache: Dict[str, Any] = {}


def parametry_bazowe() -> Dict[str, Any]:
    """Parametry z repozytorium. Cache przezywa cieple wywolania tej samej instancji."""
    if not _bazowe_cache:
        sciezka = KORZEN / DOMYSLNE_WEJSCIE
        if not sciezka.exists():
            raise BladWalidacji(
                f"Nie ma pliku wejsciowego {DOMYSLNE_WEJSCIE}. Ustaw zmienna "
                "srodowiskowa SIM_WEJSCIE na sciezke wzgledem korzenia repozytorium."
            )
        _bazowe_cache.update(_api.wczytaj_parametry(sciezka))
    return _bazowe_cache


def zbuduj_uchwyt(akcja: str):
    """Buduje klase `handler` obslugujaca jedna akcje API."""

    class Uchwyt(BaseHTTPRequestHandler):
        def _wyslij(self, kod: int, tresc: bytes, typ: str) -> None:
            self.send_response(kod)
            self.send_header("Content-Type", typ)
            self.send_header("Content-Length", str(len(tresc)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(tresc)

        def _json(self, kod: int, dane: Dict[str, Any]) -> None:
            self._wyslij(
                kod,
                json.dumps(dane, ensure_ascii=False, default=_api.serializowalne).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def _wykonaj(self, zmiany: Dict[str, Any]) -> None:
            try:
                kod, dane = _api.obsluz(akcja, parametry_bazowe(), zmiany)
            except BladWalidacji as exc:
                return self._json(400, {"ok": False, "typ": "walidacja", "powod": str(exc)})
            except Exception as exc:  # noqa: BLE001 — zadne zadanie nie moze zostac bez odpowiedzi
                import traceback

                traceback.print_exc()
                return self._json(
                    500, {"ok": False, "typ": "serwer", "powod": f"{type(exc).__name__}: {exc}"}
                )
            self._json(kod, dane)

        def do_GET(self) -> None:  # noqa: N802
            self._wykonaj({})

        def do_POST(self) -> None:  # noqa: N802
            try:
                dlugosc = int(self.headers.get("Content-Length") or 0)
                if dlugosc > 2_000_000:
                    raise BladWalidacji("Zadanie zbyt duze.")
                cialo = json.loads(self.rfile.read(dlugosc).decode("utf-8")) if dlugosc else {}
            except (ValueError, BladWalidacji) as exc:
                return self._json(400, {"ok": False, "typ": "zadanie", "powod": str(exc)})
            self._wykonaj(cialo.get("zmiany") or {})

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Uchwyt


def zbuduj_uchwyt_strony():
    """Buduje klase `handler` serwujaca jednoplikowy interfejs."""
    strona = KORZEN / "web" / "index.html"

    class UchwytStrony(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            try:
                tresc = strona.read_bytes()
            except OSError as exc:
                komunikat = f"Nie mozna wczytac interfejsu: {exc}".encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(komunikat)))
                self.end_headers()
                self.wfile.write(komunikat)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(tresc)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(tresc)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return UchwytStrony
