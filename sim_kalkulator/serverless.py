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


def _wyslij(uchwyt, kod: int, tresc: bytes, typ: str) -> None:
    uchwyt.send_response(kod)
    uchwyt.send_header("Content-Type", typ)
    uchwyt.send_header("Content-Length", str(len(tresc)))
    uchwyt.send_header("Cache-Control", "no-store")
    uchwyt.end_headers()
    uchwyt.wfile.write(tresc)


def _wyslij_json(uchwyt, kod: int, dane: Dict[str, Any]) -> None:
    _wyslij(
        uchwyt,
        kod,
        json.dumps(dane, ensure_ascii=False, default=_api.serializowalne).encode("utf-8"),
        "application/json; charset=utf-8",
    )


def obsluz(uchwyt, trasa: str, cialo: bytes) -> None:
    """Jedyne wejscie funkcji serverless. Trasa decyduje, co sie dzieje.

    Uchwyt jest instancja BaseHTTPRequestHandler zdefiniowana w pliku funkcji.
    Ta warstwa tylko pisze odpowiedz — liczy `sim_kalkulator.api`, czyli ten sam
    silnik, ktory obsluguje serwer lokalny.
    """
    if trasa == "index":
        return _obsluz_strone(uchwyt)
    if trasa == "diag":
        raport = raport_diagnostyczny()
        return _wyslij_json(uchwyt, 200 if raport["ok"] else 500, raport)

    try:
        zadanie = json.loads(cialo.decode("utf-8")) if cialo else {}
        zmiany = zadanie.get("zmiany") or {}
    except ValueError as exc:
        return _wyslij_json(
            uchwyt, 400, {"ok": False, "typ": "zadanie", "powod": str(exc)}
        )

    try:
        kod, dane = _api.obsluz(trasa, parametry_bazowe(), zmiany)
    except BladWalidacji as exc:
        return _wyslij_json(uchwyt, 400, {"ok": False, "typ": "walidacja", "powod": str(exc)})
    _wyslij_json(uchwyt, kod, dane)


def _obsluz_strone(uchwyt) -> None:
    """Podaje jednoplikowy interfejs z `web/index.html`."""
    strona = KORZEN / "web" / "index.html"
    try:
        tresc = strona.read_bytes()
    except OSError as exc:
        return _wyslij_json(
            uchwyt,
            500,
            {
                "ok": False,
                "typ": "start",
                "powod": f"Nie mozna wczytac interfejsu: {exc}",
                "sciezka": str(strona),
                "podpowiedz": (
                    "Plik web/index.html nie trafil do paczki funkcji — sprawdz "
                    "includeFiles w vercel.json."
                ),
            },
        )
    _wyslij(uchwyt, 200, tresc, "text/html; charset=utf-8")
