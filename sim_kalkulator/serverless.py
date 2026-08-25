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
import sys
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


def raport_diagnostyczny() -> Dict[str, Any]:
    """Stan srodowiska uruchomieniowego: czy wszystko, czego potrzebuje silnik,
    jest na miejscu i czy da sie policzyc wariant.

    Funkcje serverless dostaja pliki spoza katalogu `api/` tylko wtedy, gdy
    platforma dolozy je do paczki. Ten raport mowi wprost, czy tak sie stalo —
    zamiast zostawiac 500 bez wyjasnienia. Uzywany i przez wdrozenie,
    i przez serwer lokalny, zeby dalo sie porownac oba srodowiska.

    Nie ujawnia zmiennych srodowiskowych ani zawartosci plikow.
    """
    import platform

    raport: Dict[str, Any] = {
        "python": platform.python_version(),
        "katalog_roboczy": os.getcwd(),
        "korzen_wyliczony": str(KORZEN),
        "sys_path": [p for p in sys.path if p][:12],
    }

    def sprawdz(nazwa: str, wzgledna: str) -> None:
        cel = KORZEN / wzgledna
        raport[nazwa] = {"sciezka": str(cel), "istnieje": cel.exists()}
        if cel.exists() and cel.is_dir():
            raport[nazwa]["pliki"] = sorted(p.name for p in cel.iterdir())[:40]

    sprawdz("pakiet_silnika", "sim_kalkulator")
    sprawdz("interfejs", "web/index.html")
    sprawdz("parametry", DOMYSLNE_WEJSCIE)
    sprawdz("katalog_przykladow", "przyklady")

    try:
        raport["korzen_zawartosc"] = sorted(p.name for p in KORZEN.iterdir())[:40]
    except OSError as exc:
        raport["korzen_zawartosc"] = [f"blad odczytu: {exc}"]

    # Prawdziwy test: czy silnik da sie zaimportowac i policzyc wariant.
    try:
        from .dane import zbuduj as _zbuduj
        from .silnik import przelicz

        wynik = przelicz(_zbuduj(parametry_bazowe()))
        raport["silnik"] = {
            "import": "ok",
            "przeliczenie": "ok",
            "domyka_sie": wynik.domyka_sie,
            "projekt": wynik.wejscie.projekt.nazwa,
        }
    except Exception as exc:  # noqa: BLE001 — diagnostyka ma zlapac wszystko
        import traceback

        raport["silnik"] = {
            "import": "blad",
            "wyjatek": f"{type(exc).__name__}: {exc}",
            "slad": traceback.format_exc().splitlines()[-6:],
        }

    for nazwa in ("openpyxl", "yaml"):
        try:
            modul = __import__(nazwa)
            raport[f"zaleznosc_{nazwa}"] = getattr(modul, "__version__", "obecna")
        except Exception as exc:  # noqa: BLE001
            raport[f"zaleznosc_{nazwa}"] = f"BRAK: {exc}"

    kompletne = (
        raport["pakiet_silnika"]["istnieje"]
        and raport["interfejs"]["istnieje"]
        and raport["parametry"]["istnieje"]
        and raport["silnik"].get("przeliczenie") == "ok"
    )
    raport["ok"] = kompletne
    raport["werdykt"] = (
        "Srodowisko jest kompletne — silnik importuje sie i liczy."
        if kompletne
        else "Srodowisko jest niekompletne — patrz pola 'istnieje' i 'silnik' powyzej."
    )
    return raport


def zbuduj_uchwyt_diagnostyczny():
    """Buduje klase `handler` podajaca raport diagnostyczny."""
    import json

    class UchwytDiagnostyczny(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            raport = raport_diagnostyczny()
            tresc = json.dumps(raport, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200 if raport["ok"] else 500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(tresc)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(tresc)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return UchwytDiagnostyczny
